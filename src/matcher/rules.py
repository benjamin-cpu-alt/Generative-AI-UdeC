"""Las 5 hard constraints + ROI + ranking por soft constraints, de forma determinista.

Produce la salida esperada (ground truth) para un caso. Es la única fuente de
verdad sobre qué propiedades deben aprobarse y en qué orden: el modelo nunca la ve.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .schema import Case, Property

# Nombres canónicos de las restricciones (se usan en los reportes de fallo).
C_BUDGET = "presupuesto"
C_PETS = "mascotas"
C_DISTANCE = "distancia_transporte"
C_BEDROOMS = "dormitorios"
C_PARKING = "estacionamiento"

VALID_PARKING = {"propio", "asignado"}


@dataclass
class ExpectedProperty:
    id: str
    price_clp: int
    roi_pct: Optional[float]            # None si el texto no da arriendo
    failed_constraints: List[str] = field(default_factory=list)
    preferred_location: bool = False    # soft constraint: comuna preferida del comprador

    @property
    def approved(self) -> bool:
        return not self.failed_constraints

    @property
    def rank_key(self) -> tuple:
        """Mayor = mejor. Comuna preferida primero; luego ROI (sin arriendo = último)."""
        return (self.preferred_location, self.roi_pct is not None, self.roi_pct or 0.0)


@dataclass
class Expected:
    by_id: Dict[str, ExpectedProperty]

    @property
    def approved_ids(self) -> set:
        return {k for k, v in self.by_id.items() if v.approved}

    @property
    def rejected_ids(self) -> set:
        return {k for k, v in self.by_id.items() if not v.approved}

    @property
    def ranking(self) -> List[List[str]]:
        """Aprobadas ordenadas de mejor a peor, agrupadas en niveles de empate
        (misma preferencia y mismo ROI): dentro de un nivel cualquier orden vale."""
        approved = sorted((v for v in self.by_id.values() if v.approved),
                          key=lambda e: e.rank_key, reverse=True)
        tiers: List[List[str]] = []
        for e in approved:
            if tiers and self.by_id[tiers[-1][0]].rank_key == e.rank_key:
                tiers[-1].append(e.id)
            else:
                tiers.append([e.id])
        return tiers

    @property
    def ranked_ids(self) -> List[str]:
        return [pid for tier in self.ranking for pid in tier]


def price_in_clp(prop: Property, uf_value: float) -> int:
    t = prop.truth
    if t.price_clp is not None:
        return int(t.price_clp)
    if t.price_uf is not None:
        return int(round(t.price_uf * uf_value))
    raise ValueError(f"{prop.id}: sin precio en UF ni CLP")


def roi_pct(rent_monthly_clp: Optional[int], price_clp: int) -> Optional[float]:
    if rent_monthly_clp is None:
        return None
    return round(rent_monthly_clp * 12 / price_clp * 100, 2)


def evaluate_property(prop: Property, case: Case) -> ExpectedProperty:
    hc = case.hard_constraints
    t = prop.truth
    failed: List[str] = []

    clp = price_in_clp(prop, case.uf_value)
    if clp > hc.presupuesto_max_clp:
        failed.append(C_BUDGET)

    p = t.pets
    pets_ok = (
        p.explicit
        and p.allowed
        and (not p.species or hc.mascota_especie in p.species)
        and (p.max_kg is None or hc.mascota_kg <= p.max_kg)
    )
    if not pets_ok:
        failed.append(C_PETS)

    if t.distance_transport_m > hc.distancia_max_transporte_m:
        failed.append(C_DISTANCE)

    if t.bedrooms < hc.dormitorios_min:
        failed.append(C_BEDROOMS)

    if hc.estacionamiento_requerido and t.parking not in VALID_PARKING:
        failed.append(C_PARKING)

    return ExpectedProperty(
        id=prop.id,
        price_clp=clp,
        roi_pct=roi_pct(t.rent_monthly_clp, clp),
        failed_constraints=failed,
        preferred_location=is_preferred_location(t.location, case),
    )


def is_preferred_location(location: Optional[str], case: Case) -> bool:
    prefs = {x.strip().casefold() for x in case.soft_constraints.ubicaciones_preferidas}
    return bool(location) and location.strip().casefold() in prefs


def expected_output(case: Case) -> Expected:
    return Expected(by_id={p.id: evaluate_property(p, case) for p in case.properties})
