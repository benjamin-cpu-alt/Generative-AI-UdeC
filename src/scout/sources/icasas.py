"""iCasas (icasas.cl).

URL de búsqueda (verificada 26-sep-2026):
  https://www.icasas.cl/venta/{departamentos|casas}/{provincia}/{comuna-sin-artículo}/list[/p_N]
  p.ej. /venta/departamentos/santiago/condes/list. La ruta sin /list es un directorio
  de enlaces, no un listado. /venta/departamentos/region-metropolitana/... responde 410.

SUPUESTOS sobre el listado (15 avisos por página):
  - Cada aviso es <li class="serp-snippet ad ..."> con microdatos schema.org:
    itemprop latitude/longitude/addressLocality/streetAddress en <meta content=...>.
  - Precio en el elemento .price, formato chileno ("UF 1.750").
  - Dormitorios y baños junto a los íconos .icon-r-bed / .icon-r-bathroom.
  - Enlace al aviso: href="/propiedad/{id}". La descripción de la tarjeta viene cortada.
SUPUESTOS sobre el aviso:
  - Descripción completa en p.description (dentro de div.container-body.detail).
"""
from __future__ import annotations

import re
from typing import Iterator, List, Optional

from .. import comunas
from ..listing import Listing, cl_number, first_int
from .base import SearchQuery, Source, SourceError, clean_text, soup

_CAT = {"departamento": "departamentos", "casa": "casas"}


def _icon_number(card, cls: str) -> Optional[int]:
    icon = card.select_one(f".{cls}")
    if not icon:
        return None
    for node in (icon.parent, icon.parent.parent if icon.parent else None):
        if node is not None:
            n = first_int(node.get_text(" ", strip=True))
            if n is not None:
                return n
    return None


class ICasas(Source):
    name = "icasas"
    home = "https://www.icasas.cl"
    detail_required = True

    def search_urls(self, q: SearchQuery) -> Iterator[str]:
        base = f"{self.home}/venta/{_CAT[q.property_type]}/{comunas.icasas_path(q.comuna)}/list"
        yield base
        for page in range(2, q.max_pages + 1):
            yield f"{base}/p_{page}"

    def parse_search(self, body: str, url: str, q: SearchQuery) -> List[Listing]:
        s = soup(body)
        cards = s.select("li.serp-snippet")
        if not cards and "serp-snippet" not in body:
            raise SourceError("sin tarjetas li.serp-snippet")
        out = []
        for card in cards:
            a = card.find("a", href=re.compile(r"/propiedad/"))
            if not a:
                continue
            props = {m.get("itemprop"): m.get("content") for m in card.find_all("meta", itemprop=True)}
            price_el = card.select_one(".price")
            price_txt = price_el.get_text(" ", strip=True) if price_el else ""
            href = a["href"] if a["href"].startswith("http") else self.home + a["href"]
            locality = (props.get("addressLocality") or "").split(",")[0]
            desc_el = card.select_one("p.description, .description")
            img = card.select_one(".slider-ad img[alt]")   # no el logo de la corredora
            out.append(Listing(
                source=self.name, source_id=card.get("id") or href.rsplit("/", 1)[-1], url=href,
                title=img["alt"].strip() if img else "",
                property_type=q.property_type,
                comuna=comunas.canonical(locality) or q.comuna,
                address=props.get("streetAddress") or None,
                price_value=cl_number(price_txt) if price_txt else None,
                price_currency=("UF" if "UF" in price_txt.upper() else "CLP") if price_txt else None,
                bedrooms=_icon_number(card, "icon-r-bed"),
                bathrooms=_icon_number(card, "icon-r-bathroom"),
                lat=float(props["latitude"]) if props.get("latitude") else None,
                lon=float(props["longitude"]) if props.get("longitude") else None,
                description=clean_text(desc_el.get_text("\n")) if desc_el else "",
                needs_detail=True,
            ))
        return out

    def parse_detail(self, body: str, listing: Listing) -> Listing:
        s = soup(body)
        main = s.select_one("div.container-body.detail") or s
        desc = main.select_one("p.description")
        if desc:
            listing.description = clean_text(desc.get_text("\n"))
        listing.needs_detail = False
        return listing
