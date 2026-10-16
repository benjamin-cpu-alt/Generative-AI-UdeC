"""Métricas de la E3: las de evaluate.py con intervalo de confianza, más métricas por
propiedad y por fenómeno. Mismo juez (verifier.py), mismo layout de results/.

Por qué hacen falta: `e1_strict` solo castiga aprobar de más, así que rechazar todo lo
satura (ver matcher.reference). Las métricas por propiedad miden las dos direcciones:

  e1_strict / exact_match / full_correct   por caso, con IC de Wilson al 95 %
  prop_acc          propiedades con el veredicto correcto (aprobada o rechazada)
  false_approval    aprobadas que debían rechazarse / las que debían rechazarse
  false_rejection   no aprobadas que debían aprobarse / las que debían aprobarse
  por fenómeno      prop_acc de las propiedades con cada `tag` (solo sets hard_*)

Una respuesta que no pasa el parseo estricto no clasifica ninguna propiedad: todas cuentan
como error (aprobadas indebidas no, rechazos falsos sí), igual que en el criterio E1.

Uso:
  python -m matcher.metrics --cases ../data/cases/hard_dev \\
      --runs ref_reject_all_hard_dev baseline_phi4_hard_dev tools_phi4_v5_hard_dev_g3
  -> results/metrics_<split>.csv  y  results/metrics_<split>_tags.csv
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from .evaluate import CASES_DIR, RESULTS_DIR, evaluate_run, load_cases, print_table, write_csv
from .rules import expected_output
from .verifier import REASON_SCHEMA


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Intervalo de Wilson para una proporción k/n (no se sale de [0, 1] con n chico)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def fmt_ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} [{100 * lo:.0f}-{100 * hi:.0f}]"


def load_tags(cases_dir: Path) -> Dict[str, List[str]]:
    tags = {}
    for p in sorted(cases_dir.glob("*.json")):
        for prop in json.loads(p.read_text(encoding="utf-8"))["properties"]:
            tags[prop["id"]] = prop.get("tags") or []
    return tags


def run_metrics(run: str, cases, results_dir: Path, tags: Dict[str, List[str]]):
    verdicts = {v.case_id: v for v in evaluate_run(run, cases, results_dir)}
    n = len(verdicts)
    row = {"run": run, "n_cases": n,
           "e1_strict": fmt_ci(sum(v.e1_correct for v in verdicts.values()), n),
           "exact_match": fmt_ci(sum(v.exact_match for v in verdicts.values()), n),
           "full_correct": fmt_ci(sum(v.full_correct for v in verdicts.values()), n)}
    props = ok = fa = fr = should_rej = should_app = 0
    by_tag = defaultdict(lambda: [0, 0])
    for c in cases:
        v = verdicts.get(c.id)
        if v is None:
            continue
        exp = expected_output(c)
        approved = set() if v.reason == REASON_SCHEMA else set(v.approved_ids)
        for pid, e in exp.by_id.items():
            props += 1
            got = pid in approved
            correct = got == e.approved
            ok += correct
            if e.approved:
                should_app += 1
                fr += not got
            else:
                should_rej += 1
                fa += got
            for t in tags.get(pid, []):
                by_tag[t][0] += correct
                by_tag[t][1] += 1
    row.update({"n_props": props, "prop_acc": fmt_ci(ok, props),
                "false_approval": fmt_ci(fa, should_rej), "false_rejection": fmt_ci(fr, should_app)})
    tag_rows = [{"run": run, "tag": t, "n": k[1], "correct": k[0],
                 "acc": round(k[0] / k[1], 3) if k[1] else ""} for t, k in sorted(by_tag.items())]
    return row, tag_rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--cases", default=str(CASES_DIR))
    ap.add_argument("--results", default=str(RESULTS_DIR))
    a = ap.parse_args(argv)
    cases_dir, results_dir = Path(a.cases), Path(a.results)
    cases = load_cases(cases_dir)
    if not cases:
        print("no hay casos en", cases_dir, file=sys.stderr)
        return 1
    tags = load_tags(cases_dir)
    rows, tag_rows = [], []
    for run in a.runs:
        if not (results_dir / run).is_dir():
            print(f"[{run}] no existe results/{run}/", file=sys.stderr)
            continue
        r, t = run_metrics(run, cases, results_dir, tags)
        rows.append(r)
        tag_rows += t
    split = cases_dir.name
    write_csv(results_dir / f"metrics_{split}.csv", rows)
    if tag_rows:
        write_csv(results_dir / f"metrics_{split}_tags.csv", tag_rows)
    print(f"== {split}: por caso y por propiedad (IC de Wilson 95 %) ==")
    print_table(rows, ["run", "n_cases", "e1_strict", "full_correct", "exact_match", "n_props",
                       "prop_acc", "false_approval", "false_rejection"])
    if tag_rows:
        print(f"\n== {split}: exactitud por fenómeno (propiedades con ese tag) ==")
        runs = [r["run"] for r in rows]
        table = defaultdict(dict)
        for t in tag_rows:
            table[t["tag"]]["tag"] = t["tag"]
            table[t["tag"]]["n"] = t["n"]
            table[t["tag"]][t["run"]] = f"{t['correct']}/{t['n']}"
        print_table(list(table.values()), ["tag", "n", *runs])
    return 0


if __name__ == "__main__":
    sys.exit(main())
