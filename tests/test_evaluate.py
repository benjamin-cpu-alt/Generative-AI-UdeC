"""El desglose por restricción de `evaluate.py` debe contar aprobaciones indebidas con
cualquier formato de id. Antes solo reconocía `PROP-…` y reportaba 0 % en el set OOD
(`OOD-…`), aunque el baseline aprobaba propiedades fuera de presupuesto."""
import json
from pathlib import Path

from matcher.evaluate import breakdown
from matcher.rules import expected_output
from matcher.schema import Case
from matcher.verifier import verify

ROOT = Path(__file__).resolve().parents[1]


def _approve_all(case):
    exp = expected_output(case)
    return json.dumps({
        "approved_matches": [{"id": e.id, "price_clp": e.price_clp, "roi_pct": e.roi_pct}
                             for e in exp.by_id.values()],
        "rejected": [],
    })


def _check(case):
    v = verify(case, _approve_all(case))
    rows = {r["constraint"]: r for r in breakdown("x", [v], [case])}
    for r in rows.values():
        # aprobarlo todo = aprobar cada propiedad inválida: la tasa debe ser 100 %
        assert r["approved_anyway"] == r["invalid_in_test"]


def test_breakdown_ids_prop():
    _check(Case.load(ROOT / "data" / "cases" / "test" / "case_001_e1.json"))


def test_breakdown_ids_ood():
    case = Case.load(ROOT / "data" / "cases" / "ood" / "ood_002.json")
    assert case.properties[0].id.startswith("OOD-")
    _check(case)
