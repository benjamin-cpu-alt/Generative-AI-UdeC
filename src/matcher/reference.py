"""Corridas de referencia sin modelo, escritas con el mismo layout que cualquier run.

  reject_all   rechaza todas las propiedades, con JSON válido. Es el PISO del criterio
               `e1_strict`: como la E1 solo castiga aprobar de más, esta estrategia obtiene
               51/51 en test, 12/12 en OOD y 4/4 en real. Cualquier cifra de e1_strict se
               lee contra esta fila; por eso desde la E3 se reporta junto a full_correct y
               a las métricas por propiedad (matcher.metrics).

Uso:
  python -m matcher.reference --split hard_dev     # -> results/ref_reject_all_hard_dev/
  python -m matcher.reference --split test         # -> results/ref_reject_all/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluate import RESULTS_DIR, load_cases

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases"


def reject_all_output(case) -> str:
    return json.dumps({"approved_matches": [],
                       "rejected": [{"id": p.id, "failed_constraints": []} for p in case.properties]},
                      ensure_ascii=False)


def run_name(split: str) -> str:
    return "ref_reject_all" + ("" if split == "test" else f"_{split}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="test", help="subcarpeta de data/cases")
    ap.add_argument("--results", default=str(RESULTS_DIR))
    a = ap.parse_args(argv)
    cases = load_cases(CASES_DIR / a.split)
    if not cases:
        print("no hay casos en", CASES_DIR / a.split, file=sys.stderr)
        return 1
    out = Path(a.results) / run_name(a.split)
    out.mkdir(parents=True, exist_ok=True)
    for c in cases:
        (out / f"{c.id}.txt").write_text(reject_all_output(c), encoding="utf-8")
    print(f"{len(cases)} casos -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
