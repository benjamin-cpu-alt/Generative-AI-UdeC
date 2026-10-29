"""Muestra un caso de hard_test (o hard_dev) en formato legible para la revisión humana.

  python3 scripts/review_hard.py ht_01          # un caso
  python3 scripts/review_hard.py ht_01 ht_02    # varios

Por cada aviso imprime el texto, la verdad anotada en palabras y el veredicto que esa
verdad produce con rules.py. La revisión consiste en confirmar que la verdad dice lo mismo
que el texto (ver data/cases/hard_test/REVIEW.md).
"""
from __future__ import annotations

import json
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


def show(cid: str) -> None:
    split = "hard_test" if cid.startswith("ht_") else "hard_dev"
    path = ROOT / "data" / "cases" / split / f"{cid}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    case = Case.load(path)
    exp = expected_output(case)
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
    for cid in sys.argv[1:]:
        show(cid)
