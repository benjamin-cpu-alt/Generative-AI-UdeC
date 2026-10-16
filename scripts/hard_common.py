"""Atajos compartidos por los avisos del set HARD (hard_cases_dev.py, hard_cases_test.py).

Mismo formato que `build_ood.py`: cada propiedad lleva su `truth`, la lista `expect` de
restricciones que deben fallar (el constructor la contrasta con rules.py), una `note` para
revisión humana y los `tags` de fenómenos del protocolo (data/cases/hard_test/README.md).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from matcher.schema import HardConstraints, PetsPolicy, SoftConstraints, Truth  # noqa: E402

TAGS = (
    "jerga_monto", "cifra_palabras", "multi_monto", "arriendo_uf", "dorm_notacion",
    "dorm_no_cuenta", "mascota_condicion", "mascota_silencio", "estac_ambiguo", "dist_formato",
    "dist_multiple", "comuna_posicion", "casi_cumple", "distractor", "correccion", "estilo",
)

B, M, D, R, E = "presupuesto", "mascotas", "distancia_transporte", "dormitorios", "estacionamiento"

ANY = PetsPolicy(explicit=True, allowed=True, species=[], max_kg=None)
NONE_ = PetsPolicy(explicit=False, allowed=False, species=[], max_kg=None)   # no se menciona
NO = PetsPolicy(explicit=True, allowed=False, species=[], max_kg=None)       # no se aceptan


def kg(n: float) -> PetsPolicy:
    return PetsPolicy(explicit=True, allowed=True, species=[], max_kg=n)


def only(species: str, max_kg: Optional[float] = None) -> PetsPolicy:
    return PetsPolicy(explicit=True, allowed=True, species=[species], max_kg=max_kg)


def both(max_kg: Optional[float] = None) -> PetsPolicy:
    return PetsPolicy(explicit=True, allowed=True, species=["perro", "gato"], max_kg=max_kg)


def hc(presupuesto: int, especie: Optional[str], mascota_kg: Optional[float], distancia: int,
       dormitorios: int, estacionamiento: bool = True) -> HardConstraints:
    """especie=None: comprador sin mascota (la restricción de mascotas siempre se cumple)."""
    return HardConstraints(presupuesto_max_clp=presupuesto, mascota_especie=especie,
                           mascota_kg=mascota_kg, distancia_max_transporte_m=distancia,
                           dormitorios_min=dormitorios, estacionamiento_requerido=estacionamiento)


def P(pid: str, text: str, *, tags: List[str], note: str, expect: List[str], loc: str,
      beds: int, dist: Optional[int], pets: PetsPolicy, parking: str,
      uf: Optional[float] = None, clp: Optional[int] = None, rent: Optional[int] = None) -> Dict:
    bad = [t for t in tags if t not in TAGS]
    if bad:
        raise ValueError(f"{pid}: tags desconocidos {bad}")
    return {
        "id": pid, "text": " ".join(text.split()), "note": note, "expect": sorted(expect),
        "tags": sorted(tags),
        "truth": Truth(bedrooms=beds, distance_transport_m=dist, pets=pets, parking=parking,
                       price_uf=uf, price_clp=clp, rent_monthly_clp=rent, location=loc),
    }


def case(cid: str, uf_value: float, hard: HardConstraints, prefs: List[str],
         style: str, props: List[Dict]) -> Dict:
    return {"id": cid, "uf_value": uf_value, "hard_constraints": hard,
            "soft_constraints": SoftConstraints(ubicaciones_preferidas=prefs),
            "style": style, "properties": props}


def rent_uf(uf_rent: float, uf_value: float) -> int:
    """Arriendo publicado en UF -> CLP con la UF del caso (convención del protocolo)."""
    return int(round(uf_rent * uf_value))
