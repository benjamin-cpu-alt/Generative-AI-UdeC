"""Muestra un caso de hard_test (o hard_dev) en formato legible para la revisión humana.

  python3 scripts/review_hard.py ht_01          # un caso
  python3 scripts/review_hard.py ht_01 ht_02    # varios
  python3 scripts/review_hard.py --sheet carla ht_01-ht_15   # planilla de revisión (CSV)

Por cada aviso imprime el texto, la verdad anotada en palabras y el veredicto que esa
verdad produce con rules.py. La revisión consiste en confirmar que la verdad dice lo mismo
que el texto (ver data/cases/hard_test/REVIEW.md).
"""
from __future__ import annotations

import csv
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from matcher.rules import expected_output  # noqa: E402
from matcher.schema import Case  # noqa: E402


def clp(n) -> str:
    return "$" + f"{int(round(n)):,}".replace(",", ".")


def pets_text(p: dict) -> str:
    if not p["explicit"]:
        return "el aviso NO declara política (no explícita)"
    if not p["allowed"]:
        return "PROHÍBE mascotas"
    sp = " y ".join(p["species"]) if p["species"] else "cualquier especie"
    kg = f"hasta {p['max_kg']:g} kg" if p["max_kg"] is not None else "sin límite de peso"
    return f"permite {sp}, {kg}"


def load(cid: str):
    split = "hard_test" if cid.startswith("ht_") else "hard_dev"
    path = ROOT / "data" / "cases" / split / f"{cid}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw, expected_output(Case.load(path))


def buyer_text(raw: dict) -> str:
    hc = raw["hard_constraints"]
    mascota = ("sin mascota" if hc["mascota_especie"] is None
               else f"{hc['mascota_especie']} de {hc['mascota_kg']:g} kg")
    return (f"tope {clp(hc['presupuesto_max_clp'])} · {mascota} · transporte <= "
            f"{hc['distancia_max_transporte_m']} m · >= {hc['dormitorios_min']} dorm. · estac. "
            f"{'requerido' if hc['estacionamiento_requerido'] else 'no requerido'} · UF {clp(raw['uf_value'])}")


def truth_cells(t: dict, e) -> dict:
    return {
        "comuna": t["location"], "dormitorios": t["bedrooms"],
        "distancia": f"{t['distance_transport_m']} m" if t["distance_transport_m"] is not None else "NO verificable",
        "estacionamiento": t["parking"],
        "precio": (f"UF {t['price_uf']:g} = {clp(e.price_clp)}" if t["price_uf"] is not None else clp(t["price_clp"])),
        "arriendo": clp(t["rent_monthly_clp"]) + "/mes" if t["rent_monthly_clp"] else "no publica",
        "mascotas": pets_text(t["pets"]),
        "veredicto": "APROBADA" if e.approved else "RECHAZADA: " + ", ".join(e.failed_constraints),
    }


def expand(args):
    out = []
    for a in args:
        m = re.fullmatch(r"(h[td])_(\d+)-h[td]_(\d+)", a)
        out += [f"{m.group(1)}_{i:02d}" for i in range(int(m.group(2)), int(m.group(3)) + 1)] if m else [a]
    return out


def sheet(who: str, cids) -> Path:
    out = ROOT / "data" / "cases" / "hard_test" / "revision" / f"revision_{who}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        sys.exit(f"{out.relative_to(ROOT)} ya existe: no se sobrescribe")
    cols = ["caso", "comprador", "aviso", "texto", "comuna", "dormitorios", "distancia",
            "estacionamiento", "precio", "arriendo", "mascotas", "veredicto", "nota_anotacion",
            "correcto", "que_esta_mal"]
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        for cid in cids:
            raw, exp = load(cid)
            for p in raw["properties"]:
                w.writerow({"caso": cid, "comprador": buyer_text(raw), "aviso": p["id"], "texto": p["text"],
                            **truth_cells(p["truth"], exp.by_id[p["id"]]), "nota_anotacion": p["note"],
                            "correcto": "", "que_esta_mal": ""})
    return out


def show(cid: str) -> None:
    raw, exp = load(cid)
    hc = raw["hard_constraints"]
    mascota = ("sin mascota" if hc["mascota_especie"] is None
               else f"{hc['mascota_especie']} de {hc['mascota_kg']:g} kg")
    print("=" * 96)
    print(f"{cid}  ·  UF del día {clp(raw['uf_value'])}  ·  {raw['style']}")
    print(f"COMPRADOR: tope {clp(hc['presupuesto_max_clp'])} · {mascota} · transporte <= "
          f"{hc['distancia_max_transporte_m']} m · >= {hc['dormitorios_min']} dormitorios · "
          f"estacionamiento {'REQUERIDO' if hc['estacionamiento_requerido'] else 'no requerido'} · "
          f"preferidas: {', '.join(raw['soft_constraints']['ubicaciones_preferidas'])}")
    for p in raw["properties"]:
        t, e = p["truth"], exp.by_id[p["id"]]
        precio = (f"UF {t['price_uf']:g} = {clp(e.price_clp)}" if t["price_uf"] is not None
                  else clp(t["price_clp"]))
        dist = f"{t['distance_transport_m']} m" if t["distance_transport_m"] is not None else "NO verificable"
        rent = clp(t["rent_monthly_clp"]) + "/mes" if t["rent_monthly_clp"] else "no publica"
        verdict = "APROBADA" if e.approved else "RECHAZADA por " + ", ".join(e.failed_constraints)
        print("-" * 96)
        print(f"{p['id']}  [{', '.join(p['tags']) or 'control'}]")
        print(textwrap.fill(p["text"], 96, initial_indent="  «", subsequent_indent="   ") + "»")
        print(f"  comuna: {t['location']} | dormitorios: {t['bedrooms']} | distancia: {dist} | "
              f"estacionamiento: {t['parking']}")
        print(f"  precio: {precio} | arriendo: {rent} | mascotas: {pets_text(t['pets'])}")
        print(f"  → {verdict}      (nota: {p['note']})")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "--sheet":
        path = sheet(sys.argv[2], expand(sys.argv[3:]))
        print(f"-> {path.relative_to(ROOT)}")
    else:
        for cid in expand(sys.argv[1:]):
            show(cid)
