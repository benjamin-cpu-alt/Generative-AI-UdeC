"""Contrato de un adaptador de portal y utilidades de extracción compartidas.

Estrategia frente a la variabilidad del HTML, en orden de preferencia:
  1. API oficial (PortalPM: REST de WordPress).
  2. Datos estructurados que el sitio publica para buscadores: JSON-LD de schema.org,
     microdatos (`itemprop`), el JSON de estado de Next.js (`__NEXT_DATA__`). Cambian
     mucho menos que las clases CSS, porque de ellos depende el SEO del portal.
  3. Selectores CSS, solo acotados al bloque principal del aviso y con alternativas.
Cada adaptador declara sus SUPUESTOS sobre el DOM en su docstring; si un supuesto deja
de cumplirse, el adaptador devuelve menos campos (y el análisis lo marca como no
verificable) en vez de inventarlos.
"""
from __future__ import annotations

import html as htmllib
import json
import re
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from bs4 import BeautifulSoup

from ..listing import Listing


@dataclass
class SearchQuery:
    comuna: str                  # nombre canónico de la RM
    property_type: str           # "departamento" | "casa"
    max_pages: int = 2


class SourceError(Exception):
    """El formato de la respuesta no es el esperado (cambió el sitio)."""


class Source:
    name: str = ""
    home: str = ""
    # True si la tarjeta del listado no trae descripción completa y hay que abrir el aviso
    detail_required: bool = False

    def __init__(self):
        self.notes: List[str] = []   # avisos para el reporte (p.ej. resultados truncados)

    def prepare(self, fetcher, queries: List["SearchQuery"]) -> None:
        """Consultas previas (p.ej. traducir comunas a ids internos). Por defecto nada."""

    def search_urls(self, q: SearchQuery) -> Iterator[str]:
        raise NotImplementedError

    def parse_search(self, body: str, url: str, q: SearchQuery) -> List[Listing]:
        raise NotImplementedError

    def parse_detail(self, body: str, listing: Listing) -> Listing:
        return listing


# ---------------------------------------------------------------- utilidades ----

def soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(body, "html.parser")


def json_ld(body: str) -> List[dict]:
    """Todos los objetos JSON-LD de la página, aplanando `@graph` y listas."""
    out: List[dict] = []
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', body, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                if "@graph" in d:
                    stack.extend(d["@graph"] if isinstance(d["@graph"], list) else [d["@graph"]])
                out.append(d)
    return out


def ld_of_type(body: str, *types: str) -> List[dict]:
    def t(d):
        v = d.get("@type")
        return v if isinstance(v, list) else [v]
    return [d for d in json_ld(body) if any(x in types for x in t(d))]


def next_data(body: str) -> Optional[dict]:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', body, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def clean_text(text: Optional[str]) -> str:
    """HTML -> texto plano: <br> y <p> como saltos, entidades resueltas, espacios colapsados."""
    if not text:
        return ""
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>", "\n", text)
    t = re.sub(r"<[^>]+>", " ", t)
    t = htmllib.unescape(t).replace("\r", "")
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def meta(body: str, prop: str) -> Optional[str]:
    m = re.search(rf'<meta (?:property|name)="{re.escape(prop)}" content="([^"]*)"', body)
    return htmllib.unescape(m.group(1)) if m else None
