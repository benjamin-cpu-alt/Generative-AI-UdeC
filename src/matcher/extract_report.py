"""Lectura de límites: compara los HECHOS que extrajo el LLM con el `truth` de cada
propiedad, campo por campo. Es la evidencia de *por qué* falla la solución cuando
falla: como la decisión es determinista, todo error final se origina en un campo
mal extraído, y aquí se ve cuál y con qué frecuencia.

Uso:
  python -m matcher.extract_report --run tools_phi4            # tabla por campo
  python -m matcher.extract_report --run tools_phi4 --show     # lista cada discrepancia
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import normalize
from .schema import Case, Truth

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases" / "test"
RESULTS_DIR = ROOT / "results"

FIELDS = ["price_clp", "rent_clp", "distance_m", "bedrooms", "pets_allowed", "pets_species",
          "pets_max_kg", "parking_valid", "location"]


def facts_view(f: Dict, uf: float) -> Dict:
    """Proyecta los hechos extraídos al mismo espacio que `truth` para poder compararlos."""
    v, u = normalize.parse_money(f.get("price_text"))
    rent, _ = normalize.parse_money(f.get("rent_text")) if f.get("rent_text") else (None, None)
    dists = [x for x in (normalize.parse_distance_m(f.get("distance_metro_text")),
                         normalize.parse_distance_m(f.get("distance_bus_text"))) if x is not None]
    return {
        "price_clp": normalize.to_clp(v, u, uf) if v is not None else None,
        "rent_clp": int(rent) if rent is not None else None,
        "distance_m": min(dists) if dists else None,
        "bedrooms": f.get("bedrooms"),
        "pets_allowed": f.get("pets_policy") == "permitidas",
        "pets_species": sorted(f.get("pets_species") or []),
        "pets_max_kg": f.get("pets_max_kg"),
        "parking_valid": f.get("parking") in ("propio", "asignado"),
        "location": (f.get("location") or "").strip().casefold(),
    }


def truth_view(t: Truth, uf: float) -> Dict:
    price = int(t.price_clp) if t.price_clp is not None else int(round(t.price_uf * uf))
    return {
        "price_clp": price,
        "rent_clp": t.rent_monthly_clp,
        "distance_m": t.distance_transport_m,
        "bedrooms": t.bedrooms,
        "pets_allowed": t.pets.explicit and t.pets.allowed,
        "pets_species": sorted(t.pets.species),
        "pets_max_kg": t.pets.max_kg,
        "parking_valid": t.parking in ("propio", "asignado"),
        "location": (t.location or "").strip().casefold(),
    }


def _same(field: str, a, b) -> bool:
    if field == "pets_species":
        # [] = cualquiera; ["perro","gato"] también cubre a cualquier comprador de la tarea.
        norm = lambda s: [] if set(s) >= {"perro", "gato"} else list(s)
        return norm(a) == norm(b)
    if field == "price_clp" and a is not None and b is not None:
        return abs(a - b) <= 1
    return a == b


def compare_run(run: str, cases: List[Case], results_dir: Path = RESULTS_DIR
                ) -> Tuple[Counter, Counter, List[str]]:
    total, wrong, lines = Counter(), Counter(), []
    for case in cases:
        p = results_dir / run / f"{case.id}.trace.json"
        if not p.exists():
            continue
        facts = json.loads(p.read_text(encoding="utf-8"))["facts"]
        for prop in case.properties:
            f = facts.get(prop.id)
            if not f:
                continue
            fv, tv = facts_view(f, case.uf_value), truth_view(prop.truth, case.uf_value)
            for k in FIELDS:
                total[k] += 1
                if not _same(k, fv[k], tv[k]):
                    wrong[k] += 1
                    lines.append(f"{case.id} {prop.id} {k}: extraído={fv[k]!r} verdad={tv[k]!r}"
                                 f"  | texto: {prop.text[:140]}…")
    return total, wrong, lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--show", action="store_true", help="imprime cada discrepancia")
    ap.add_argument("--cases", default=str(CASES_DIR), help="carpeta de casos (test por defecto; train para iterar)")
    a = ap.parse_args(argv)
    cases = [Case.load(p) for p in sorted(Path(a.cases).glob("*.json"))]
    total, wrong, lines = compare_run(a.run, cases)
    if not total:
        print(f"no hay .trace.json en results/{a.run}/", file=sys.stderr)
        return 1
    print(f"== Errores de extracción por campo ({a.run}) ==")
    print(f"{'campo':<14}{'propiedades':>12}{'errores':>9}{'tasa':>8}")
    for k in FIELDS:
        print(f"{k:<14}{total[k]:>12}{wrong[k]:>9}{100 * wrong[k] / total[k]:>7.1f}%")
    if a.show:
        print()
        for ln in lines:
            print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
