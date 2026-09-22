"""Paso 2 de la descomposición: DECISIÓN determinista sobre los hechos extraídos.

Aquí se resuelve el "colapso lógico": cada hard constraint es una comparación
aislada en Python sobre un campo ya normalizado; no hay razonamiento condicional
cruzado que el modelo deba sostener. Las 5 reglas son la definición de la tarea
(Entregable 1, sección 1), no una heurística nueva:

  1. presupuesto:   price_clp <= presupuesto_max_clp  (UF→CLP con la UF del día)
  2. mascotas:      política explícita de aceptación, especie permitida, peso <= límite
  3. distancia:     min(metro, paradero troncal) <= distancia_max
  4. dormitorios:   dormitorios reales >= mínimo
  5. estacionamiento: propio o asignado (visitas / calle / ninguno no sirven)

Este módulo NO importa rules.py: opera sobre `Facts` (lo que el LLM leyó), nunca
sobre `truth` (lo que solo ve el juez). Si la extracción es correcta, la decisión
es correcta por construcción; si la extracción falla, el error es observable campo
a campo (extract_report.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import normalize
from .extract import Facts
from .schema import HardConstraints, SoftConstraints

C_BUDGET = "presupuesto"
C_PETS = "mascotas"
C_DISTANCE = "distancia_transporte"
C_BEDROOMS = "dormitorios"
C_PARKING = "estacionamiento"
VALID_PARKING = {"propio", "asignado"}


@dataclass
class Decision:
    id: str
    price_clp: Optional[int]
    roi_pct: Optional[float]
    failed_constraints: List[str] = field(default_factory=list)
    preferred_location: bool = False
    notes: List[str] = field(default_factory=list)   # trazabilidad de cada comparación

    @property
    def approved(self) -> bool:
        return not self.failed_constraints

    @property
    def rank_key(self) -> tuple:
        # Soft constraints de la E1: comuna preferida primero; luego ROI desc; sin arriendo al final.
        return (self.preferred_location, self.roi_pct is not None, self.roi_pct or 0.0)


def decide(prop_id: str, f: Facts, hc: HardConstraints, sc: SoftConstraints, uf_value: float) -> Decision:
    d = Decision(id=prop_id, price_clp=None, roi_pct=None)

    # 1. Presupuesto (herramienta: parseo + conversión, no el LLM)
    value, unit = normalize.parse_money(f.price_text)
    if value is None:
        d.failed_constraints.append(C_BUDGET)
        d.notes.append(f"precio ilegible: {f.price_text!r} -> se rechaza por no verificable")
    else:
        d.price_clp = normalize.to_clp(value, unit, uf_value)
        d.notes.append(f"precio {f.price_text!r} = {value:g} {unit} -> {d.price_clp:,} CLP "
                       f"{'<=' if d.price_clp <= hc.presupuesto_max_clp else '>'} {hc.presupuesto_max_clp:,}")
        if d.price_clp > hc.presupuesto_max_clp:
            d.failed_constraints.append(C_BUDGET)

    # 2. Mascotas
    pets_ok = (
        f.pets_policy == "permitidas"
        and (not f.pets_species or hc.mascota_especie in f.pets_species)
        and (f.pets_max_kg is None or hc.mascota_kg <= f.pets_max_kg)
    )
    d.notes.append(f"mascotas: politica={f.pets_policy} especies={f.pets_species or 'cualquiera'} "
                   f"max_kg={f.pets_max_kg} vs {hc.mascota_especie} {hc.mascota_kg:g}kg -> {'ok' if pets_ok else 'FALLA'}")
    if not pets_ok:
        d.failed_constraints.append(C_PETS)

    # 3. Distancia: metro O paradero troncal, la menor
    dists = [x for x in (normalize.parse_distance_m(f.distance_metro_text),
                         normalize.parse_distance_m(f.distance_bus_text)) if x is not None]
    dist = min(dists) if dists else None
    d.notes.append(f"distancia: metro={f.distance_metro_text!r} bus={f.distance_bus_text!r} -> "
                   f"min={dist} vs max {hc.distancia_max_transporte_m}")
    if dist is None or dist > hc.distancia_max_transporte_m:
        d.failed_constraints.append(C_DISTANCE)

    # 4. Dormitorios (None = la cláusula no tiene un número: no verificable, se rechaza)
    d.notes.append(f"dormitorios: {f.bedrooms if f.bedrooms is not None else 'no verificable'} "
                   f"vs min {hc.dormitorios_min}")
    if f.bedrooms is None or f.bedrooms < hc.dormitorios_min:
        d.failed_constraints.append(C_BEDROOMS)

    # 5. Estacionamiento
    d.notes.append(f"estacionamiento: {f.parking} (requerido={hc.estacionamiento_requerido})")
    if hc.estacionamiento_requerido and f.parking not in VALID_PARKING:
        d.failed_constraints.append(C_PARKING)

    # ROI (solo tiene sentido con precio válido)
    rent, _ = normalize.parse_money(f.rent_text) if f.rent_text else (None, None)
    if d.price_clp and rent is not None:
        d.roi_pct = normalize.roi_pct(int(rent), d.price_clp)

    prefs = {x.strip().casefold() for x in sc.ubicaciones_preferidas}
    d.preferred_location = bool(f.location) and f.location.strip().casefold() in prefs
    return d


def build_output(decisions: List[Decision]) -> Dict:
    """Ensambla el JSON estricto de la E1 (mismo esquema que el baseline)."""
    approved = sorted((d for d in decisions if d.approved), key=lambda d: d.rank_key, reverse=True)
    rejected = [d for d in decisions if not d.approved]
    return {
        "approved_matches": [
            {"id": d.id, "price_clp": d.price_clp, "roi_pct": d.roi_pct} for d in approved
        ],
        "rejected": [
            {"id": d.id, "failed_constraints": list(d.failed_constraints)} for d in rejected
        ],
    }
