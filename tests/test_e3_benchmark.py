"""Benchmark de la E3: sets hard_*, comprador sin mascota y piso "rechazar todo".

- hard_test/ está congelado: si un JSON cambia sin re-congelar (y sin registrarlo en
  REVIEW.md), toda cifra reportada sobre él deja de ser comparable.
- La anotación debe seguir coincidiendo con rules.py (misma auto-verificación que
  scripts/build_hard.py, aplicada a los JSON ya escritos).
- El comprador sin mascota (mascota_especie=None) no cambia ninguna verdad previa.
"""
import glob
import hashlib
import json
import unicodedata
from pathlib import Path

import pytest

from matcher.constraints import decide
from matcher.extract import Facts
from matcher.metrics import wilson
from matcher.prompt import render_profile
from matcher.reference import reject_all_output
from matcher.rules import evaluate_property, expected_output
from matcher.schema import Case, HardConstraints, PetsPolicy, Property, SoftConstraints, Truth
from matcher.verifier import verify

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "cases"
HARD = {s: sorted(glob.glob(str(CASES / s / "*.json"))) for s in ("hard_dev", "hard_test")}
ALL_HARD = HARD["hard_dev"] + HARD["hard_test"]


def _fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()


def test_tamano_de_los_sets():
    assert len(HARD["hard_dev"]) == 10
    assert len(HARD["hard_test"]) == 30


def test_hard_test_coincide_con_el_manifiesto():
    manifest = {}
    for line in (CASES / "hard_test" / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            digest, name = line.split(maxsplit=1)
            manifest[name] = digest
    # CRLF -> LF: en Windows git puede extraer los JSON con CRLF; el manifiesto se calculó sobre LF
    current = {Path(p).name: hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
               for p in HARD["hard_test"]}
    assert current == manifest, "hard_test/ cambió: re-congelar con build_hard.py --freeze y registrarlo en REVIEW.md"


@pytest.mark.parametrize("path", ALL_HARD, ids=[Path(p).stem for p in ALL_HARD])
def test_caso_hard_es_coherente(path):
    case = Case.load(path)
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    exp = expected_output(case)
    assert len(exp.approved_ids) >= 2 and len(exp.rejected_ids) >= 2
    for prop, rawp in zip(case.properties, raw["properties"]):
        t = prop.truth
        assert (t.price_uf is None) != (t.price_clp is None), f"{prop.id}: precio ambiguo"
        assert _fold(t.location) in _fold(prop.text), f"{prop.id}: el aviso no nombra {t.location}"
        assert rawp.get("note"), f"{prop.id}: falta la nota de revisión"
        assert isinstance(rawp.get("tags"), list)


def test_hard_test_tiene_aprobaciones_suficientes():
    """Si casi todo debe rechazarse, rechazar todo vuelve a saturar el criterio."""
    total = approved = 0
    for path in HARD["hard_test"]:
        for e in expected_output(Case.load(path)).by_id.values():
            total += 1
            approved += e.approved
    assert total == 240
    assert 0.40 <= approved / total <= 0.55


def test_dev_y_test_no_comparten_avisos():
    texts = lambda s: {p["text"] for f in HARD[s] for p in json.loads(Path(f).read_text(encoding="utf-8"))["properties"]}
    assert not texts("hard_dev") & texts("hard_test")


# ------------------------------------------------------ comprador sin mascota --

HC_SIN = HardConstraints(presupuesto_max_clp=150_000_000, mascota_especie=None, mascota_kg=None,
                         distancia_max_transporte_m=1000, dormitorios_min=2,
                         estacionamiento_requerido=True)


def _case(hc, pets):
    t = Truth(bedrooms=2, distance_transport_m=500, pets=pets, parking="propio", price_clp=120_000_000,
              location="Ñuñoa")
    return Case(id="x", uf_value=39_000, hard_constraints=hc,
                properties=[Property(id="P-1", text="Ñuñoa", truth=t)], soft_constraints=SoftConstraints())


@pytest.mark.parametrize("pets", [
    PetsPolicy(explicit=False),
    PetsPolicy(explicit=True, allowed=False),
    PetsPolicy(explicit=True, allowed=True, species=["gato"], max_kg=3),
])
def test_sin_mascota_cumple_cualquier_politica(pets):
    c = _case(HC_SIN, pets)
    assert evaluate_property(c.properties[0], c).approved


def test_sin_mascota_en_el_decisor_y_el_prompt():
    f = Facts(location="Ñuñoa", bedrooms=2, price_text="$120.000.000", rent_text=None,
              distance_metro_text="500 m", distance_bus_text=None, pets_policy="no_permitidas",
              pets_species=[], pets_max_kg=None, parking="propio")
    d = decide("P-1", f, HC_SIN, SoftConstraints(), 39_000)
    assert "mascotas" not in d.failed_constraints
    assert "No tiene mascota" in render_profile(_case(HC_SIN, PetsPolicy(explicit=False)))


def test_con_mascota_sin_politica_no_descarta_pero_baja():
    """Convención E3: sin política declarada no se descarta; una prohibición sí."""
    hc = HardConstraints(**{**HC_SIN.__dict__, "mascota_especie": "perro", "mascota_kg": 10})
    e = evaluate_property(_case(hc, PetsPolicy(explicit=False)).properties[0], _case(hc, PetsPolicy(explicit=False)))
    assert "mascotas" not in e.failed_constraints and not e.pets_confirmed
    c = _case(hc, PetsPolicy(explicit=True, allowed=False))
    assert "mascotas" in evaluate_property(c.properties[0], c).failed_constraints


# --------------------------------------------------------- piso del criterio --

def test_rechazar_todo_satura_e1_strict_pero_no_full_correct():
    cases = [Case.load(p) for p in sorted(glob.glob(str(CASES / "test" / "*.json")))]
    vs = [verify(c, reject_all_output(c)) for c in cases]
    assert all(v.e1_correct for v in vs)              # 51/51: el criterio E1 no lo distingue
    assert sum(v.full_correct for v in vs) < 10       # pero casi nunca es la salida correcta


def test_wilson():
    lo, hi = wilson(51, 51)
    assert hi == pytest.approx(1.0) and 0.92 < lo < 0.94
    assert wilson(0, 0) == (0.0, 0.0)


# ------------------------------------------------------------ set real E3 --

REAL_E3 = sorted(glob.glob(str(CASES / "real_e3" / "*.json")))


def test_real_e3_dos_compradores_y_mismos_avisos():
    assert len(REAL_E3) == 20
    b1 = [Case.load(p) for p in REAL_E3 if "real_b1_" in p]
    b2 = [Case.load(p) for p in REAL_E3 if "real_b2_" in p]
    assert len(b1) == len(b2) == 10
    assert all(c.hard_constraints.mascota_especie is None for c in b2)
    ids = lambda cs: sorted(p.id for c in cs for p in c.properties)
    assert ids(b1) == ids(b2) and len(ids(b1)) == 40


def test_real_e3_aprobaciones_preregistradas():
    """Cifras de PREREGISTRO_E3.md: si la adjudicación cambia, este test lo delata."""
    n = {b: sum(len(expected_output(Case.load(p)).approved_ids) for p in REAL_E3 if f"real_{b}_" in p)
         for b in ("b1", "b2")}
    assert n == {"b1": 2, "b2": 3}   # b1: 0 -> 2 por la convención E3 de mascotas (enmienda del 29-oct)
