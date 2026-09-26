"""Descarga educada y estable. Prioriza no molestar al sitio sobre la velocidad.

Política (la misma para los cinco portales):
  - User-Agent HONESTO que identifica al bot y al proyecto. No se rotan user-agents ni
    se simula un navegador humano: eso es evadir la detección, y si un sitio decide no
    atender bots, la respuesta correcta es respetarlo.
  - robots.txt: se consulta por dominio y se obedece (Disallow y Crawl-delay).
  - Pausa mínima por dominio de `min_delay` s (o el Crawl-delay, si es mayor) más un
    `jitter` aleatorio, para no generar ráfagas.
  - Reintentos con backoff exponencial ante 429/5xx y errores de red; se respeta el
    encabezado Retry-After.
  - Bloqueo = 401/403, o una página de desafío (Cloudflare, DataDome, PerimeterX,
    CAPTCHA). Se lanza `Blocked`: quien llama registra el fallo, omite ese portal y sigue
    con los demás. Nunca se intenta resolver un CAPTCHA ni saltar un desafío.
  - Caché en disco con TTL: repetir una búsqueda no vuelve a golpear al sitio.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import time
import urllib.error
import urllib.request
import urllib.robotparser
import zlib
from pathlib import Path
from typing import Callable, Dict, Optional
from urllib.parse import urlsplit

USER_AGENT = ("Mozilla/5.0 (compatible; UdeC-GenAI-scout/0.1; proyecto academico "
              "Universidad de Concepcion; +https://github.com/benjamin-cpu-alt/Generative-AI-UdeC)")

# Marcas de páginas de desafío. Se buscan solo en respuestas sospechosas (status de
# error) o en el <title>, porque muchas páginas normales cargan scripts de reCAPTCHA
# para sus formularios de contacto (se verificó en Yapo y PortalPM).
_CHALLENGE_TITLES = ("just a moment", "attention required", "access denied", "un momento",
                     "verifying you are human", "verificando", "captcha")
_CHALLENGE_BODY = ("cf-chl-", "challenge-platform/h/", "id=\"challenge-form\"", "captcha-delivery.com",
                   "px-captcha", "_incapsula_resource", "cdn-cgi/challenge")


class FetchError(Exception):
    """No se pudo obtener la página (red, 404/410, reintentos agotados)."""

    def __init__(self, url: str, reason: str, status: Optional[int] = None):
        super().__init__(f"{reason}: {url}")
        self.url, self.reason, self.status = url, reason, status


class Blocked(FetchError):
    """El sitio no atiende a este bot (robots.txt, 401/403 o página de desafío)."""


def looks_like_challenge(status: int, body: str) -> bool:
    head = body[:4000].casefold()
    title = ""
    if "<title" in head:
        title = head.split("<title", 1)[1].split(">", 1)[-1].split("</title", 1)[0]
    if any(t in title for t in _CHALLENGE_TITLES):
        return True
    if status >= 400 and any(m in head for m in _CHALLENGE_BODY):
        return True
    return False


def _decode(raw: bytes, encoding: Optional[str], charset: Optional[str]) -> str:
    if encoding == "gzip":
        raw = gzip.decompress(raw)
    elif encoding == "deflate":
        raw = zlib.decompress(raw)
    return raw.decode(charset or "utf-8", errors="replace")


Opener = Callable[[urllib.request.Request, float], "urllib.response.addinfourl"]


class PoliteFetcher:
    def __init__(self, user_agent: str = USER_AGENT, min_delay: float = 3.0, jitter: float = 2.0,
                 max_retries: int = 3, timeout: float = 30.0, cache_dir: Optional[Path] = None,
                 cache_ttl_s: float = 6 * 3600, respect_robots: bool = True,
                 opener: Optional[Opener] = None, sleep: Callable[[float], None] = time.sleep,
                 log: Callable[[str], None] = lambda m: None):
        self.user_agent = user_agent
        self.min_delay, self.jitter = min_delay, jitter
        self.max_retries, self.timeout = max_retries, timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_ttl_s = cache_ttl_s
        self.respect_robots = respect_robots
        self._open = opener or (lambda req, t: urllib.request.urlopen(req, timeout=t))
        self._sleep = sleep
        self.log = log
        self._last: Dict[str, float] = {}
        self._robots: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self.requests_made = 0

    # ------------------------------------------------------------- robots ----
    def _robots_for(self, url: str) -> Optional[urllib.robotparser.RobotFileParser]:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                body = self._request(f"{origin}/robots.txt", accept="text/plain", check_robots=False,
                                     use_cache=True, retries=1)
                rp.parse(body.splitlines())
                self._robots[origin] = rp
            except FetchError as e:
                # Sin robots.txt legible no hay restricciones declaradas (RFC 9309, 4xx).
                self.log(f"robots.txt no disponible en {origin} ({e.reason}); se asume sin restricciones")
                self._robots[origin] = None
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        rp = self._robots_for(url) if self.respect_robots else None
        return rp is None or rp.can_fetch(self.user_agent, url)

    def _delay_for(self, url: str) -> float:
        rp = self._robots_for(url) if self.respect_robots else None
        crawl = (rp.crawl_delay(self.user_agent) if rp else None) or 0
        return max(self.min_delay, float(crawl))

    # -------------------------------------------------------------- caché ----
    def _cache_path(self, url: str) -> Optional[Path]:
        if not self.cache_dir:
            return None
        return self.cache_dir / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")

    def _cache_get(self, url: str) -> Optional[str]:
        p = self._cache_path(url)
        if not p or not p.exists():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if time.time() - d.get("t", 0) > self.cache_ttl_s:
            return None
        return d.get("body")

    def _cache_put(self, url: str, body: str) -> None:
        p = self._cache_path(url)
        if p:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"url": url, "t": time.time(), "body": body}), encoding="utf-8")

    # ------------------------------------------------------------ petición ----
    def get(self, url: str, accept: str = "text/html,application/xhtml+xml") -> str:
        """Descarga `url` respetando todas las reglas. Lanza `Blocked` o `FetchError`."""
        return self._request(url, accept=accept, check_robots=True, use_cache=True, retries=self.max_retries)

    def _wait_turn(self, url: str, check_robots: bool) -> None:
        host = urlsplit(url).netloc
        delay = self._delay_for(url) if check_robots else self.min_delay
        wait = self._last.get(host, 0) + delay + random.uniform(0, self.jitter) - time.time()
        if wait > 0:
            self._sleep(wait)
        self._last[host] = time.time()

    def _request(self, url: str, accept: str, check_robots: bool, use_cache: bool, retries: int) -> str:
        if use_cache:
            cached = self._cache_get(url)
            if cached is not None:
                return cached
        if check_robots and self.respect_robots and not self.allowed(url):
            raise Blocked(url, "robots.txt no permite esta ruta")

        last_err = "sin respuesta"
        for attempt in range(retries + 1):
            self._wait_turn(url, check_robots)
            req = urllib.request.Request(url, headers={
                "User-Agent": self.user_agent, "Accept": accept,
                "Accept-Language": "es-CL,es;q=0.9", "Accept-Encoding": "gzip, deflate"})
            status, retry_after = 0, None
            try:
                self.requests_made += 1
                with self._open(req, self.timeout) as resp:
                    status = getattr(resp, "status", 200)
                    body = _decode(resp.read(), resp.headers.get("Content-Encoding"),
                                   resp.headers.get_content_charset())
                if looks_like_challenge(status, body):
                    raise Blocked(url, "página de desafío anti-bots", status)
                if use_cache:
                    self._cache_put(url, body)
                return body
            except urllib.error.HTTPError as e:
                status = e.code
                body = ""
                try:
                    body = _decode(e.read(), e.headers.get("Content-Encoding"), e.headers.get_content_charset())
                except Exception:
                    pass
                if status in (401, 403) or looks_like_challenge(status, body):
                    raise Blocked(url, f"HTTP {status}", status) from None
                if status in (404, 410):
                    raise FetchError(url, f"HTTP {status}", status) from None
                if status not in (429, 500, 502, 503, 504):
                    raise FetchError(url, f"HTTP {status}", status) from None
                retry_after = e.headers.get("Retry-After")
                last_err = f"HTTP {status}"
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = f"red: {getattr(e, 'reason', e)}"
            if attempt < retries:
                backoff = float(retry_after) if (retry_after or "").isdigit() else 5 * 2 ** attempt
                self.log(f"{last_err} en {url}; reintento {attempt + 1}/{retries} en {backoff:.0f}s")
                self._sleep(backoff)
        if last_err == "HTTP 429":
            raise Blocked(url, "HTTP 429 persistente (el sitio limita a este bot)", 429)
        raise FetchError(url, f"reintentos agotados ({last_err})")
