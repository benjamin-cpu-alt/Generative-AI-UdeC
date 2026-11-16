"""Comparación campo a campo entre lo que leyó el sistema (`hechos`) y el `truth` de un aviso.

Lo usan `scripts/atribucion_e3.py` (¿en qué agente nace cada error?) y
`scripts/ft/build_lector_data.py` (cada etiqueta de entrenamiento se comprueba con las mismas
herramientas que usa el sistema). No lo usa ningún agente: el `truth` nunca entra a un prompt.
"""
from __future__ import annotations

from typing import Dict, Optional

from matcher import grounding, rules
from matcher.schema import Case, Property

from . import tools

CAMPOS = ("comuna", "dormitorios", "precio", "arriendo", "distancia", "estacionamiento", "mascotas")


def verdad(prop: Property, case: Case) -> Dict:
    """El `truth` del aviso en las mismas unidades que `hechos` (CLP, metros, categorías)."""
    t = prop.truth
    pets = "no_explicita" if not t.pets.explicit else ("permitidas" if t.pets.allowed else "no_permitidas")
    return {"comuna": tools.comuna_canonica(t.location) or t.location,
            "dormitorios": t.bedrooms,
            "precio": rules.price_in_clp(prop, case.uf_value),
            "arriendo": t.rent_monthly_clp,
            "distancia": t.distance_transport_m,
            "estacionamiento": t.parking,
            "mascotas": (pets, tuple(sorted(t.pets.species)) if pets == "permitidas" else (),
                         t.pets.max_kg if pets == "permitidas" else None)}


def leido(h: Dict) -> Dict:
    """`hechos` de un aviso en la misma forma que `verdad`."""
    pol = h.get("mascotas")
    return {"comuna": tools.comuna_canonica(h.get("comuna")) or h.get("comuna"),
            "dormitorios": h.get("dormitorios"),
            "precio": h.get("precio"), "arriendo": h.get("arriendo"),
            "distancia": tools.distancia(h),
            "estacionamiento": h.get("estacionamiento"),
            "mascotas": (("duda" if h.get("_mascotas_duda") else pol),
                         tuple(sorted(h.get("especies") or [])) if pol == "permitidas" else (),
                         h.get("mascotas_kg") if pol == "permitidas" else None)}


def igual(campo: str, v, t, uf: float) -> bool:
    if campo in ("precio", "arriendo"):
        if v is None or t is None:
            return v is None and t is None
        return abs(v - t) <= max(uf, 0.005 * t)          # redondeo de UF
    if campo == "estacionamiento":                         # lo que decide: ¿sirve o no?
        return (v in ("propio", "asignado")) == (t in ("propio", "asignado"))
    return v == t


def marcado(campo: str, dudas: Dict[str, str]) -> bool:
    """¿`dudas` marcó el campo para el Verificador? (el peso de la mascota va con `mascotas`)"""
    return campo in dudas or (campo == "mascotas" and "mascotas_kg" in dudas)


def fragmento_trae_dato(campo: str, spans: Dict, t, uf: float) -> Optional[bool]:
    """¿El fragmento que copió el Lector contiene el dato verdadero? Si no lo contiene, el
    error nace en el Lector; si lo contiene y aun así quedó mal leído, nace en `anclar`.
    Para leer el fragmento se usa `interpretar`, el lector de `comprobar`, que entiende más
    formatos que `anclar` (jerga, cifras en palabras, «habitaciones»)."""
    frs = [spans.get(k) for k in tools.SPAN_DE[campo] if spans.get(k)]
    if not frs:
        return False
    if campo == "comuna":
        return any(tools.comuna_canonica(f) == t for f in frs)
    if campo in ("dormitorios", "precio", "arriendo", "distancia"):
        if t is None:
            return True
        vals = [v for f in frs for v in tools.interpretar(campo, f, uf)]
        return any(igual(campo, v, t, uf) for v in vals)
    if campo == "estacionamiento":
        return any(igual(campo, grounding.parse_parking(f, strict=True, apart=True), t, uf) for f in frs)
    return True      # mascotas: hay una frase copiada; su lectura depende del parser
