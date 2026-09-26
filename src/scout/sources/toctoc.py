"""TocToc (toctoc.com).

URL de búsqueda (verificada 26-sep-2026):
  https://www.toctoc.com/venta/{departamento|casa}/metropolitana/{slug-comuna}
  robots.txt prohíbe /resultados/, /Propiedades/VistaLista y /Propiedades/VistaMapa;
  esta ruta (/venta/...) está permitida.

SUPUESTOS sobre la página:
  - Es Next.js y embebe el listado completo en <script id="__NEXT_DATA__">, en
    props.pageProps.propiedades.results (respaldo: initialReduxState.PropertyState.results).
  - Cada resultado trae: urlFicha, hashId, titulo, comuna, description (texto completo),
    precios = [{prefix: "UF"|"$", value: "5.850"}] en formato chileno, dormitorios y
    bannos como LISTAS de strings (varias tipologías en proyectos), superficie,
    tipoOperacion ("Venta Usado" | "Venta Nuevo"), latitud, longitud.
  - La página renderizada en el servidor trae como MÁXIMO 260 avisos, aunque
    propiedades.total diga más (1.524 departamentos en Providencia). Ningún parámetro de
    URL la pagina (?page=2, ?pagina=2 devuelven lo mismo): el resto se carga desde el
    navegador por rutas que robots.txt prohíbe (/resultados/, VistaLista). No se sortea:
    se usa ese subconjunto y el reporte avisa cuántos quedaron fuera.
No hace falta abrir cada aviso: la descripción ya viene completa.
"""
from __future__ import annotations

from typing import Iterator, List

from .. import comunas
from ..listing import Listing, cl_number, first_int
from .base import SearchQuery, Source, SourceError, clean_text, next_data


class TocToc(Source):
    name = "toctoc"
    home = "https://www.toctoc.com"

    def search_urls(self, q: SearchQuery) -> Iterator[str]:
        yield f"{self.home}/venta/{q.property_type}/metropolitana/{comunas.slug(q.comuna)}"

    def parse_search(self, body: str, url: str, q: SearchQuery) -> List[Listing]:
        nd = next_data(body)
        if nd is None:
            raise SourceError("sin __NEXT_DATA__ (¿cambió el sitio?)")
        pp = nd.get("props", {}).get("pageProps", {})
        results = (pp.get("propiedades") or {}).get("results") \
            or pp.get("initialReduxState", {}).get("PropertyState", {}).get("results")
        if results is None:
            raise SourceError("__NEXT_DATA__ sin lista de propiedades")
        total = (pp.get("propiedades") or {}).get("total")
        if isinstance(total, int) and total > len(results):
            self.notes.append(f"{q.property_type} en {q.comuna}: el portal entrega {len(results)} "
                              f"de {total} avisos sin JavaScript; el resto no se consulta")
        return [self._listing(r, q) for r in results if r.get("urlFicha")]

    def _listing(self, r: dict, q: SearchQuery) -> Listing:
        prices = {p.get("prefix"): p.get("value") for p in (r.get("precios") or [])}
        if prices.get("UF"):
            value, currency = cl_number(prices["UF"]), "UF"
        elif prices.get("$"):
            value, currency = cl_number(prices["$"]), "CLP"
        else:
            value, currency = None, None
        beds = [b for b in (first_int(x) for x in r.get("dormitorios") or []) if b is not None]
        baths = [b for b in (first_int(x) for x in r.get("bannos") or []) if b is not None]
        areas = [a for a in (cl_number(x) for x in r.get("superficie") or []) if a is not None]
        project = r.get("tipoOperacion") == "Venta Nuevo" or len(beds) > 1
        return Listing(
            source=self.name, source_id=str(r.get("hashId") or r.get("idProperty")), url=r["urlFicha"],
            title=clean_text(r.get("titulo")), property_type=q.property_type,
            comuna=comunas.canonical(r.get("comuna") or "") or r.get("comuna") or q.comuna,
            price_value=value, price_currency=currency, price_is_from=project,
            bedrooms=min(beds) if beds else None, bedrooms_max=max(beds) if len(beds) > 1 else None,
            bathrooms=min(baths) if baths else None, area_m2=min(areas) if areas else None,
            lat=r.get("latitud"), lon=r.get("longitud"),
            description=clean_text(r.get("description")), is_project=project,
        )
