"""El set OOD escrito a mano debe mantenerse consistente con `rules.py`.

Si alguien edita un aviso (p.ej. cambia un precio) sin actualizar su `truth`, el ground
truth del set queda mal y todas las cifras que se reporten sobre él son inválidas. Este
test corre la misma auto-verificación que `scripts/build_ood.py` sobre los JSON ya escritos.
"""
import glob
import json
import unicodedata
from pathlib import Path

import pytest

from matcher.rules import expected_output
from matcher.schema import Case

ROOT = Path(__file__).resolve().parents[1]
PATHS = sorted(glob.glob(str(ROOT / "data" / "cases" / "ood" / "*.json")))


def _norm(s):
    return unicodedata.normalize("NFC", s or "").casefold()


def test_hay_casos_ood():
    assert len(PATHS) == 12


@pytest.mark.parametrize("path", PATHS, ids=[Path(p).stem for p in PATHS])
def test_caso_ood_es_coherente(path):
    case = Case.load(path)
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    exp = expected_output(case)
    assert len(case.properties) >= 5
    for prop, rawp in zip(case.properties, raw["properties"]):
        t = prop.truth
        # el precio existe en exactamente una unidad
        assert (t.price_uf is None) != (t.price_clp is None), f"{prop.id}: precio ambiguo"
        # la comuna del truth tiene que estar en el aviso: si no, el ranking es incontestable
        assert _norm(t.location) in _norm(prop.text), f"{prop.id}: el aviso no nombra {t.location}"
        # el veredicto del juez es computable y determinista
        assert prop.id in exp.by_id
        assert rawp.get("note"), f"{prop.id}: falta la nota de revisión"


def test_el_set_ejercita_las_cinco_restricciones():
    """Un set donde todo falla por lo mismo no prueba nada."""
    counts = {}
    total = approved = 0
    for path in PATHS:
        for e in expected_output(Case.load(path)).by_id.values():
            total += 1
            approved += e.approved
            for k in e.failed_constraints:
                counts[k] = counts.get(k, 0) + 1
    assert total == 70
    assert set(counts) == {"presupuesto", "mascotas", "distancia_transporte",
                           "dormitorios", "estacionamiento"}
    assert all(v >= 5 for v in counts.values()), counts
    assert 0.2 <= approved / total <= 0.45, f"{approved}/{total} aprobadas"


def test_hay_distancias_no_publicadas():
    """El caso más común de un aviso real: 'a 10 minutos del metro', sin metros."""
    sin_dist = [p.id for path in PATHS for p in Case.load(path).properties
                if p.truth.distance_transport_m is None]
    assert len(sin_dist) >= 2, sin_dist
