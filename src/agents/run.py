"""Corre el sistema multiagente sobre un split con el mismo layout que la E2, para que
`matcher.evaluate` y `matcher.metrics` lo juzguen con el mismo criterio:

  results/<run>/<case_id>.txt           JSON final (lo que juzga el verificador)
  results/<run>/<case_id>.meta.json     configuración, llamadas, tokens, tiempo, acciones
  results/<run>/<case_id>.trace.jsonl   TODOS los mensajes entre agentes y herramientas

Uso:
  python -m agents.run --split hard_dev --run agents_v1_hard_dev
  python -m agents.run --split hard_test --run agents_sin_retro_hard_test --sin retro
  python -m agents.show results/agents_v1_hard_dev/hd_01.trace.jsonl     # ver una traza
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from matcher.schema import Case

from .orchestrator import Config, Sistema

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases"
RESULTS_DIR = ROOT / "results"
ABLACIONES = ("esquema", "literal", "refinar", "retro", "herramientas_decisor")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--model", default="phi4-mini:latest")
    ap.add_argument("--sin", nargs="*", default=[], choices=ABLACIONES, help="técnicas a quitar (ablación)")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    cfg = Config(model=a.model, **{k: False for k in a.sin})
    sistema = Sistema(cfg)
    cases = [Case.load(p) for p in sorted((CASES_DIR / a.split).glob("*.json"))]
    if a.only:
        cases = [c for c in cases if c.id in set(a.only)]
    cases = cases[: a.limit] if a.limit else cases
    out = RESULTS_DIR / a.run
    out.mkdir(parents=True, exist_ok=True)
    print(f"agentes config={cfg.nombre} split={a.split} run={a.run} casos={len(cases)}", flush=True)
    for i, case in enumerate(cases, 1):
        txt = out / f"{case.id}.txt"
        if txt.exists() and not a.force:
            print(f"[{i}/{len(cases)}] {case.id}: ya existe, se omite", flush=True)
            continue
        t0 = time.time()
        result, tr = sistema.run_case(case)
        txt.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / f"{case.id}.trace.jsonl").write_text(tr.jsonl(), encoding="utf-8")
        meta = {"case_id": case.id, "run": a.run, "split": a.split, "mode": "agents", "config": cfg.nombre,
                "model": cfg.model, "prompts": {"lector": cfg.lector, "verificador": cfg.verificador,
                                                "decisor": cfg.decisor},
                "grounding_version": cfg.grounding, "calls": tr.llamadas, "prompt_tokens": tr.prompt_tokens,
                "output_tokens": tr.output_tokens, "wall_s": round(time.time() - t0, 2),
                "llm_s": round(tr.wall_s, 2), "acciones": tr.acciones, "mensajes": len(tr.mensajes),
                "done_reason": "error" if tr.errores else "stop", "errors": tr.errores,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
        (out / f"{case.id}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[{i}/{len(cases)}] {case.id}: {tr.llamadas} llamadas, {len(tr.mensajes)} mensajes, "
              f"{meta['wall_s']:.0f}s {tr.acciones}" + (f" ERRORES {tr.errores}" if tr.errores else ""), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
