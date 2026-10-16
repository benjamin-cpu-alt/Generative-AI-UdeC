"""Anotación humana doble del set real de la E3 (protocolo: data/cases/real/PREREGISTRO_E3.md).

  python3 scripts/real_annotation.py sheets      # hojas en blanco, una por anotador
  python3 scripts/real_annotation.py agreement   # acuerdo y kappa de Cohen por campo
  python3 scripts/real_annotation.py build       # real_e3/ desde anotacion/adjudicada.csv

Las hojas son CSV con ';' (se abren directo en Excel o Google Sheets en español). Los 40
avisos son los 16 del sorteo 1 (fuente/muestra.json) y los 24 del sorteo 2
(fuente/muestra_2.json). Cada anotador llena SOLO su hoja, sin mirar la del otro ni
scripts/build_real.py (la anotación previa de Claude del sorteo 1).

Columnas a llenar (convenciones de data/cases/hard_test/README.md):
  dormitorios          entero (estudio = 0)
  distancia_m          entero en metros, o NV si la ficha no trae una distancia verificable
  mascotas             no_menciona | permite | prohibe
  mascotas_especies    perro | gato | perro+gato | (vacío = cualquiera)   solo si permite
  mascotas_max_kg      número o vacío (sin límite)                         solo si permite
  estacionamiento      propio | asignado | visitas | calle | ninguno
  precio_valor         número tal como aparece (4420 o 260000000)
  precio_moneda        UF | CLP
  comuna               la de la propiedad
  nota                 cualquier duda (obligatoria si la decisión es discutible)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_real import BUYER as BUYER_1, PREFS as PREFS_1, UF as UF_1  # noqa: E402
from matcher.rules import evaluate_property  # noqa: E402
from matcher.schema import Case, PetsPolicy, Truth  # noqa: E402

REAL = ROOT / "data" / "cases" / "real"
SHEETS = REAL / "anotacion"
OUT = ROOT / "data" / "cases" / "real_e3"
ANNOTATORS = ("carla", "benjamin")
FIELDS = ["dormitorios", "distancia_m", "mascotas", "mascotas_especies", "mascotas_max_kg",
          "estacionamiento", "precio_valor", "precio_moneda", "comuna"]
FIXED = ["rid", "sorteo", "portal", "url", "ficha"]

# Comprador 2 tal como quedó preregistrado (PREREGISTRO_E3.md). No se ajusta.
BUYER_2 = dict(presupuesto_max_clp=180_000_000, mascota_especie=None, mascota_kg=None,
               distancia_max_transporte_m=1200, dormitorios_min=2, estacionamiento_requerido=False)
PREFS_2 = ["Ñuñoa", "Santiago"]

ALLOWED = {
    "mascotas": {"no_menciona", "permite", "prohibe"},
    "mascotas_especies": {"", "perro", "gato", "perro+gato"},
    "estacionamiento": {"propio", "asignado", "visitas", "calle", "ninguno"},
    "precio_moneda": {"UF", "CLP"},
}


def listings() -> List[Dict]:
    out = []
    for sorteo, name in ((1, "muestra.json"), (2, "muestra_2.json")):
        path = REAL / "fuente" / name
        if not path.exists():
            sys.exit(f"falta {path.relative_to(ROOT)} (sorteo {sorteo})")
        snap = json.loads(path.read_text(encoding="utf-8"))
        for a in snap["avisos"]:
            out.append({"sorteo": sorteo, "uf": snap.get("uf_dia") or UF_1, **a})
    for i, a in enumerate(out, 1):
        a["rid"] = f"R{i:02d}"
    return out


def read_sheet(path: Path) -> Dict[str, Dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["rid"]: r for r in csv.DictReader(f, delimiter=";")}


def cmd_sheets() -> int:
    SHEETS.mkdir(parents=True, exist_ok=True)
    rows = [{"rid": a["rid"], "sorteo": a["sorteo"], "portal": a["source"], "url": a["url"],
             "ficha": a["ficha"], **{k: "" for k in FIELDS}, "nota": ""} for a in listings()]
    for who in ANNOTATORS:
        path = SHEETS / f"hoja_{who}.csv"
        if path.exists():
            print(f"{path.relative_to(ROOT)} ya existe: no se sobrescribe")
            continue
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIXED + FIELDS + ["nota"], delimiter=";")
            w.writeheader()
            w.writerows(rows)
        print(f"{len(rows)} avisos -> {path.relative_to(ROOT)}")
    return 0


def validate(sheet: Dict[str, Dict], who: str) -> List[str]:
    errs = []
    for rid, r in sheet.items():
        for k in FIELDS:
            v = (r.get(k) or "").strip()
            if k in ALLOWED and v not in ALLOWED[k]:
                errs.append(f"{who} {rid}: {k}={v!r} no es uno de {sorted(ALLOWED[k])}")
            elif k in ("dormitorios", "precio_valor", "comuna") and not v:
                errs.append(f"{who} {rid}: falta {k}")
            elif k == "distancia_m" and not (v == "NV" or v.isdigit()):
                errs.append(f"{who} {rid}: distancia_m={v!r} (entero o NV)")
    return errs


def cohen_kappa(a: List[str], b: List[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def _norm(k: str, v: str) -> str:
    v = (v or "").strip()
    if k in ("precio_valor", "mascotas_max_kg") and v:
        v = v.replace(".", "").replace(",", ".")
        return f"{float(v):g}"
    return v.casefold() if k == "comuna" else v


def cmd_agreement() -> int:
    sheets = {w: read_sheet(SHEETS / f"hoja_{w}.csv") for w in ANNOTATORS}
    errs = [e for w, s in sheets.items() for e in validate(s, w)]
    if errs:
        print("Hojas incompletas o con valores inválidos:\n  " + "\n  ".join(errs[:40]))
        return 1
    a, b = (sheets[w] for w in ANNOTATORS)
    rids = sorted(a)
    print(f"{len(rids)} avisos, anotadores: {', '.join(ANNOTATORS)}\n")
    print(f"{'campo':20s} acuerdo   kappa")
    diffs = []
    for k in FIELDS:
        xa = [_norm(k, a[r][k]) for r in rids]
        xb = [_norm(k, b[r][k]) for r in rids]
        agree = sum(x == y for x, y in zip(xa, xb))
        print(f"{k:20s} {agree:3d}/{len(rids)}  {cohen_kappa(xa, xb):6.2f}")
        diffs += [(r, k, x, y) for r, x, y in zip(rids, xa, xb) if x != y]
    print(f"\n{len(diffs)} desacuerdos (resolverlos en anotacion/adjudicada.csv):")
    for r, k, x, y in diffs:
        print(f"  {r} {k}: {ANNOTATORS[0]}={x!r} {ANNOTATORS[1]}={y!r}")
    return 0


def truth_from(r: Dict) -> Truth:
    pets = {"no_menciona": PetsPolicy(explicit=False), "prohibe": PetsPolicy(explicit=True, allowed=False)}
    if r["mascotas"] == "permite":
        sp = [s for s in r["mascotas_especies"].split("+") if s]
        kg = _norm("mascotas_max_kg", r["mascotas_max_kg"])
        pet = PetsPolicy(explicit=True, allowed=True, species=sp, max_kg=float(kg) if kg else None)
    else:
        pet = pets[r["mascotas"]]
    value = float(_norm("precio_valor", r["precio_valor"]))
    dist = None if r["distancia_m"] == "NV" else int(r["distancia_m"])
    return Truth(bedrooms=int(r["dormitorios"]), distance_transport_m=dist, pets=pet,
                 parking=r["estacionamiento"],
                 price_uf=value if r["precio_moneda"] == "UF" else None,
                 price_clp=int(value) if r["precio_moneda"] == "CLP" else None,
                 rent_monthly_clp=None, location=r["comuna"].strip())


def groups(items: List[Dict]) -> List[List[Dict]]:
    """Un aviso de cada portal por caso, como en real/: el sorteo guarda los avisos por
    portal en bloques del mismo tamaño."""
    out = []
    for sorteo in (1, 2):
        xs = [a for a in items if a["sorteo"] == sorteo]
        per = len(xs) // 4
        out += [[xs[k + per * j] for j in range(4)] for k in range(per)]
    return out


def cmd_build() -> int:
    adj_path = SHEETS / "adjudicada.csv"
    if not adj_path.exists():
        sys.exit("falta anotacion/adjudicada.csv (paso 4 del preregistro)")
    adj = read_sheet(adj_path)
    errs = validate(adj, "adjudicada")
    if errs:
        print("\n  ".join(["adjudicada.csv inválida:"] + errs[:40]))
        return 1
    items = listings()
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for buyer, (hc, prefs) in {"b1": (BUYER_1, PREFS_1), "b2": (BUYER_2, PREFS_2)}.items():
        for i, members in enumerate(groups(items), 1):
            props = [{"id": f"REAL-{int(a['rid'][1:]):02d}", "text": a["ficha"],
                      "truth": asdict(truth_from(adj[a["rid"]])), "fuente": a["url"],
                      "portal": a["source"], "note": adj[a["rid"]].get("nota", "")} for a in members]
            c = {"id": f"real_{buyer}_{i:03d}", "uf_value": members[0]["uf"], "hard_constraints": hc,
                 "soft_constraints": {"ubicaciones_preferidas": prefs}, "properties": props}
            case = Case.from_dict(c)
            verdicts = {p.id: evaluate_property(p, case).failed_constraints for p in case.properties}
            print(c["id"], " ".join(f"{k}:{'OK' if not v else ','.join(v)}" for k, v in verdicts.items()))
            (OUT / f"{c['id']}.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
            n += 1
    print(f"{n} casos -> {OUT.relative_to(ROOT)}/  (revisar los veredictos de arriba antes de versionar)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("sheets", "agreement", "build"))
    sys.exit({"sheets": cmd_sheets, "agreement": cmd_agreement, "build": cmd_build}[ap.parse_args().cmd]())
