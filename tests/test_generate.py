import json
import random
from pathlib import Path

from matcher.generate import gen_case
from matcher.prompt import render_prompt
from matcher.rules import expected_output
from matcher.schema import Case
from matcher.verifier import verify

ROOT = Path(__file__).resolve().parents[1]


def oracle_response(case: Case) -> str:
    """Respuesta perfecta construida desde rules.py (lo que un modelo ideal diría)."""
    exp = expected_output(case)
    return json.dumps({
        "approved_matches": [
            {"id": pid, "price_clp": e.price_clp, "roi_pct": e.roi_pct}
            for pid, e in exp.by_id.items() if e.approved
        ],
        "rejected": [
            {"id": pid, "failed_constraints": e.failed_constraints}
            for pid, e in exp.by_id.items() if not e.approved
        ],
    }, ensure_ascii=False)


def test_generated_cases_round_trip():
    """Todo caso en data/cases debe ser resoluble: el oráculo obtiene 1 en ambas métricas."""
    paths = sorted((ROOT / "data" / "cases").glob("*/*.json"))
    assert len(paths) >= 351          # 300 train + 50 test + case_001_e1
    for p in paths:
        case = Case.load(p)
        v = verify(case, oracle_response(case))
        assert v.e1_correct and v.exact_match, (p.name, v.details)


def test_generated_case_matches_declared_scenarios():
    for p in sorted((ROOT / "data" / "cases" / "test").glob("test_*.json"))[:10]:
        d = json.loads(p.read_text(encoding="utf-8"))
        exp = expected_output(Case.from_dict(d))
        for prop in d["properties"]:
            assert exp.by_id[prop["id"]].approved == (prop["scenario"] == "pass"), (p.name, prop["id"])


def test_generation_is_deterministic():
    a, _ = gen_case(random.Random(7), "x")
    b, _ = gen_case(random.Random(7), "x")
    assert [p.text for p in a.properties] == [p.text for p in b.properties]


def test_prompt_contains_everything_the_model_needs():
    case = Case.load(ROOT / "data" / "cases" / "test" / "case_001_e1.json")
    prompt = render_prompt(case)
    assert "VALOR UF HOY: $39.200 CLP" in prompt
    assert "$150.000.000 CLP" in prompt
    assert "1 perro de 18kg" in prompt
    for p in case.properties:
        assert f"[{p.id}]" in prompt and p.text in prompt
    assert '"roi_pct"' in prompt and '"failed_constraints"' in prompt
    # el prompt nunca filtra la verdad estructurada
    assert "truth" not in prompt and "scenario" not in prompt


def test_saved_prompt_file_is_in_sync():
    """data/prompt_e2_case_001.txt es el prompt real; si cambia prompt.py hay que regenerarlo."""
    case = Case.load(ROOT / "data" / "cases" / "test" / "case_001_e1.json")
    saved = (ROOT / "data" / "prompt_e2_case_001.txt").read_text(encoding="utf-8")
    assert saved.strip() == render_prompt(case).strip()


def test_prompt_has_explicit_format_rule():
    case = Case.load(ROOT / "data" / "cases" / "test" / "case_001_e1.json")
    assert "empezar con el carácter {" in render_prompt(case)
