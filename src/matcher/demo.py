"""Demo para el video: baseline vs solución sobre el MISMO caso, de principio a fin,
con el veredicto del mismo juez para ambos. Sin edición: todo se imprime en vivo.

  python -m matcher.demo --case case_001_e1        # el caso original de la E1
  python -m matcher.demo --random                  # caso al azar del split test (no elegido a mano)
  python -m matcher.demo --random --seed 7         # reproducible
  python -m matcher.demo --split ood --case ood_002 # un caso donde la solución todavía falla
  python -m matcher.demo --split real --random      # un aviso REAL sorteado de los portales
  python -m matcher.demo --split real_fallo --case fallo_001 --grounding g3   # fallo real de g3

Imprime: (1) el perfil y el catálogo crudo, (2) la respuesta del baseline y su
veredicto, (3) los hechos extraídos por propiedad, las comparaciones deterministas
y el JSON final de la solución con su veredicto, (4) tiempos y tokens.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from . import grounding
from .extract import DEFAULT_PROMPT
from .pipeline import run_case
from .prompt import render_profile, render_soft
from .rules import expected_output
from .schema import Case
from .verifier import verify

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases"


def hr(title: str) -> None:
    print("\n" + "=" * 78 + f"\n {title}\n" + "=" * 78, flush=True)


def show_verdict(case: Case, text: str) -> None:
    v = verify(case, text, expected_output(case))
    tag = "CORRECTO" if v.e1_correct else "INCORRECTO"
    print(f"\n>>> VEREDICTO (criterio E1): {tag} — motivo: {v.reason}")
    for d in v.details:
        print(f"    - {d}")
    print(f"    exact_match={int(v.exact_match)} ranking_ok={int(v.ranking_ok)} "
          f"full_correct={int(v.full_correct)}")
    print(f"    esperado aprobadas={v.expected_approved} rechazadas={v.expected_rejected}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--case", help="id del caso, p.ej. case_001_e1 o test_0017")
    g.add_argument("--random", action="store_true")
    ap.add_argument("--split", default="test", help="subcarpeta de data/cases (test|ood|train)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--model", default="phi4-mini:latest")
    ap.add_argument("--baseline-model", default=None, help="por defecto el mismo modelo")
    ap.add_argument("--skip-baseline", action="store_true")
    ap.add_argument("--grounding", default=grounding.DEFAULT_VERSION, choices=grounding.VERSIONS,
                    help="capa de anclaje (g3 = la reportada en la E2; g4 = + correcciones con avisos reales)")
    ap.add_argument("--prompt-version", default=DEFAULT_PROMPT,
                    help="prompt del extractor (v5 = el reportado en el PDF; v1 = la primera versión)")
    a = ap.parse_args(argv)

    cases_dir = CASES_DIR / a.split
    paths = sorted(cases_dir.glob("*.json"))
    if a.random:
        rng = random.Random(a.seed)
        path = rng.choice(paths)
        print(f"caso elegido al azar de {a.split}/ (seed={a.seed}): {path.name}")
    else:
        path = cases_dir / f"{a.case}.json"
    case = Case.load(path)

    hr(f"ENTRADA — {case.id}  (UF hoy: ${int(case.uf_value):,} CLP)".replace(",", "."))
    print(render_profile(case)); print(); print(render_soft(case)); print()
    for p in case.properties:
        print(f"[{p.id}] {p.text}\n")

    if not a.skip_baseline:
        hr(f"BASELINE — prompting directo, {a.baseline_model or a.model}")
        tb = run_case(case, a.baseline_model or a.model, "baseline")
        print(tb.output_text)
        print(f"\n[{tb.calls} llamada, {tb.output_tokens} tokens de salida, {tb.wall_s:.1f}s]")
        show_verdict(case, tb.output_text)

    hr(f"SOLUCIÓN — descomposición + herramientas, {a.model}, prompt {a.prompt_version}, anclaje {a.grounding}")
    ts = run_case(case, a.model, "tools", prompt_version=a.prompt_version, grounding_version=a.grounding)
    print("Paso 1 · hechos extraídos por el LLM (una llamada por propiedad, sin ver el perfil):")
    for pid, f in ts.facts.items():
        keys = ("location", "bedrooms", "price_text", "rent_text", "distance_metro_text",
                "distance_bus_text", "pets_policy", "pets_species", "pets_max_kg", "parking")
        print(f"  {pid}: " + json.dumps({k: f[k] for k in keys}, ensure_ascii=False))
    print("\nPaso 2 · comparaciones deterministas (Python):")
    for pid, d in ts.decisions.items():
        estado = "APROBADA" if not d["failed_constraints"] else f"RECHAZADA {d['failed_constraints']}"
        print(f"  {pid}: {estado}")
        for n in d["notes"]:
            print(f"      · {n}")
    print("\nPaso 3 · JSON final:")
    print(ts.output_text)
    print(f"\n[{ts.calls} llamadas, {ts.output_tokens} tokens de salida, {ts.wall_s:.1f}s]")
    show_verdict(case, ts.output_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
