"""Corre una estrategia (pipeline.MODES) sobre un split y guarda resultados en el
MISMO layout que run_model.py, para que `evaluate.py` compare baseline y solución
con el mismo juez:

  results/<run>/<case_id>.txt          JSON final (lo que juzga el verificador)
  results/<run>/<case_id>.meta.json    modelo, modo, llamadas, tokens, tiempo
  results/<run>/<case_id>.trace.json   hechos extraídos + decisiones (solo modos decomp)

Uso:
  python -m matcher.run_pipeline --mode tools      --run tools_phi4                       # prompt v2
  python -m matcher.run_pipeline --mode tools      --run tools_phi4_v1 --prompt-version v1
  python -m matcher.run_pipeline --mode tools      --run dev_tools_v2 --split train --limit 30   # iterar en DEV
  python -m matcher.run_pipeline --mode tools      --run dev_tools_v5 --split train --limit 30 --prompt-version v5
  python -m matcher.run_pipeline --mode cot        --run cot_phi4
  python -m matcher.run_pipeline --mode decomp_llm --run decomp_phi4
  python -m matcher.evaluate --runs baseline_phi4 cot_phi4 decomp_phi4 tools_phi4
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
from pathlib import Path
from typing import List

from .pipeline import MODES, run_case
from .schema import Case

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases"
RESULTS_DIR = ROOT / "results"


def run(model: str, mode: str, run_name: str, cases: List[Case], results_dir: Path = RESULTS_DIR,
        force: bool = False, timeout: int = 600, prompt_version: str = "v1") -> int:
    out = results_dir / run_name
    out.mkdir(parents=True, exist_ok=True)
    done = 0
    for i, case in enumerate(cases, 1):
        txt = out / f"{case.id}.txt"
        if txt.exists() and not force:
            print(f"[{i}/{len(cases)}] {case.id}: ya existe, se omite", flush=True)
            continue
        try:
            tr = run_case(case, model, mode, timeout=timeout, prompt_version=prompt_version)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"[{i}/{len(cases)}] {case.id}: ERROR {e}", file=sys.stderr, flush=True)
            continue
        txt.write_text(tr.output_text, encoding="utf-8")
        meta = {
            "case_id": case.id, "model": model, "run": run_name, "mode": mode,
            "prompt_version": prompt_version if mode in ("tools", "decomp_llm") else None,
            "calls": tr.calls, "prompt_tokens": tr.prompt_tokens, "output_tokens": tr.output_tokens,
            "wall_s": tr.wall_s, "done_reason": "error" if tr.errors else "stop",
            "errors": tr.errors, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        (out / f"{case.id}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        if tr.facts:
            (out / f"{case.id}.trace.json").write_text(
                json.dumps({"facts": tr.facts, "decisions": tr.decisions}, indent=2, ensure_ascii=False),
                encoding="utf-8")
        done += 1
        print(f"[{i}/{len(cases)}] {case.id}: {tr.calls} llamadas, {tr.output_tokens} tok, {tr.wall_s:.1f}s"
              + (f" ERRORES: {tr.errors}" if tr.errors else ""), flush=True)
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=MODES, required=True)
    ap.add_argument("--model", default="phi4-mini:latest")
    ap.add_argument("--run", required=True, help="carpeta en results/")
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--prompt-version", default="v1", choices=("v1", "v2", "v3", "v4", "v5"),
                    help="prompt del extractor (ver extract.py; v5 = spans + grounding; "
                         "se elige en dev, nunca en test)")
    a = ap.parse_args(argv)

    cases = [Case.load(p) for p in sorted((CASES_DIR / a.split).glob("*.json"))]
    if a.only:
        cases = [c for c in cases if c.id in set(a.only)]
    if a.limit:
        cases = cases[: a.limit]
    if not cases:
        print("sin casos", file=sys.stderr)
        return 1
    print(f"modo={a.mode} modelo={a.model} run={a.run} casos={len(cases)}", flush=True)
    n = run(a.model, a.mode, a.run, cases, force=a.force, timeout=a.timeout, prompt_version=a.prompt_version)
    print(f"listo: {n} respuestas nuevas en results/{a.run}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
