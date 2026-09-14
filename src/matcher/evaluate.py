"""Runner de evaluación y tabla comparativa entre modelos.

Estructura esperada:
  data/cases/test/<case_id>.json     casos held-out anotados con `truth`
  results/<run>/<case_id>.txt        respuesta cruda del modelo para ese caso
  results/<run>/<case_id>.meta.json  (opcional) tokens y tiempos, escritos por run_model

Uso:
  python -m matcher.evaluate --runs baseline_phi4 baseline_granite baseline_deepseek
  -> results/summary.csv               una fila por run (la tabla del PDF)
     results/<run>.csv                 veredicto por caso
     results/<run>_breakdown.csv       aprobaciones indebidas por restricción

Dos niveles de corrección, siempre reportados juntos:
  e1_strict         criterio E1 literal sobre la respuesta cruda
  e1_after_extract  mismo criterio tras quitar fences/<think> (extractor determinista)
Métricas secundarias: exact_match (conjunto exacto), ranking_ok (orden por soft
constraints) y full_correct (E1 + exact_match + ranking_ok).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from .rules import expected_output
from .schema import Case
from .verifier import Verdict, verify

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases" / "test"   # held-out; train/ es solo para destilar
RESULTS_DIR = ROOT / "results"

CONSTRAINTS = ["presupuesto", "mascotas", "distancia_transporte", "dormitorios", "estacionamiento"]
_FA_RE = re.compile(r"(PROP-\w+) aprobada pero viola \[([^\]]*)\]")


def load_cases(cases_dir: Path = CASES_DIR) -> List[Case]:
    return [Case.load(p) for p in sorted(cases_dir.glob("*.json"))]


def evaluate_run(run: str, cases: List[Case], results_dir: Path = RESULTS_DIR) -> List[Verdict]:
    verdicts, missing = [], []
    for case in cases:
        path = results_dir / run / f"{case.id}.txt"
        if not path.exists():
            missing.append(case.id)
            continue
        raw = path.read_text(encoding="utf-8")
        verdicts.append(verify(case, raw, expected_output(case)))
    if missing:
        print(f"[{run}] {len(missing)}/{len(cases)} casos sin respuesta aún "
              f"(p.ej. {missing[0]}); la tabla usa solo los {len(verdicts)} respondidos", file=sys.stderr)
    return verdicts


def write_csv(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _pct(num: int, den: int) -> str:
    return f"{100 * num / den:.0f}%" if den else "-"


def breakdown(run: str, verdicts: List[Verdict], cases: List[Case]) -> List[Dict]:
    """Por restricción: cuántas propiedades inválidas la violan y cuántas aprobó el modelo igual."""
    invalid = Counter()
    for c in cases:
        for e in expected_output(c).by_id.values():
            for k in e.failed_constraints:
                invalid[k] += 1
    approved_anyway = Counter()
    for v in verdicts:
        for m in _FA_RE.finditer(" | ".join(v.details)):
            for k in re.findall(r"'(\w+)'", m.group(2)):
                approved_anyway[k] += 1
    return [{
        "run": run, "constraint": k, "invalid_in_test": invalid[k],
        "approved_anyway": approved_anyway[k],
        "false_approval_rate": _pct(approved_anyway[k], invalid[k]),
    } for k in CONSTRAINTS]


def cost(run: str, results_dir: Path) -> Dict:
    metas = [json.loads(p.read_text()) for p in (results_dir / run).glob("*.meta.json")]
    if not metas:
        return {"model": "", "truncated": "", "mean_output_tokens": "", "mean_wall_s": ""}
    return {
        "model": metas[0].get("model", ""),
        "truncated": sum(m.get("done_reason") == "length" for m in metas),
        "mean_output_tokens": round(statistics.mean(m.get("output_tokens") or 0 for m in metas)),
        "mean_wall_s": round(statistics.mean(m.get("wall_s") or 0 for m in metas), 1),
    }


def summarize(run: str, verdicts: List[Verdict], results_dir: Path) -> Dict:
    n = len(verdicts)
    strict = sum(v.e1_correct for v in verdicts)
    extracted = sum(v.e1_correct or bool(v.lenient_e1) for v in verdicts)
    # motivo de fallo tras extractor (el más informativo para "lectura de límites")
    reasons = Counter((v.lenient_reason or v.reason) for v in verdicts if not (v.e1_correct or v.lenient_e1))
    row = {"run": run, **cost(run, results_dir), "n": n,
           "e1_strict": strict, "e1_strict_acc": round(strict / n, 3) if n else 0.0,
           "e1_after_extract": extracted, "e1_after_extract_acc": round(extracted / n, 3) if n else 0.0,
           "exact_match": sum(v.exact_match for v in verdicts),
           "ranking_ok": sum(v.ranking_ok for v in verdicts),
           "full_correct": sum(v.full_correct for v in verdicts),
           "fail_schema": reasons.get("schema_error", 0),
           "fail_false_approval": reasons.get("false_approval", 0),
           "fail_arithmetic": reasons.get("arithmetic_error", 0),
           "raw_wrapped": sum(1 for v in verdicts if v.lenient_e1 is not None)}
    return row


def print_table(rows: List[Dict], cols: List[str]) -> None:
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True, help="nombres de carpetas dentro de results/")
    ap.add_argument("--cases", default=str(CASES_DIR))
    ap.add_argument("--results", default=str(RESULTS_DIR))
    args = ap.parse_args(argv)

    cases = load_cases(Path(args.cases))
    if not cases:
        print("no hay casos en", args.cases, file=sys.stderr)
        return 1
    results_dir = Path(args.results)

    summaries, breakdowns = [], []
    for run in args.runs:
        verdicts = evaluate_run(run, cases, results_dir)
        if not verdicts:
            continue
        rows = [dict(run=run, **v.as_row()) for v in verdicts]
        write_csv(results_dir / f"{run}.csv", rows)
        bd = breakdown(run, verdicts, cases)
        write_csv(results_dir / f"{run}_breakdown.csv", bd)
        breakdowns += bd
        summaries.append(summarize(run, verdicts, results_dir))

    write_csv(results_dir / "summary.csv", summaries)

    print("== Resumen por modelo ==")
    print_table(summaries, ["run", "model", "n", "e1_strict", "e1_after_extract", "exact_match",
                            "ranking_ok", "full_correct", "fail_schema", "fail_false_approval", "fail_arithmetic", "raw_wrapped",
                            "truncated", "mean_output_tokens", "mean_wall_s"])
    print("\n== Aprobaciones indebidas por restricción (tras extractor) ==")
    print_table(breakdowns, ["run", "constraint", "invalid_in_test", "approved_anyway", "false_approval_rate"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
