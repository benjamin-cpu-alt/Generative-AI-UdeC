"""Re-decide una corrida `tools` YA EXISTENTE pasando sus hechos por grounding.py,
sin llamar al modelo. Mide cuánto de la mejora de v5 viene de la CAPA DE HERRAMIENTAS
(anclaje + parsers) y cuánto requiere re-extraer (las tres preguntas de mascotas).

Los traces v1 no tienen cláusulas copiadas para dormitorios/estacionamiento/mascotas,
así que aquí la cláusula se toma del aviso completo: equivale a suponer que el modelo
localiza la frase correcta. Por eso el resultado es una COTA SUPERIOR de v5 sin
re-extraer, y así debe reportarse. Los errores de especies de v1 se conservan tal cual
(no hay respuestas cerradas en esos traces), lo que muestra el residuo que v5 ataca
con el cambio de esquema.

Uso:
  python -m matcher.reground --run tools_phi4_v1 --out tools_phi4_v1_reground
  python -m matcher.evaluate --runs tools_phi4_v1 tools_phi4_v1_reground
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from . import grounding
from .constraints import Decision, build_output, decide
from .extract import Facts
from .schema import Case

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases"
RESULTS_DIR = ROOT / "results"

_SENT_RE = re.compile(r"[^.]*\b(?:%s)[^.]*\.?")


def _sentence_with(text: str, words: str) -> Optional[str]:
    m = re.search(_SENT_RE.pattern % words, text, re.IGNORECASE)
    return m.group(0).strip() if m else None


def _answers_from_v1(f: Dict) -> Dict[str, str]:
    """pets_policy/pets_species de v1 -> las tres respuestas cerradas de v5 (sin corregir nada)."""
    policy, species = f.get("pets_policy"), list(f.get("pets_species") or [])
    if policy == "permitidas":
        if not species:
            return {"acepta_mascotas": "si", "acepta_perros": "si", "acepta_gatos": "si"}
        return {"acepta_mascotas": "si",
                "acepta_perros": "si" if "perro" in species else "no_dice",
                "acepta_gatos": "si" if "gato" in species else "no_dice"}
    if policy == "no_permitidas":
        return {"acepta_mascotas": "no", "acepta_perros": "no", "acepta_gatos": "no"}
    return {"acepta_mascotas": "no_dice", "acepta_perros": "no_dice", "acepta_gatos": "no_dice"}


def spans_from_v1(f: Dict, text: str) -> Dict:
    return {
        "location_text": f.get("location"),
        "bedrooms_text": text,                                   # cláusula = aviso completo
        "price_text": f.get("price_text"),
        "rent_text": f.get("rent_text"),
        "distance_metro_text": f.get("distance_metro_text"),
        "distance_bus_text": f.get("distance_bus_text"),
        "parking_text": _sentence_with(text, "estacionamiento|parking|aparc"),
        "pets_text": _sentence_with(text, "mascota|pet friendly|gatos|perros|kg"),
        **_answers_from_v1(f),
    }


def reground_case(case: Case, trace: Dict, version: str = grounding.DEFAULT_VERSION) -> Dict:
    facts: Dict[str, Facts] = {}
    for p in case.properties:
        f = trace["facts"].get(p.id) or {}
        spans = f.get("spans") or spans_from_v1(f, p.text)        # traces v5 ya traen spans
        kwargs, warnings = grounding.facts_from_spans(spans, p.text, version)
        facts[p.id] = Facts(**kwargs, spans=spans, warnings=warnings, raw=f.get("raw", ""))
    decisions: List[Decision] = [
        decide(pid, fx, case.hard_constraints, case.soft_constraints, case.uf_value)
        for pid, fx in facts.items()
    ]
    return {
        "output": build_output(decisions),
        "facts": {k: v.to_dict() for k, v in facts.items()},
        "decisions": {d.id: {"price_clp": d.price_clp, "roi_pct": d.roi_pct,
                             "failed_constraints": d.failed_constraints,
                             "preferred_location": d.preferred_location, "notes": d.notes}
                      for d in decisions},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="corrida tools existente (con .trace.json)")
    ap.add_argument("--out", required=True, help="nombre de la corrida re-decidida en results/")
    ap.add_argument("--split", default="test")
    ap.add_argument("--grounding", default=grounding.DEFAULT_VERSION, choices=grounding.VERSIONS)
    a = ap.parse_args(argv)

    src, out = RESULTS_DIR / a.run, RESULTS_DIR / a.out
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for path in sorted((CASES_DIR / a.split).glob("*.json")):
        case = Case.load(path)
        tp = src / f"{case.id}.trace.json"
        if not tp.exists():
            continue
        r = reground_case(case, json.loads(tp.read_text(encoding="utf-8")), a.grounding)
        (out / f"{case.id}.txt").write_text(json.dumps(r["output"], ensure_ascii=False, indent=2), encoding="utf-8")
        meta_src = src / f"{case.id}.meta.json"
        meta = json.loads(meta_src.read_text(encoding="utf-8")) if meta_src.exists() else {}
        meta.update({"run": a.out, "mode": f"reground/{a.run}/{a.grounding}", "source_run": a.run,
                     "grounding_version": a.grounding,
                     "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")})
        (out / f"{case.id}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / f"{case.id}.trace.json").write_text(
            json.dumps({"facts": r["facts"], "decisions": r["decisions"]}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        n += 1
    print(f"listo: {n} casos re-decididos en results/{a.out}/ (sin llamadas al modelo)")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
