"""Recolección: portales -> `Listing` enriquecidos y prefiltrados, listos para analizar.

Un portal que falla no detiene la búsqueda: se registra por qué (bloqueo, robots.txt,
formato cambiado, sin resultados para esa comuna) y se sigue con los demás. Un bloqueo
(`Blocked`) inhabilita ese portal por el resto de la ejecución: insistir contra un sitio
que ya dijo que no es justamente lo que no se debe hacer.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import geo
from .fetch import Blocked, FetchError, PoliteFetcher
from .listing import Listing
from .prefilter import discard_reason, price_clp
from .profile import BuyerProfile
from .sources import REGISTRY, SearchQuery, Source, SourceError


@dataclass
class SourceStatus:
    ok: bool = True
    error: str = ""
    listings: int = 0
    requests: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class Collection:
    listings: List[Listing]
    discarded: Counter
    status: Dict[str, SourceStatus]
    duplicates: int = 0


def same_property(a: Listing, b: Listing, uf: float) -> bool:
    """Mismo inmueble publicado en dos portales: coordenadas a < 40 m, mismos dormitorios
    y precio a ±1 %. Conservador: ante la duda se tratan como distintos."""
    if None in (a.lat, a.lon, b.lat, b.lon) or a.bedrooms != b.bedrooms:
        return False
    pa, pb = price_clp(a, uf), price_clp(b, uf)
    if not pa or not pb or abs(pa - pb) > 0.01 * max(pa, pb):
        return False
    return geo.haversine_m(a.lat, a.lon, b.lat, b.lon) < 40


def enrich_transit(listing: Listing, stations: List[geo.Station], kinds: List[str]) -> None:
    if listing.lat is None or listing.lon is None or not stations:
        return
    kinds = [k for k in kinds if k in ("metro", "tren")]
    hit = geo.nearest(listing.lat, listing.lon, stations, kinds) if kinds else None
    if hit:
        station, walk = hit
        listing.transit_name, listing.transit_kind, listing.transit_walk_m = station.name, station.kind, walk


def collect(profile: BuyerProfile, fetcher: PoliteFetcher, uf: float, stations: List[geo.Station],
            source_names: List[str], max_per_source: int = 20, max_pages: int = 2,
            log: Callable[[str], None] = print) -> Collection:
    queries = [SearchQuery(c, t, max_pages) for c in profile.comunas for t in profile.tipos]
    status: Dict[str, SourceStatus] = {}
    discarded: Counter = Counter()
    kept: List[Listing] = []
    duplicates = 0

    for name in source_names:
        src: Source = REGISTRY[name]()
        st = status[name] = SourceStatus()
        before = fetcher.requests_made
        try:
            src.prepare(fetcher, queries)
            found = _search(src, queries, fetcher, st, log)
            candidates = []
            for l in found:
                enrich_transit(l, stations, profile.transportes)
                reason = discard_reason(l, profile, uf)
                if reason:
                    discarded[reason] += 1
                else:
                    candidates.append(l)
            # Con el tope por portal, primero lo más probable de servir: unidades (no
            # proyectos), con distancia calculable, y de menor precio.
            candidates.sort(key=lambda l: (l.is_project, l.transit_walk_m is None,
                                           price_clp(l, uf) or float("inf")))
            ready = []
            for l in candidates:
                if len(ready) >= max_per_source:
                    break
                if l.needs_detail:
                    try:
                        l = src.parse_detail(fetcher.get(l.url), l)
                    except Blocked:
                        raise
                    except (FetchError, SourceError) as e:
                        st.warnings.append(f"aviso omitido ({e}): {l.url}")
                        continue
                    enrich_transit(l, stations, profile.transportes)
                    reason = discard_reason(l, profile, uf)   # el aviso completo trae más datos
                    if reason:
                        discarded[reason] += 1
                        continue
                dup = next((k for k in kept if same_property(k, l, uf)), None)
                if dup:
                    duplicates += 1
                    st.warnings.append(f"duplicado de {dup.key}: {l.url}")
                    continue
                ready.append(l)
            kept += ready
            st.listings = len(ready)
            st.warnings = src.notes + st.warnings
            log(f"[{name}] {len(found)} avisos encontrados, {len(ready)} pasan al análisis")
        except Blocked as e:
            st.ok, st.error = False, f"bloqueado: {e.reason}"
            log(f"[{name}] BLOQUEADO ({e.reason}); se omite este portal y se sigue con los demás")
        except (FetchError, SourceError, ValueError) as e:
            st.ok, st.error = False, str(e)
            log(f"[{name}] FALLÓ: {e}; se omite este portal")
        st.requests = fetcher.requests_made - before
    return Collection(kept, discarded, status, duplicates)


def _search(src: Source, queries: List[SearchQuery], fetcher: PoliteFetcher, st: SourceStatus,
            log: Callable[[str], None]) -> List[Listing]:
    out: Dict[str, Listing] = {}
    for q in queries:
        for i, url in enumerate(src.search_urls(q)):
            try:
                page = src.parse_search(fetcher.get(url), url, q)
            except Blocked:
                raise
            except FetchError as e:
                if e.status in (404, 410) or i > 0:
                    # la comuna/tipo no existe en ese portal, o se acabaron las páginas
                    if i == 0:
                        st.warnings.append(f"sin listado para {q.property_type} en {q.comuna} ({e.reason})")
                    break
                raise
            except SourceError as e:
                st.warnings.append(f"formato inesperado en {url}: {e}")
                break
            new = [l for l in page if l.key not in out]
            for l in new:
                out[l.key] = l
            log(f"[{src.name}] {q.property_type} en {q.comuna}, página {i + 1}: {len(page)} avisos")
            if not new:
                break
    return list(out.values())
