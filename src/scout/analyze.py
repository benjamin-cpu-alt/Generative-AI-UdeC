"""Integración con el analizador de la E2: cada aviso pasa por la misma cadena que se
evaluó en test y OOD, sin copias. La única diferencia es la versión del anclaje: g4 en vez
de g3. g4 agrega dos correcciones de seguridad halladas con avisos reales (ver
matcher/grounding.py) y da salidas idénticas a g3 en todas las corridas de test, dev y OOD.

  ficha (texto) -> matcher.extract.extract_facts(v5, g4)   el LLM localiza cláusulas
                -> matcher.constraints.decide               Python convierte y compara
                -> clasificación en tres grupos (esta capa)

Qué agrega esta capa, y por qué no vive en matcher/:
  1. Sin mascota, la restricción de mascotas no aplica (el criterio de la E1 siempre
     la exige; aquí la necesidad del comprador manda). Se elimina de los fallos.
  2. Separa "viola un filtro" de "no se pudo verificar". En los casos sintéticos todo
     aviso trae todos los datos; en avisos reales muchos no dicen nada de mascotas o de
     la distancia al metro. El criterio de la E2 los rechaza (no aprobar lo que no se
     puede verificar) y eso se mantiene: nunca se aprueban. Pero se muestran aparte,
     como "revisar", con el dato que falta, porque para el comprador no es lo mismo
     "no admite mascotas" que "el aviso no lo dice".
  3. Un proyecto nuevo con tipologías nunca se aprueba solo: su precio "desde" no está
     asociado a una tipología. Si ningún dato verificado lo descarta, va a "revisar".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from matcher import normalize
from matcher.constraints import (C_BEDROOMS, C_BUDGET, C_DISTANCE, C_PARKING, C_PETS, Decision,
                                 build_output, decide)
from matcher.extract import Facts, default_options, extract_facts

from . import ficha
from .listing import Listing
from .profile import BuyerProfile

APPROVED, REVIEW, REJECTED = "aprobada", "revisar", "rechazada"


@dataclass
class Result:
    listing: Listing
    ficha: str
    bucket: str
    decision: Optional[Decision] = None
    facts: Dict = field(default_factory=dict)
    violated: List[str] = field(default_factory=list)       # filtros incumplidos con dato verificado
    unverifiable: List[str] = field(default_factory=list)   # filtros que el aviso no permite verificar
    note: str = ""

    def to_dict(self) -> Dict:
        d = self.decision
        return {
            "id": self.listing.key, "url": self.listing.url, "fuente": self.listing.source,
            "titulo": self.listing.title, "comuna": self.listing.comuna, "grupo": self.bucket,
            "price_clp": d.price_clp if d else None, "roi_pct": d.roi_pct if d else None,
            "incumple": self.violated, "no_verificable": self.unverifiable, "nota": self.note,
            "transporte": ({"estacion": self.listing.transit_name, "tipo": self.listing.transit_kind,
                            "metros_a_pie_estimados": self.listing.transit_walk_m}
                           if self.listing.transit_name else None),
            "ficha": self.ficha, "hechos": self.facts,
            "notas_decision": d.notes if d else [],
        }


def unverifiable_constraints(f: Facts, profile: BuyerProfile) -> List[str]:
    """Filtros cuyo dato quedó vacío tras el anclaje (el aviso no lo dice, o no se pudo
    anclar). Son los mismos casos que `decide` rechaza por 'no verificable'."""
    out = []
    if normalize.parse_money(f.price_text)[0] is None:
        out.append(C_BUDGET)
    if profile.tiene_mascota and f.pets_policy == "no_mencionada":
        out.append(C_PETS)
    if normalize.parse_distance_m(f.distance_metro_text) is None and normalize.parse_distance_m(f.distance_bus_text) is None:
        out.append(C_DISTANCE)
    if f.bedrooms is None:
        out.append(C_BEDROOMS)
    if profile.requiere_estacionamiento and (f.parking == "no_mencionado" or _visitors_from_amenities(f)):
        out.append(C_PARKING)
    return out


def _visitors_from_amenities(f: Facts) -> bool:
    """`visitas` leído de una frase que el MODELO no eligió como la del estacionamiento de la
    unidad, sino que el código recuperó del aviso (g2+). En avisos reales esa frase suele
    ser la lista de amenidades del edificio ("salas de eventos, ... estacionamientos de
    visitas"), que no dice si la unidad trae uno propio: es un dato ausente, no un
    incumplimiento. Sigue sin aprobarse; pasa a 'revisar'."""
    return f.parking == "visitas" and any(w.startswith("parking_text: recuperado") for w in f.warnings)


Extractor = Callable[[str, str], Facts]


def llm_extractor(model: str, prompt_version: str = "v5", grounding_version: str = "g4") -> Extractor:
    # contexto de 4096: la ficha (~1.300 caracteres) + el prompt v5 superan a veces los
    # 2048 que bastaban para los avisos sintéticos
    options = default_options(num_ctx=4096, num_predict=384)
    return lambda pid, text: extract_facts(model, pid, text, options, timeout=180,
                                           prompt_version=prompt_version,
                                           grounding_version=grounding_version)


def analyze_one(listing: Listing, profile: BuyerProfile, uf_value: float, extract: Extractor) -> Result:
    text = ficha.render(listing)
    facts = extract(listing.key, text)
    if facts.error:
        return Result(listing, text, REVIEW, facts=facts.to_dict(),
                      note=f"la extracción falló ({facts.error}); no se pudo evaluar")
    hc, sc = profile.hard_constraints(uf_value), profile.soft_constraints()
    d = decide(listing.key, facts, hc, sc, uf_value)
    if not profile.tiene_mascota and C_PETS in d.failed_constraints:
        d.failed_constraints.remove(C_PETS)
        d.notes.append("mascotas: el comprador no tiene -> no aplica")
    missing = [c for c in unverifiable_constraints(facts, profile) if c in d.failed_constraints]
    violated = [c for c in d.failed_constraints if c not in missing]

    if violated:
        bucket, note = REJECTED, ""
    elif missing:
        bucket, note = REVIEW, "cumple todo lo que el aviso permite verificar"
    elif listing.is_project:
        bucket = REVIEW
        note = "proyecto con varias tipologías: confirmar precio y dormitorios de la unidad"
    else:
        bucket, note = APPROVED, ""
    return Result(listing, text, bucket, d, facts.to_dict(), violated, missing, note)


def rank(results: List[Result]) -> List[Result]:
    """Mismo orden que la solución de la E2 (comuna preferida, luego ROI; sin arriendo
    publicado al final) y, a igualdad, el más barato primero."""
    def key(r: Result):
        if not r.decision:
            return (1, 0, 0.0, 0)
        preferred, has_roi, roi = r.decision.rank_key
        return (-preferred, -has_roi, -roi, r.decision.price_clp or 0)
    return sorted(results, key=key)


def e1_output(results: List[Result]) -> Dict:
    """El JSON estricto de la E1 (approved_matches / rejected), generado por el mismo
    `build_output` de la solución, para las aprobadas y las rechazadas con dato verificado."""
    return build_output([r.decision for r in results if r.decision and r.bucket in (APPROVED, REJECTED)])
