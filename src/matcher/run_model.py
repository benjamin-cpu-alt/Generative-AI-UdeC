"""Corre un modelo de Ollama sobre un split de casos y guarda las respuestas crudas.

Cada caso produce:
  results/<run>/<case_id>.txt        respuesta cruda, tal cual la emitió el modelo
  results/<run>/<case_id>.meta.json  modelo, opciones, tokens, duración (trazabilidad)

El prompt es siempre `prompt.render_prompt(case)`. Este módulo corre el BASELINE
(prompting directo) de cualquier modelo; la solución de la E2 vive en run_pipeline.py.

Uso:
  python -m matcher.run_model --model phi4-mini:latest --run baseline_phi4
  python -m matcher.run_model --model granite4.1:8b --run baseline_granite
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from .prompt import render_prompt
from .schema import Case

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases"
RESULTS_DIR = ROOT / "results"
OLLAMA_URL = "http://localhost:11434"


def ollama_generate(model: str, prompt: str, options: Dict, timeout: int = 600,
                    url: str = OLLAMA_URL) -> Dict:
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False, "options": options,
    }).encode("utf-8")
    req = urllib.request.Request(f"{url}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run(model: str, run_name: str, cases: List[Case], options: Dict,
        results_dir: Path = RESULTS_DIR, force: bool = False, timeout: int = 600) -> int:
    out = results_dir / run_name
    out.mkdir(parents=True, exist_ok=True)
    done = 0
    for i, case in enumerate(cases, 1):
        txt = out / f"{case.id}.txt"
        if txt.exists() and not force:
            print(f"[{i}/{len(cases)}] {case.id}: ya existe, se omite", flush=True)
            continue
        prompt = render_prompt(case)
        t0 = time.time()
        try:
            r = ollama_generate(model, prompt, options, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"[{i}/{len(cases)}] {case.id}: ERROR {e}", file=sys.stderr, flush=True)
            continue
        dt = time.time() - t0
        txt.write_text(r.get("response", ""), encoding="utf-8")
        meta = {
            "case_id": case.id, "model": model, "run": run_name, "options": options,
            "prompt_tokens": r.get("prompt_eval_count"), "output_tokens": r.get("eval_count"),
            "total_duration_s": round(r.get("total_duration", 0) / 1e9, 2),
            "wall_s": round(dt, 2), "done_reason": r.get("done_reason"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        (out / f"{case.id}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        done += 1
        print(f"[{i}/{len(cases)}] {case.id}: {meta['output_tokens']} tok, {dt:.1f}s "
              f"({meta['done_reason']})", flush=True)
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="nombre del modelo en Ollama")
    ap.add_argument("--run", required=True, help="nombre de la carpeta en results/")
    ap.add_argument("--split", default="test", help="subcarpeta de data/cases (test|train)")
    ap.add_argument("--limit", type=int, default=None, help="solo los primeros N casos")
    ap.add_argument("--only", nargs="*", help="ids de casos específicos")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--num-predict", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--force", action="store_true", help="re-genera aunque exista")
    a = ap.parse_args(argv)

    paths = sorted((CASES_DIR / a.split).glob("*.json"))
    cases = [Case.load(p) for p in paths]
    if a.only:
        cases = [c for c in cases if c.id in set(a.only)]
    if a.limit:
        cases = cases[: a.limit]
    if not cases:
        print("sin casos", file=sys.stderr)
        return 1

    options = {"temperature": a.temperature, "num_ctx": a.num_ctx,
               "num_predict": a.num_predict, "seed": a.seed}
    print(f"modelo={a.model} run={a.run} casos={len(cases)} opciones={options}", flush=True)
    n = run(a.model, a.run, cases, options, force=a.force, timeout=a.timeout)
    print(f"listo: {n} respuestas nuevas en results/{a.run}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
