import json
from pathlib import Path

import pytest

from matcher.rules import expected_output
from matcher.schema import Case
from matcher.verifier import verify

ROOT = Path(__file__).resolve().parents[1]
CASE = Case.load(ROOT / "data" / "cases" / "case_001_e1.json")

PERFECT = {
    "approved_matches": [
        {"id": "PROP-F61", "price_clp": 145040000, "roi_pct": 7.61},
        {"id": "PROP-G77", "price_clp": 142000000, "roi_pct": 7.44},
    ],
    "rejected": [
        {"id": "PROP-A42", "failed_constraints": ["presupuesto"]},
        {"id": "PROP-B19", "failed_constraints": ["distancia_transporte"]},
        {"id": "PROP-C88", "failed_constraints": ["estacionamiento"]},
        {"id": "PROP-D05", "failed_constraints": ["dormitorios", "mascotas"]},
        {"id": "PROP-E33", "failed_constraints": ["mascotas"]},
        {"id": "PROP-H12", "failed_constraints": ["presupuesto"]},
    ],
}


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)


# ------------------------------------------------------------- ground truth

def test_expected_output_e1_case():
    exp = expected_output(CASE)
    assert exp.approved_ids == {"PROP-F61", "PROP-G77"}
    assert exp.rejected_ids == {"PROP-A42", "PROP-B19", "PROP-C88", "PROP-D05", "PROP-E33", "PROP-H12"}

    assert exp.by_id["PROP-A42"].price_clp == 150920000
    assert exp.by_id["PROP-A42"].failed_constraints == ["presupuesto"]
    assert exp.by_id["PROP-B19"].failed_constraints == ["distancia_transporte"]
    assert exp.by_id["PROP-C88"].failed_constraints == ["estacionamiento"]
    assert exp.by_id["PROP-D05"].failed_constraints == ["mascotas", "dormitorios"]
    assert exp.by_id["PROP-E33"].failed_constraints == ["mascotas"]
    assert exp.by_id["PROP-H12"].failed_constraints == ["presupuesto"]

    assert exp.by_id["PROP-F61"].price_clp == 145040000
    assert exp.by_id["PROP-F61"].roi_pct == pytest.approx(7.61, abs=0.01)
    assert exp.by_id["PROP-G77"].roi_pct == pytest.approx(7.44, abs=0.01)


# ------------------------------------------------------------- respuestas OK

def test_perfect_response_is_correct():
    v = verify(CASE, dumps(PERFECT))
    assert v.e1_correct and v.exact_match and v.reason == "ok"


def test_accepts_prompt_base_roi_key_name():
    obj = json.loads(dumps(PERFECT))
    for a in obj["approved_matches"]:
        a["roi_calculado_pct"] = a.pop("roi_pct")
        a["distance_to_transport_m"] = 0            # campos extra se ignoran
        a["ranking_score_justificacion"] = "..."
    v = verify(CASE, dumps(obj))
    assert v.e1_correct and v.reason == "ok"


def test_reject_everything_passes_e1_but_not_exact_match():
    """El hueco del criterio E1 que motiva la métrica secundaria."""
    obj = {"approved_matches": [], "rejected": [{"id": p.id, "failed_constraints": ["x"]} for p in CASE.properties]}
    v = verify(CASE, dumps(obj))
    assert v.e1_correct is True
    assert v.exact_match is False
    assert any("rechazo falso" in d for d in v.details)


# --------------------------------------------------------- condición 1: lógica

def test_granite_log_false_approval_of_a42():
    """Reproduce el fallo de Granite en el log de la E1: aprueba A42 (excede presupuesto)."""
    obj = json.loads(dumps(PERFECT))
    obj["approved_matches"].append({"id": "PROP-A42", "price_clp": 150920000, "roi_pct": 7.79})
    obj["rejected"] = [r for r in obj["rejected"] if r["id"] != "PROP-A42"]
    v = verify(CASE, dumps(obj))
    assert not v.e1_correct and v.reason == "false_approval"
    assert "PROP-A42" in v.details[0]


def test_phi4_log_approves_c88_visitor_parking():
    obj = json.loads(dumps(PERFECT))
    obj["approved_matches"].append({"id": "PROP-C88", "price_clp": 137200000, "roi_pct": None})
    obj["rejected"] = [r for r in obj["rejected"] if r["id"] != "PROP-C88"]
    v = verify(CASE, dumps(obj))
    assert v.reason == "false_approval"


# ------------------------------------------------------ condición 2: aritmética

def test_wrong_uf_conversion_is_arithmetic_error():
    obj = json.loads(dumps(PERFECT))
    obj["approved_matches"][0]["price_clp"] = 145000000      # 3.700 UF mal convertido
    v = verify(CASE, dumps(obj))
    assert not v.e1_correct and v.reason == "arithmetic_error"


def test_wrong_roi_is_arithmetic_error():
    obj = json.loads(dumps(PERFECT))
    obj["approved_matches"][1]["roi_pct"] = 0.0744            # fracción en vez de porcentaje
    v = verify(CASE, dumps(obj))
    assert v.reason == "arithmetic_error"


def test_roi_within_tolerance():
    obj = json.loads(dumps(PERFECT))
    obj["approved_matches"][0]["roi_pct"] = 7.6               # 7.61 ± 0.05
    v = verify(CASE, dumps(obj))
    assert v.e1_correct


def test_false_approval_takes_precedence_over_arithmetic():
    obj = json.loads(dumps(PERFECT))
    obj["approved_matches"][0]["price_clp"] = 1
    obj["approved_matches"].append({"id": "PROP-H12", "price_clp": 151000000, "roi_pct": None})
    obj["rejected"] = [r for r in obj["rejected"] if r["id"] != "PROP-H12"]
    v = verify(CASE, dumps(obj))
    assert v.reason == "false_approval"


# ---------------------------------------------------------- condición 3: esquema

@pytest.mark.parametrize("raw, fragment", [
    ("```json\n" + dumps(PERFECT) + "\n```", "fences markdown"),
    ("Claro, aquí está el resultado:\n" + dumps(PERFECT), "texto conversacional"),
    ("<think>\nvoy a evaluar...\n</think>\n" + dumps(PERFECT), "<think>"),
    ("", "vacía"),
    ("{no es json}", "malformado"),
    ("[]", "no es un objeto"),
])
def test_schema_errors_from_wrapping(raw, fragment):
    v = verify(CASE, raw)
    assert not v.e1_correct and v.reason == "schema_error"
    assert fragment in v.details[0]


def test_missing_keys_is_schema_error():
    v = verify(CASE, dumps({"approved_matches": []}))
    assert v.reason == "schema_error" and "rejected" in v.details[0]


def test_missing_price_is_schema_error():
    obj = json.loads(dumps(PERFECT))
    del obj["approved_matches"][0]["price_clp"]
    v = verify(CASE, dumps(obj))
    assert v.reason == "schema_error" and "price_clp" in v.details[0]


def test_unknown_id_is_schema_error():
    obj = json.loads(dumps(PERFECT))
    obj["rejected"].append({"id": "PROP-Z99", "failed_constraints": ["x"]})
    v = verify(CASE, dumps(obj))
    assert v.reason == "schema_error" and "PROP-Z99" in v.details[0]


def test_id_in_both_lists_is_schema_error():
    obj = json.loads(dumps(PERFECT))
    obj["rejected"].append({"id": "PROP-F61", "failed_constraints": ["x"]})
    v = verify(CASE, dumps(obj))
    assert v.reason == "schema_error" and "repetidos" in v.details[0]
