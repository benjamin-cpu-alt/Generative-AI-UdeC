"""Yapo (yapo.cl).

URL de búsqueda (verificada 26-sep-2026):
  https://www.yapo.cl/bienes-raices-venta-de-propiedades-{apartamentos|casas}/region-metropolitana-{slug}?page=N

SUPUESTOS sobre el listado:
  - Cada aviso es un <a> cuyo href termina en /{slug-del-titulo}/{id numérico de 6+ dígitos}
    dentro de /bienes-raices-venta-de-propiedades-.../.
  - La tarjeta (ancestro del enlace) muestra "N Dormitorios", "N Baños", "N m²" y
    "Región Metropolitana, {Comuna}". El precio de la tarjeta usa COMA DE MILES
    ("UF 9,950"): no se usa; el precio sale del JSON-LD del aviso.
SUPUESTOS sobre el aviso:
  - JSON-LD de tipo Product con name, description (HTML con <br/>) y
    offers.price (número) + offers.priceCurrency ("CLF" = UF, o "CLP").
  - Las coordenadas aparecen en el iframe de Google Maps: "q=-33.43%2C-70.61".
  - Dormitorios/baños/estacionamiento: <span>etiqueta</span> + valor en el mismo contenedor.
  - Las características son textos cortos sueltos ("Permite mascotas",
    "Estacionamiento bajo techo", "Estacionamiento de visitas"). Se toman solo los de
    ≤ 5 palabras que nombren un tema relevante, para no arrastrar títulos de avisos
    relacionados que la página muestra abajo.
"""
from __future__ import annotations

import re
from typing import Iterator, List

from .. import comunas
from ..listing import Listing, currency_code, first_int
from .base import SearchQuery, Source, SourceError, clean_text, ld_of_type, meta, soup

_CAT = {"departamento": "apartamentos", "casa": "casas"}
_AD_HREF = re.compile(r"/bienes-raices-venta-de-propiedades-[a-z-]+/[^/?#]+/(\d{6,})/?$")
_FEATURE = re.compile(r"mascota|estacionamiento|bodega|amoblad|ascensor|conserjer", re.I)
_ATTR_LABEL = re.compile(r"^\s*(dormitorios?|baños?|estacionamientos?)\s*$", re.I)
_COORDS = re.compile(r"[?&;]q=(-?\d{1,2}\.\d+)(?:%2C|,)(-?\d{1,3}\.\d+)")


class Yapo(Source):
    name = "yapo"
    home = "https://www.yapo.cl"
    detail_required = True

    def search_urls(self, q: SearchQuery) -> Iterator[str]:
        base = f"{self.home}/bienes-raices-venta-de-propiedades-{_CAT[q.property_type]}/region-metropolitana-{comunas.slug(q.comuna)}"
        yield base
        for page in range(2, q.max_pages + 1):
            yield f"{base}?page={page}"

    def parse_search(self, body: str, url: str, q: SearchQuery) -> List[Listing]:
        s = soup(body)
        out, seen = [], set()
        for a in s.find_all("a", href=True):
            m = _AD_HREF.search(a["href"].split("?")[0])
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            card = a
            for _ in range(6):   # sube hasta el contenedor de la tarjeta
                if card.parent is None or "Dormitorio" in card.get_text(" "):
                    break
                card = card.parent
            text = card.get_text(" ", strip=True)
            beds = re.search(r"(\d+)\s*Dormitorio", text)
            baths = re.search(r"(\d+)\s*Baño", text)
            area = re.search(r"(\d+)\s*m²", text)
            loc = re.search(r"Región Metropolitana,\s*([^|\d]+?)(?:\s+\d|$)", text)
            href = a["href"] if a["href"].startswith("http") else self.home + a["href"]
            img = card.find("img", alt=True)
            out.append(Listing(
                source=self.name, source_id=m.group(1), url=href.split("?")[0],
                title=(img["alt"] if img else a.get("title") or "").strip(),
                property_type=q.property_type,
                comuna=(comunas.canonical(loc.group(1)) if loc else None) or q.comuna,
                bedrooms=int(beds.group(1)) if beds else None,
                bathrooms=int(baths.group(1)) if baths else None,
                area_m2=float(area.group(1)) if area else None,
                needs_detail=True,
            ))
        if not out and "Dormitorio" not in body:
            raise SourceError("no se encontraron tarjetas de avisos")
        return out

    def parse_detail(self, body: str, listing: Listing) -> Listing:
        products = ld_of_type(body, "Product")
        if products:
            p = products[0]
            listing.title = listing.title or clean_text(p.get("name"))
            listing.description = clean_text(p.get("description"))
            offer = p.get("offers") or {}
            if isinstance(offer, list):
                offer = offer[0] if offer else {}
            price = offer.get("price")
            if isinstance(price, (int, float)) or (isinstance(price, str) and re.fullmatch(r"\d+(\.\d+)?", price)):
                listing.price_value = float(price)
                listing.price_currency = currency_code(offer.get("priceCurrency"))
        else:
            listing.description = clean_text(meta(body, "og:description"))
        if not listing.title:
            listing.title = clean_text(meta(body, "og:title"))
        if listing.bedrooms is None:
            m = re.search(r"(\d+)\s*dormitorios?", meta(body, "og:title") or "", re.I)
            listing.bedrooms = int(m.group(1)) if m else None
        m = _COORDS.search(body)
        if m:
            listing.lat, listing.lon = float(m.group(1)), float(m.group(2))
        s = soup(body)
        for tag in s(["script", "style", "noscript", "title", "head"]):
            tag.decompose()
        # Pares etiqueta/valor de la ficha: <span>estacionamiento</span> junto a "2".
        for t in s.find_all(string=_ATTR_LABEL):
            label = t.strip().casefold()
            value = first_int(t.parent.parent.get_text(" ", strip=True).casefold().replace(label, "", 1))
            if value is None:
                continue
            if label.startswith("dormitorio"):
                listing.bedrooms = value
            elif label.startswith("baño"):
                listing.bathrooms = value
            elif label.startswith("estacionamiento"):
                listing.parking_spaces = value
        feats = []
        for t in s.find_all(string=_FEATURE):
            txt = " ".join(t.split())
            if (1 < len(txt.split()) <= 5 and txt not in feats and not re.search(r"\d", txt)
                    and not _ATTR_LABEL.match(txt)):
                feats.append(txt)
        listing.features = feats
        listing.needs_detail = False
        return listing
