"""Tests de las herramientas deterministas de la solución E2 (sin Ollama).

Garantizan que, con hechos correctamente extraídos, la decisión coincide con el
ground truth de rules.py en TODOS los casos del split test. Es decir: cualquier
fallo de la solución sobre test/ se origina en la extracción, nunca en las reglas.
"""
import json
from pathlib import Path

import pytest

from matcher import normalize
from matcher.constraints import build_output, decide
from matcher.extract import Facts
from matcher.rules import expected_output
from matcher.schema import Case
from matcher.verifier import verify

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted((ROOT / "data" / "cases" / "test").glob("*.json"))


@pytest.mark.parametrize("text,expected", [
    ("3.850 UF", (3850, "UF")), ("UF 4.183", (4183, "UF")), ("4698 UF", (4698, "UF")),
    ("$148.500.000", (148500000, "CLP")), ("$980.000/mes", (980000, "CLP")),
    ("Precio rebajado a 3.850 UF", (3850, "UF")), ("", (None, None)), (None, (None, None)),
])
def test_parse_money(text, expected):
    assert normalize.parse_money(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("950m", 950), ("1,4 km", 1400), ("1,2km", 1200), ("a 300m del metro", 300),
    ("unos 15 minutos caminando", None), (None, None),
])
def test_parse_distance(text, expected):
    assert normalize.parse_distance_m(text) == expected


def test_uf_conversion_and_roi_match_e1():
    assert normalize.to_clp(3850, "UF", 39200) == 150_920_000       # PROP-A42: sobre 150 M
    assert normalize.roi_pct(920000, normalize.to_clp(3700, "UF", 39200)) == 7.61  # PROP-F61


def facts_from_truth(p) -> Facts:
    """Extracción 'perfecta': lo que el LLM debería devolver si leyera bien."""
    t = p.truth
    price_text = f"{t.price_uf:,} UF".replace(",", ".") if t.price_uf is not None else f"${t.price_clp:,}".replace(",", ".")
    rent_text = None if t.rent_monthly_clp is None else f"${t.rent_monthly_clp:,}/mes".replace(",", ".")
    return Facts(
        location=t.location, bedrooms=t.bedrooms, price_text=price_text, rent_text=rent_text,
        distance_metro_text=f"{t.distance_transport_m}m", distance_bus_text=None,
        pets_policy=("permitidas" if t.pets.explicit and t.pets.allowed
                     else "no_permitidas" if t.pets.explicit else "no_mencionada"),
        pets_species=list(t.pets.species), pets_max_kg=t.pets.max_kg, parking=t.parking,
    )


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_perfect_extraction_gives_full_correct(path):
    case = Case.load(path)
    decisions = [decide(p.id, facts_from_truth(p), case.hard_constraints, case.soft_constraints, case.uf_value)
                 for p in case.properties]
    out = json.dumps(build_output(decisions), ensure_ascii=False)
    v = verify(case, out, expected_output(case))
    assert v.full_correct, v.details


def test_unreadable_price_is_rejected_not_approved():
    case = Case.load(ROOT / "data" / "cases" / "test" / "case_001_e1.json")
    p = case.properties[0]
    f = facts_from_truth(p)
    f.price_text = "consultar"
    d = decide(p.id, f, case.hard_constraints, case.soft_constraints, case.uf_value)
    assert "presupuesto" in d.failed_constraints and d.price_clp is None
