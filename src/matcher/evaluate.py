"""Runner de evaluación.

Estructura esperada:
  data/cases/<case_id>.json          casos anotados con `truth`
  results/<run>/<case_id>.txt        respuesta cruda del modelo para ese caso

Uso:
  python -m matcher.evaluate --runs baseline_phi4 distill_phi4
  -> escribe results/summary.csv y results/<run>.csv, e imprime la tabla resumen.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

from .rules import expected_output
from .schema import Case
from .verifier import Verdict, verify

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases"
RESULTS_DIR = ROOT / "results"


def load_cases(cases_dir: Path = CASES_DIR) -> List[Case]:
    return [Case.load(p) for p in sorted(cases_dir.glob("*.json"))]


def evaluate_run(run: str, cases: List[Case], results_dir: Path = RESULTS_DIR) -> List[Verdict]:
    verdicts = []
    for case in cases:
        path = results_dir / run / f"{case.id}.txt"
        if not path.exists():
            print(f"[{run}] falta {path.relative_to(ROOT)}", file=sys.stderr)
            continue
        raw = path.read_text(encoding="utf-8")
        verdicts.append(verify(case, raw, expected_output(case)))
    return verdicts


def write_csv(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def summarize(run: str, verdicts: List[Verdict]) -> Dict:
    n = len(verdicts)
    reasons = Counter(v.reason for v in verdicts)
    return {
        "run": run,
        "n": n,
        "e1_correct": sum(v.e1_correct for v in verdicts),
        "e1_accuracy": round(sum(v.e1_correct for v in verdicts) / n, 3) if n else 0.0,
        "exact_match": sum(v.exact_match for v in verdicts),
        "exact_accuracy": round(sum(v.exact_match for v in verdicts) / n, 3) if n else 0.0,
        "schema_error": reasons.get("schema_error", 0),
        "false_approval": reasons.get("false_approval", 0),
        "arithmetic_error": reasons.get("arithmetic_error", 0),
    }


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

    summaries = []
    for run in args.runs:
        verdicts = evaluate_run(run, cases, results_dir)
        rows = [v.as_row() for v in verdicts]
        for r in rows:
            r["run"] = run
        write_csv(results_dir / f"{run}.csv", rows)
        summaries.append(summarize(run, verdicts))

    write_csv(results_dir / "summary.csv", summaries)

    cols = ["run", "n", "e1_correct", "e1_accuracy", "exact_match", "exact_accuracy",
            "schema_error", "false_approval", "arithmetic_error"]
    widths = {c: max(len(c), *(len(str(s[c])) for s in summaries)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for s in summaries:
        print("  ".join(str(s[c]).ljust(widths[c]) for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
