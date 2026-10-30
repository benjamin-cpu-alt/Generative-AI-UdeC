"""Set HARD de la E3: hard_dev (10 casos) y hard_test (30 casos), avisos escritos a mano.

El protocolo (cuotas, convenciones, reglas de uso) está en data/cases/hard_test/README.md
y se escribió antes que los casos. Este script es su auto-verificación: aborta si

  - rules.py no llega al veredicto anotado (`expect`) de alguna propiedad;
  - el aviso no nombra su comuna, o el precio no está en exactamente una unidad;
  - un caso tiene menos de 2 aprobadas o de 2 rechazadas, o el split sale del 40-55 % de
    aprobadas;
  - no se cumple alguna cuota de fenómenos (tags) o de casos (comprador sin mascota,
    estacionamiento no requerido, preferencia de comuna contra ROI);
  - una propiedad `casi_cumple` falla más de una restricción;
  - dev y test comparten un fragmento de 8 palabras seguidas;
  - hard_test/ no coincide con su MANIFEST.sha256 (una vez congelado).

Uso:
  python3 scripts/build_hard.py --check    # verifica todo, no escribe
  python3 scripts/build_hard.py            # escribe hard_dev/ (y hard_test/ si no está congelado)
  python3 scripts/build_hard.py --freeze   # escribe hard_test/ y su MANIFEST.sha256
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

from hard_common import ROOT, TAGS  # noqa: E402  (añade src/ al path)
from matcher.rules import evaluate_property, expected_output  # noqa: E402
from matcher.schema import Case, Property  # noqa: E402

import hard_cases_dev  # noqa: E402
import hard_cases_test1  # noqa: E402
import hard_cases_test2  # noqa: E402
import hard_cases_test3  # noqa: E402

SPLITS = {
    "hard_dev": {"cases": hard_cases_dev.CASES, "n_cases": 10, "props": 7, "prefix": "HD-",
                 "quota": 0},
    "hard_test": {"cases": hard_cases_test1.CASES + hard_cases_test2.CASES + hard_cases_test3.CASES,
                  "n_cases": 30, "props": 8, "prefix": "HT-", "quota": 1},
}

# Cuotas mínimas de propiedades por tag: (dev, test). Ver la tabla del protocolo.
TAG_QUOTA = {
    "jerga_monto": (3, 10), "cifra_palabras": (3, 10), "multi_monto": (3, 12),
    "arriendo_uf": (2, 6), "dorm_notacion": (3, 12), "dorm_no_cuenta": (3, 10),
    "mascota_condicion": (4, 14), "mascota_silencio": (2, 8), "estac_ambiguo": (4, 12),
    "dist_formato": (4, 12), "dist_multiple": (2, 8), "comuna_posicion": (4, 14),
    "casi_cumple": (4, 14), "distractor": (3, 10), "correccion": (2, 6), "estilo": (4, 12),
}
assert set(TAG_QUOTA) == set(TAGS)
CASE_QUOTA_TEST = {"sin_mascota": 4, "sin_estacionamiento": 4, "preferencia_vs_roi": 6}
APPROVED_RANGE = (0.40, 0.55)
UF_RANGE = (38_500, 41_500)
SHINGLE = 8
MANIFEST = ROOT / "data" / "cases" / "hard_test" / "MANIFEST.sha256"


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()


def _shingles(text: str) -> set:
    words = re.findall(r"\w+", _fold(text))
    return {" ".join(words[i:i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def to_case(spec: Dict) -> Case:
    props = [Property(id=p["id"], text=p["text"], truth=p["truth"]) for p in spec["properties"]]
    return Case(id=spec["id"], uf_value=spec["uf_value"], hard_constraints=spec["hard_constraints"],
                properties=props, soft_constraints=spec["soft_constraints"])


def payload(spec: Dict, c: Case) -> Dict:
    return {
        "id": c.id, "uf_value": c.uf_value, "style": spec["style"],
        "hard_constraints": asdict(c.hard_constraints),
        "soft_constraints": asdict(c.soft_constraints),
        "properties": [{"id": p["id"], "text": p["text"], "note": p["note"], "tags": p["tags"],
                        "truth": asdict(p["truth"])} for p in spec["properties"]],
    }


def check_split(name: str, conf: Dict, errors: List[str]) -> Tuple[Dict, List[Tuple[Dict, Case]]]:
    specs = conf["cases"]
    built = []
    tag_count = {t: 0 for t in TAGS}
    n_props = n_ok = 0
    case_quota = {"sin_mascota": 0, "sin_estacionamiento": 0, "preferencia_vs_roi": 0}
    if len(specs) != conf["n_cases"]:
        errors.append(f"{name}: {len(specs)} casos, el protocolo pide {conf['n_cases']}")
    for spec in specs:
        c = to_case(spec)
        built.append((spec, c))
        if not UF_RANGE[0] <= c.uf_value <= UF_RANGE[1]:
            errors.append(f"{c.id}: UF {c.uf_value} fuera de {UF_RANGE}")
        if len(c.properties) != conf["props"]:
            errors.append(f"{c.id}: {len(c.properties)} propiedades, se piden {conf['props']}")
        exp = expected_output(c)
        n_app = len(exp.approved_ids)
        if n_app < 2 or len(c.properties) - n_app < 2:
            errors.append(f"{c.id}: {n_app} aprobadas de {len(c.properties)} (se piden >=2 y >=2)")
        hc = c.hard_constraints
        case_quota["sin_mascota"] += hc.mascota_especie is None
        case_quota["sin_estacionamiento"] += not hc.estacionamiento_requerido
        # El ranking importa si ordenar solo por ROI pondría una aprobada NO preferida antes
        # que una preferida (que no tenga ROI cuenta como ROI más bajo).
        appr = [exp.by_id[i] for i in exp.approved_ids]
        case_quota["preferencia_vs_roi"] += any(
            b.roi_pct is not None and (a.roi_pct is None or b.roi_pct > a.roi_pct)
            for a in appr if a.preferred_location
            for b in appr if not b.preferred_location)
        for prop, p in zip(c.properties, spec["properties"]):
            n_props += 1
            if not p["id"].startswith(conf["prefix"]):
                errors.append(f"{p['id']}: el id debe empezar con {conf['prefix']}")
            got = evaluate_property(prop, c)
            if sorted(got.failed_constraints) != p["expect"]:
                errors.append(f"{c.id} {prop.id}: anotado {p['expect']} pero rules.py dice "
                              f"{got.failed_constraints} (precio {got.price_clp:,} CLP)")
            n_ok += got.approved
            t = prop.truth
            if (t.price_uf is None) == (t.price_clp is None):
                errors.append(f"{prop.id}: el precio debe estar en exactamente una unidad")
            if _fold(t.location) not in _fold(prop.text):
                errors.append(f"{prop.id}: el aviso no nombra la comuna {t.location!r}")
            if not p["note"]:
                errors.append(f"{prop.id}: falta la nota de revisión")
            if "casi_cumple" in p["tags"] and len(got.failed_constraints) > 1:
                errors.append(f"{prop.id}: casi_cumple pero falla {got.failed_constraints}")
            for tag in p["tags"]:
                tag_count[tag] += 1
    q = conf["quota"]
    for tag, mins in TAG_QUOTA.items():
        if tag_count[tag] < mins[q]:
            errors.append(f"{name}: tag {tag} en {tag_count[tag]} propiedades, cuota {mins[q]}")
    ratio = n_ok / n_props if n_props else 0
    if not APPROVED_RANGE[0] <= ratio <= APPROVED_RANGE[1]:
        errors.append(f"{name}: {n_ok}/{n_props} aprobadas ({ratio:.0%}), fuera de {APPROVED_RANGE}")
    if name == "hard_test":
        for k, v in CASE_QUOTA_TEST.items():
            if case_quota[k] < v:
                errors.append(f"{name}: {case_quota[k]} casos con {k}, cuota {v}")
    stats = {"casos": len(specs), "propiedades": n_props, "aprobadas": n_ok, "tags": tag_count,
             **case_quota}
    return stats, built


def file_hashes(dirpath: Path) -> Dict[str, str]:
    # CRLF -> LF, para que un checkout en Windows no rompa el congelamiento
    return {p.name: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in sorted(dirpath.glob("*.json"))}


def read_manifest() -> Dict[str, str]:
    if not MANIFEST.exists():
        return {}
    out = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            digest, name = line.split(maxsplit=1)
            out[name.strip()] = digest
    return out


def main(check_only: bool, freeze: bool) -> int:
    errors: List[str] = []
    results = {name: check_split(name, conf, errors) for name, conf in SPLITS.items()}

    ids = [p["id"] for conf in SPLITS.values() for s in conf["cases"] for p in s["properties"]]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"ids repetidos: {dupes}")
    dev_sh = set().union(*(_shingles(p["text"]) for s in SPLITS["hard_dev"]["cases"] for p in s["properties"]))
    for s in SPLITS["hard_test"]["cases"]:
        for p in s["properties"]:
            shared = _shingles(p["text"]) & dev_sh
            if shared:
                errors.append(f"{p['id']}: comparte con dev el fragmento {sorted(shared)[0]!r}")

    for name, (stats, _) in results.items():
        tags = ", ".join(f"{k} {v}" for k, v in stats["tags"].items())
        print(f"{name}: {stats['casos']} casos, {stats['propiedades']} propiedades, "
              f"{stats['aprobadas']} aprobadas ({100 * stats['aprobadas'] / max(1, stats['propiedades']):.0f} %); "
              f"sin mascota {stats['sin_mascota']}, sin estacionamiento {stats['sin_estacionamiento']}, "
              f"preferencia vs ROI {stats['preferencia_vs_roi']}\n  tags: {tags}")

    manifest = read_manifest()
    test_dir = ROOT / "data" / "cases" / "hard_test"
    if manifest and not freeze:
        current = file_hashes(test_dir)
        if current != manifest:
            changed = sorted(set(current.items()) ^ set(manifest.items()))
            errors.append(f"hard_test/ no coincide con MANIFEST.sha256: {changed[:3]}")
        # lo que se escribiría hoy debe ser idéntico a lo congelado
        for spec, c in results["hard_test"][1]:
            text = json.dumps(payload(spec, c), ensure_ascii=False, indent=2) + "\n"
            if manifest.get(f"{c.id}.json") != hashlib.sha256(text.encode("utf-8")).hexdigest():
                errors.append(f"{c.id}: la fuente cambió después de congelar hard_test")

    if errors:
        print("\nPROBLEMAS:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 1
    print("OK: anotación == rules.py, cuotas cumplidas, sin solapamiento dev/test.")
    if check_only:
        return 0

    for name, (_, built) in results.items():
        if name == "hard_test" and manifest and not freeze:
            print("hard_test/ está congelado: no se reescribe (usa --freeze para re-congelar)")
            continue
        out = ROOT / "data" / "cases" / name
        out.mkdir(parents=True, exist_ok=True)
        for spec, c in built:
            (out / f"{c.id}.json").write_text(
                json.dumps(payload(spec, c), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"escritos {len(built)} casos en data/cases/{name}/")
    if freeze:
        lines = ["# sha256 de cada caso de hard_test/. Generado por scripts/build_hard.py --freeze.",
                 "# Si un archivo cambia, tests/test_e3_benchmark.py falla."]
        lines += [f"{d}  {n}" for n, d in file_hashes(test_dir).items()]
        MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"congelado: {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verifica sin escribir")
    ap.add_argument("--freeze", action="store_true", help="escribe hard_test/ y su manifiesto")
    a = ap.parse_args()
    sys.exit(main(a.check, a.freeze))
