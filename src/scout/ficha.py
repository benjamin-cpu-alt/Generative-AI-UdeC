"""`Listing` -> "ficha": un aviso de texto compacto en el formato que lee el extractor
de la E2 (matcher.extract v5 + grounding g3).

Por qué reescribir el aviso en vez de pasarle la página:
  - El extractor se diseñó para avisos de ~300 tokens; una página real trae miles, con
    avisos relacionados, gastos comunes, dividendos y otros montos que el modelo podría
    copiar como precio. La ficha deja un solo precio, rotulado.
  - Los datos estructurados del portal (precio del JSON-LD, dormitorios, estacionamientos)
    se escriben en formato chileno ("UF 3.656,36", "3D/2B"), el que parsea normalize.py.
    Así Yapo, que muestra "UF 9,950", no se lee como 9,95 UF.
  - La distancia calculada con OSM (geo.py) entra como una frase más, rotulada como
    estimación. El anclaje de g3 exige que todo número exista en el texto: al estar en
    la ficha, la cadena de verificación se mantiene intacta y trazable.
El LLM sigue leyendo la descripción libre: ahí están mascotas, estacionamiento de
visitas, "escritorio convertible", y es lo que ningún dato estructurado trae.
"""
from __future__ import annotations

import re
from typing import List

from .listing import Listing, fmt_cl, fmt_price

MAX_DESCRIPTION_CHARS = 900
_TOPIC = re.compile(r"mascota|perro|gato|pet|estacionamiento|parking|metro|paradero|estaci[óo]n|"
                    r"dormitorio|escritorio|arriendo|renta|bodega|kg|kilo", re.I)
_MONEY = re.compile(r"\bUF\s*\d|\$\s*\d|\d\s*(?:UF|pesos|millones)\b", re.I)
# Solo "arriendo" identifica el arriendo: en los avisos chilenos "renta" suele ser el
# ingreso exigido al comprador ("Renta recomendada desde $1.800.000") y "mensual" aparece
# en gastos comunes y dividendos. Tomarlos por arriendo daría un ROI absurdo.
_RENT = re.compile(r"arriendo", re.I)
_NOT_RENT = re.compile(r"gasto|dividendo|sueldo|renta\b|ingreso|pie\b|cr[eé]dito", re.I)
_CONTACT = re.compile(r"https?://\S+|www\.\S+|\S+@\S+|\+?56\s*9?[\d\s]{8,}|\b9\s?\d{4}\s?\d{4}\b")


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip(" -•*·\t") for p in parts if p and p.strip(" -•*·\t")]


def compact_description(listing: Listing, limit: int = MAX_DESCRIPTION_CHARS) -> str:
    """Oraciones de la descripción, sin datos de contacto y sin montos que compitan con
    el precio (salvo el arriendo, que sirve para el ROI). Si hay que recortar, se
    privilegian las oraciones que hablan de los temas de los filtros, en su orden original."""
    sents = []
    for s in _sentences(_CONTACT.sub("", listing.description)):
        is_rent = _RENT.search(s) and not _NOT_RENT.search(s)
        if listing.price_value is not None and _MONEY.search(s) and not is_rent:
            continue
        sents.append(s if s.endswith((".", "!", "?")) else s + ".")
    if sum(len(s) + 1 for s in sents) <= limit:
        return " ".join(sents)
    keep, used = set(), 0
    for i, s in sorted(enumerate(sents), key=lambda t: (not _TOPIC.search(t[1]), t[0])):
        if used + len(s) + 1 > limit:
            continue
        keep.add(i)
        used += len(s) + 1
    return " ".join(s for i, s in enumerate(sents) if i in keep)


def render(listing: Listing) -> str:
    kind = "Casa" if listing.property_type == "casa" else "Departamento"
    parts = [f"{kind} en {listing.comuna or 'comuna no indicada'}"
             + (f", {listing.address}" if listing.address and listing.address != listing.comuna else "") + "."]

    if listing.is_project and listing.bedrooms_max:
        parts.append(f"Proyecto nuevo con tipologías de {listing.bedrooms} a {listing.bedrooms_max} dormitorios.")
    elif listing.bedrooms is not None:
        bb = f"{listing.bedrooms}D" + (f"/{listing.bathrooms}B" if listing.bathrooms is not None else "")
        parts.append(bb + (f", {fmt_cl(listing.area_m2)} m²." if listing.area_m2 else "."))

    if listing.price_value is not None and listing.price_currency:
        label = "Precio desde" if listing.price_is_from else "Precio"
        parts.append(f"{label}: {fmt_price(listing.price_value, listing.price_currency)}.")

    if listing.parking_spaces:
        n = listing.parking_spaces
        parts.append(f"Incluye {n} estacionamiento{'s' if n > 1 else ''}.")

    if listing.transit_walk_m is not None and listing.transit_name:
        parts.append(f"Distancia estimada a la estación de {listing.transit_kind} {listing.transit_name}: "
                     f"{listing.transit_walk_m} m.")

    feats = list(listing.features)
    has_own_parking = bool(listing.parking_spaces) or any(
        re.search(r"estacionamiento", f, re.I) and not re.search(r"visita", f, re.I) for f in feats)
    if has_own_parking:
        # "Estacionamiento de visitas" en la lista de amenidades del edificio no dice que la
        # unidad carezca de uno propio; si hay otra señal de estacionamiento, se omite para
        # que el extractor no lo tome como la cláusula de estacionamiento de la unidad.
        feats = [f for f in feats if not re.search(r"visita", f, re.I)]
    for f in feats:
        parts.append(f.rstrip(".") + ".")

    desc = compact_description(listing)
    if desc:
        parts.append(desc)
    return " ".join(parts)
