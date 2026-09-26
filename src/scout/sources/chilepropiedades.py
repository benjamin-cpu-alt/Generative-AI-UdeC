"""Chilepropiedades (chilepropiedades.cl).

URL de búsqueda (verificada 26-sep-2026), paginada desde 0:
  https://chilepropiedades.cl/propiedades/venta/{departamento|casa}/{slug-comuna}/{página}
robots.txt: Crawl-delay 2 (se respeta; la pausa mínima del fetcher ya es mayor).

SUPUESTOS sobre el listado:
  - JSON-LD ItemList con las URLs de los avisos (/ver-publicacion/...). Es la fuente
    principal; las tarjetas (div.clp-list-search-card-layout) solo aportan precio y
    habitaciones para prefiltrar antes de abrir cada aviso.
SUPUESTOS sobre el aviso:
  - JSON-LD RealEstateListing: name, about.address, about.floorSize,
    offers.price (string numérico) + offers.priceCurrency. Su `description` viene
    TRUNCADA; la completa está en div.clp-description-box.
  - Datos clave en div.clp-publication-key-fact (span.clp-publication-key-label + valor).
  - Coordenadas en un script: `var publicationLocation = [ -33.42, -70.61 ];`.
  - La página muestra también avisos "comparables" con OTROS precios
    (div.clp-price-context-comparables). Por eso nunca se lee el texto de toda la
    página: solo article.clp-publication-detail-main, sin ese bloque.
"""
from __future__ import annotations

import re
from typing import Iterator, List

from .. import comunas
from ..listing import Listing, cl_number, currency_code, first_int
from .base import SearchQuery, Source, SourceError, clean_text, ld_of_type, soup

_AD = re.compile(r"/ver-publicacion/venta/[^/]+/[^/]+/[^/]+/(\d+)")
_LOC = re.compile(r"publicationLocation\s*=\s*\[\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\]")


class ChilePropiedades(Source):
    name = "chilepropiedades"
    home = "https://chilepropiedades.cl"
    detail_required = True

    def search_urls(self, q: SearchQuery) -> Iterator[str]:
        for page in range(q.max_pages):
            yield f"{self.home}/propiedades/venta/{q.property_type}/{comunas.slug(q.comuna)}/{page}"

    def parse_search(self, body: str, url: str, q: SearchQuery) -> List[Listing]:
        urls = []
        for lst in ld_of_type(body, "ItemList"):
            for it in lst.get("itemListElement") or []:
                if not isinstance(it, dict):
                    continue
                item = it.get("item")
                u = it.get("url") or (item.get("@id") if isinstance(item, dict) else item)
                if isinstance(u, str) and _AD.search(u) and u not in urls:
                    urls.append(u)
        cards = {}
        for card in soup(body).select("div.clp-list-search-card-layout"):
            a = card.find("a", href=_AD)
            if not a:
                continue
            text = card.get_text(" ", strip=True)
            href = a["href"] if a["href"].startswith("http") else self.home + a["href"]
            cards[href] = text
            if href not in urls:
                urls.append(href)
        if not urls and "clp-list-search" not in body:
            raise SourceError("sin ItemList ni tarjetas de avisos")
        out = []
        for u in urls:
            text = cards.get(u, "")
            price = re.search(r"(UF|\$)\s*([\d.]+(?:,\d+)?)", text)
            rooms = re.search(r"Habitaciones:\s*(\d+)", text)
            out.append(Listing(
                source=self.name, source_id=_AD.search(u).group(1), url=u, property_type=q.property_type,
                comuna=q.comuna,
                price_value=cl_number(price.group(2)) if price else None,
                price_currency=("UF" if price.group(1) == "UF" else "CLP") if price else None,
                bedrooms=int(rooms.group(1)) if rooms else None,
                needs_detail=True,
            ))
        return out

    def parse_detail(self, body: str, listing: Listing) -> Listing:
        for d in ld_of_type(body, "RealEstateListing"):
            listing.title = clean_text(d.get("name")) or listing.title
            about = d.get("about") or {}
            addr = about.get("address") or {}
            listing.address = addr.get("streetAddress") or listing.address
            listing.comuna = comunas.canonical(addr.get("addressLocality") or "") or listing.comuna
            size = (about.get("floorSize") or {}).get("value")
            listing.area_m2 = float(size) if isinstance(size, (int, float)) else listing.area_m2
            offer = d.get("offers") or {}
            if isinstance(offer, list):
                offer = offer[0] if offer else {}
            if offer.get("price") is not None and currency_code(offer.get("priceCurrency")):
                listing.price_value = float(str(offer["price"]).replace(",", "."))
                listing.price_currency = currency_code(offer.get("priceCurrency"))
            listing.description = clean_text(d.get("description"))
            break
        s = soup(body)
        main = s.select_one("article.clp-publication-detail-main") or s
        for noise in main.select("div.clp-price-context-comparables, div.clp-price-context-details-content, script, style"):
            noise.decompose()
        box = main.select_one("div.clp-description-box")
        if box:
            listing.description = clean_text(str(box))
        for fact in main.select("div.clp-publication-key-fact"):
            label = fact.select_one(".clp-publication-key-label")
            if not label:
                continue
            key = label.get_text(" ", strip=True).casefold()
            value = fact.get_text(" ", strip=True).replace(label.get_text(" ", strip=True), "", 1).strip()
            n = first_int(value)
            if key.startswith(("habitaci", "dormitori")) and n is not None:
                listing.bedrooms = n
            elif key.startswith("baño") and n is not None:
                listing.bathrooms = n
            elif key.startswith("estac") and n is not None:   # "Estacionamientos" o "Estac."
                listing.parking_spaces = n
            elif value:
                listing.features.append(f"{label.get_text(' ', strip=True)}: {value}")
        m = _LOC.search(body)
        if m:
            listing.lat, listing.lon = float(m.group(1)), float(m.group(2))
        listing.needs_detail = False
        return listing
