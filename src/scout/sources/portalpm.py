"""Portal PM (portalpm.cl): portal de PROYECTOS NUEVOS de inmobiliarias.

Se usa su API oficial (REST de WordPress + tema Houzez) en vez del HTML
(verificada 26-sep-2026; robots.txt solo prohíbe /wp-admin/):
  /wp-json/wp/v2/property_city?search={comuna}    -> id de la comuna
  /wp-json/wp/v2/property_type                    -> ids de "departamento" y "casa"
  /wp-json/wp/v2/property_feature                 -> nombres de características
  /wp-json/wp/v2/properties?property_city=ID&property_type=ID&per_page=50&page=N

SUPUESTOS sobre la respuesta de `properties`:
  - property_meta.fave_property_price: número SIN formato ("2308") en UF. La moneda no
    viene en el campo; se asume UF porque el sitio lo muestra como "UF2,308" en todas
    las fichas revisadas. fave_property_price_prefix = "Desde" => precio mínimo.
  - fave_property_bedrooms: "2" o un rango "1 - 2" (tipologías del proyecto).
  - houzez_geolocation_lat / _long: coordenadas.
  - content.rendered: descripción en HTML.
Todo aviso de este portal es un proyecto con tipologías: su precio "desde" no se puede
asociar a una cantidad de dormitorios, así que el análisis nunca lo aprueba solo (va a
"revisar") salvo que lo descarte un dato verificado (p.ej. "desde" > presupuesto).
"""
from __future__ import annotations

import json
import re
from typing import Dict, Iterator, List
from urllib.parse import quote

from .. import comunas
from ..fetch import FetchError
from ..listing import Listing, first_int
from .base import SearchQuery, Source, SourceError, clean_text

_FIELDS = "id,link,title,content,property_meta,property_feature"


class PortalPM(Source):
    name = "portalpm"
    home = "https://www.portalpm.cl"

    def __init__(self):
        super().__init__()
        self.city_ids: Dict[str, int] = {}
        self.type_ids: Dict[str, int] = {}
        self.features: Dict[int, str] = {}

    def _api(self, fetcher, path: str):
        return json.loads(fetcher.get(f"{self.home}/wp-json/wp/v2/{path}", accept="application/json"))

    def prepare(self, fetcher, queries: List[SearchQuery]) -> None:
        self.type_ids = {t["slug"]: t["id"] for t in self._api(fetcher, "property_type?per_page=100&_fields=id,slug")}
        try:
            self.features = {f["id"]: f["name"] for f in self._api(fetcher, "property_feature?per_page=100&_fields=id,name")}
        except (FetchError, ValueError):
            self.features = {}
        for c in {q.comuna for q in queries}:
            hits = self._api(fetcher, f"property_city?search={quote(c)}&_fields=id,name")
            match = [h for h in hits if comunas.fold(h.get("name", "")) == comunas.fold(c)]
            if match:
                self.city_ids[c] = match[0]["id"]

    def search_urls(self, q: SearchQuery) -> Iterator[str]:
        city, ptype = self.city_ids.get(q.comuna), self.type_ids.get(q.property_type)
        if city is None or ptype is None:
            return   # la comuna no tiene proyectos en el portal
        for page in range(1, q.max_pages + 1):
            yield (f"{self.home}/wp-json/wp/v2/properties?property_city={city}&property_type={ptype}"
                   f"&per_page=50&page={page}&_fields={_FIELDS}")

    def parse_search(self, body: str, url: str, q: SearchQuery) -> List[Listing]:
        try:
            items = json.loads(body)
        except ValueError:
            raise SourceError("la API no devolvió JSON")
        if not isinstance(items, list):
            raise SourceError(f"respuesta inesperada de la API: {str(items)[:120]}")
        return [self._listing(x, q) for x in items]

    def _listing(self, x: dict, q: SearchQuery) -> Listing:
        m = x.get("property_meta") or {}
        one = lambda k: (m.get(k) or [None])[0]
        beds = [int(b) for b in re.findall(r"\d+", one("fave_property_bedrooms") or "")]
        baths = [int(b) for b in re.findall(r"\d+", one("fave_property_bathrooms") or "")]
        price = one("fave_property_price")
        lat, lon = one("houzez_geolocation_lat"), one("houzez_geolocation_long")
        garage = first_int(one("fave_property_garage"))
        return Listing(
            source=self.name, source_id=str(x.get("id")), url=x.get("link", ""),
            title=clean_text((x.get("title") or {}).get("rendered")), property_type=q.property_type,
            comuna=q.comuna, address=one("fave_property_address"),
            price_value=float(price) if price and re.fullmatch(r"\d+(\.\d+)?", price) else None,
            price_currency="UF" if price else None,
            price_is_from=(one("fave_property_price_prefix") or "").strip().casefold() == "desde",
            bedrooms=min(beds) if beds else None, bedrooms_max=max(beds) if len(beds) > 1 else None,
            bathrooms=min(baths) if baths else None,
            parking_spaces=garage if garage else None,
            lat=float(lat) if lat else None, lon=float(lon) if lon else None,
            description=clean_text((x.get("content") or {}).get("rendered")),
            features=[self.features[f] for f in x.get("property_feature") or [] if f in self.features],
            is_project=True,
        )
