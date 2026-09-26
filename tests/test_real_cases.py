"""El set REAL (avisos de portales, anotados a mano) debe seguir siendo coherente:
la anotación coincide con rules.py, y el texto de cada caso es exactamente la ficha de
la instantánea versionada (lo que se sorteó es lo que se evalúa)."""
import importlib.util
import json
from pathlib import Path

from matcher.rules import expected_output
from matcher.schema import Case

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "cases" / "real"


def _build_module():
    spec = importlib.util.spec_from_file_location("build_real", ROOT / "scripts" / "build_real.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_anotacion_coincide_con_rules():
    assert _build_module().build(check_only=True) == 0


def test_casos_son_la_instantanea_sorteada():
    muestra = json.loads((REAL / "fuente" / "muestra.json").read_text(encoding="utf-8"))
    fichas = {f"REAL-{i:02d}": a["ficha"] for i, a in enumerate(muestra["avisos"], 1)}
    assert len(fichas) == 16 and muestra["semilla"] == 2026
    seen = set()
    for path in sorted(REAL.glob("real_*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        case = Case.load(path)
        assert case.hard_constraints.presupuesto_max_clp == 150_000_000   # comprador de la E1
        for p, rp in zip(case.properties, raw["properties"]):
            assert p.text == fichas[p.id] and rp["fuente"].startswith("https://")
            seen.add(p.id)
        # un aviso de cada portal por caso
        assert len({rp["portal"] for rp in raw["properties"]}) == 4
    assert seen == set(fichas)


def test_caso_de_fallo_real_separado_del_sorteo():
    case = Case.load(ROOT / "data" / "cases" / "real_fallo" / "fallo_001.json")
    exp = expected_output(case)
    assert exp.approved_ids == set()
    assert sorted(exp.by_id["REAL-F1"].failed_constraints) == ["estacionamiento", "mascotas"]
    assert not (REAL / "fallo_001.json").exists()
