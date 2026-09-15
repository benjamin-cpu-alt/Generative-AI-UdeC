"""Estrategias evaluadas para la E2, de menor a mayor intervención. Todas reciben
exactamente el mismo caso (perfil + catálogo crudo) y producen el mismo JSON
estricto de la E1, así que `evaluate.py` las juzga con el mismo criterio.

  baseline    prompting directo, una llamada (run_model.py; se incluye aquí solo para
              que demo.py compare en la misma corrida).
  cot         prompting estructurado: misma llamada única, pero el prompt impone un
              procedimiento por pasos (presupuesto primero, luego el resto). Es la
              hipótesis literal de la E1 para Phi-4-mini. Sin herramientas.
  decomp_llm  descomposición SIN herramientas: paso 1 extracción por propiedad con
              JSON Schema; paso 2 el propio LLM convierte UF→CLP, compara y arma el
              JSON final (con decodificación restringida). Aísla cuánto aporta
              quitar el cálculo del modelo.
  tools       descomposición + herramientas (solución E2): paso 1 igual; paso 2 en
              Python (normalize.py + constraints.py). El LLM nunca calcula ni decide.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import prompt as base_prompt
from .constraints import Decision, build_output, decide
from .extract import Facts, default_options, extract_facts, ollama_chat
from .schema import Case

MODES = ("baseline", "cot", "decomp_llm", "tools")


@dataclass
class Trace:
    """Todo lo necesario para reconstruir la respuesta y explicar un fallo."""
    case_id: str
    mode: str
    model: str
    output_text: str                       # lo que se guarda en results/<run>/<case>.txt
    facts: Dict[str, Dict] = field(default_factory=dict)      # por propiedad (modos decomp)
    decisions: Dict[str, Dict] = field(default_factory=dict)  # por propiedad (modo tools)
    calls: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    wall_s: float = 0.0
    errors: List[str] = field(default_factory=list)


# ------------------------------------------------------------------ cot ----

PROCEDURE = (
    "PROCEDIMIENTO OBLIGATORIO (hazlo internamente, en este orden, propiedad por propiedad):\n"
    "Paso 1. Precio: si viene en UF, multiplica por el valor de la UF de hoy y escribe el resultado "
    "exacto en CLP. Compara con el presupuesto máximo. Ignora frases como 'bajo el presupuesto', "
    "'negociable' o 'según el tasador': solo vale el número.\n"
    "Paso 2. Dormitorios reales: escritorios, loggias o salas 'convertibles' NO son dormitorios.\n"
    "Paso 3. Distancia: la menor entre metro y paradero troncal, en metros; los minutos caminando no cuentan.\n"
    "Paso 4. Mascotas: debe aceptar explícitamente la especie y el peso del comprador.\n"
    "Paso 5. Estacionamiento: solo propio o asignado.\n"
    "Paso 6. Si falló CUALQUIER paso, va a rejected. Si pasó todos, calcula roi_pct y va a approved_matches.\n"
    "Paso 7. Ordena approved_matches por comuna preferida y luego ROI descendente."
)


def render_cot_prompt(case: Case) -> str:
    base = base_prompt.render_prompt(case)
    # Inserta el procedimiento justo antes de la TAREA, sin cambiar esquema ni regla de formato.
    marker = "TAREA:"
    i = base.rfind(marker)
    return base[:i] + PROCEDURE + "\n\n" + base[i:]


def _single_call(model: str, prompt_text: str, options: Dict, timeout: int) -> Dict:
    """Llamada única estilo baseline (/api/generate) para baseline y cot."""
    import urllib.request
    body = json.dumps({"model": model, "prompt": prompt_text, "stream": False,
                       "options": options, "keep_alive": "15m"}).encode("utf-8")
    req = urllib.request.Request("http://localhost:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_single(case: Case, model: str, mode: str, options: Dict, timeout: int = 600) -> Trace:
    text = base_prompt.render_prompt(case) if mode == "baseline" else render_cot_prompt(case)
    t0 = time.time()
    r = _single_call(model, text, options, timeout)
    return Trace(case_id=case.id, mode=mode, model=model, output_text=r.get("response", ""),
                 calls=1, prompt_tokens=r.get("prompt_eval_count") or 0,
                 output_tokens=r.get("eval_count") or 0, wall_s=round(time.time() - t0, 2))


# --------------------------------------------------------- decomposición ----

def extract_all(case: Case, model: str, options: Dict, timeout: int, prompt_version: str = "v1") -> Dict[str, Facts]:
    return {p.id: extract_facts(model, p.id, p.text, options, timeout, prompt_version) for p in case.properties}


def run_tools(case: Case, model: str, options: Optional[Dict] = None, timeout: int = 120,
              prompt_version: str = "v1") -> Trace:
    options = options or default_options()
    t0 = time.time()
    facts = extract_all(case, model, options, timeout, prompt_version)
    decisions: List[Decision] = [
        decide(pid, f, case.hard_constraints, case.soft_constraints, case.uf_value)
        for pid, f in facts.items()
    ]
    out = build_output(decisions)
    tr = Trace(case_id=case.id, mode=f"tools/{prompt_version}", model=model,
               output_text=json.dumps(out, ensure_ascii=False, indent=2),
               facts={k: v.to_dict() for k, v in facts.items()},
               decisions={d.id: {"price_clp": d.price_clp, "roi_pct": d.roi_pct,
                                 "failed_constraints": d.failed_constraints,
                                 "preferred_location": d.preferred_location,
                                 "notes": d.notes} for d in decisions},
               calls=len(facts), wall_s=round(time.time() - t0, 2))
    tr.prompt_tokens = sum(f.prompt_tokens for f in facts.values())
    tr.output_tokens = sum(f.output_tokens for f in facts.values())
    tr.errors = [f"{k}: {v.error}" for k, v in facts.items() if v.error]
    return tr


OUTPUT_SCHEMA: Dict = {
    "type": "object",
    "properties": {
        "approved_matches": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "price_clp": {"type": "integer"},
                           "roi_pct": {"type": ["number", "null"]}},
            "required": ["id", "price_clp", "roi_pct"]}},
        "rejected": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": {"type": "string"},
                           "failed_constraints": {"type": "array", "items": {"type": "string"}}},
            "required": ["id", "failed_constraints"]}},
    },
    "required": ["approved_matches", "rejected"],
}

FACT_KEYS = ("location", "bedrooms", "price_text", "rent_text", "distance_metro_text",
             "distance_bus_text", "pets_policy", "pets_species", "pets_max_kg", "parking")


def run_decomp_llm(case: Case, model: str, options: Optional[Dict] = None, timeout: int = 300,
                   prompt_version: str = "v1") -> Trace:
    """Extracción igual que `tools`, pero la aritmética y la lógica las hace el LLM."""
    options = options or default_options()
    t0 = time.time()
    facts = extract_all(case, model, options, timeout, prompt_version)
    clean = {pid: {k: getattr(f, k) for k in FACT_KEYS} for pid, f in facts.items()}
    uf = f"{int(case.uf_value):,}".replace(",", ".")
    user = "\n\n".join([
        f"VALOR UF HOY: ${uf} CLP",
        base_prompt.render_profile(case),
        base_prompt.render_soft(case),
        "HECHOS YA EXTRAÍDOS DE CADA PROPIEDAD (JSON, campos *_text copiados del aviso):\n"
        + json.dumps(clean, ensure_ascii=False, indent=1),
        "TAREA: Con estos hechos, evalúa cada propiedad contra las 5 Hard Constraints "
        "(convierte UF a CLP con la UF de hoy; distancia = la menor entre metro y paradero; "
        "mascotas requiere política 'permitidas', especie compatible y peso dentro del límite; "
        "estacionamiento solo propio o asignado). Para las aprobadas calcula price_clp y "
        "roi_pct = (arriendo × 12) / price_clp × 100 con dos decimales, y ordénalas según las "
        "Soft Constraints. Responde solo con el JSON.",
    ])
    opts = dict(options, num_ctx=4096, num_predict=1024)
    r = ollama_chat(model, base_prompt.SYSTEM, user, opts, fmt=OUTPUT_SCHEMA, timeout=timeout)
    out_text = r.get("message", {}).get("content", "")
    tr = Trace(case_id=case.id, mode="decomp_llm", model=model, output_text=out_text,
               facts={k: v.to_dict() for k, v in facts.items()},
               calls=len(facts) + 1, wall_s=round(time.time() - t0, 2))
    tr.prompt_tokens = sum(f.prompt_tokens for f in facts.values()) + (r.get("prompt_eval_count") or 0)
    tr.output_tokens = sum(f.output_tokens for f in facts.values()) + (r.get("eval_count") or 0)
    tr.errors = [f"{k}: {v.error}" for k, v in facts.items() if v.error]
    return tr


def run_case(case: Case, model: str, mode: str, timeout: int = 600, prompt_version: str = "v1") -> Trace:
    if mode == "tools":
        return run_tools(case, model, timeout=min(timeout, 120), prompt_version=prompt_version)
    if mode == "decomp_llm":
        return run_decomp_llm(case, model, timeout=min(timeout, 300), prompt_version=prompt_version)
    if mode in ("baseline", "cot"):
        # Mismas opciones que scripts/run_baselines.sh para phi4/granite.
        return run_single(case, model, mode,
                          {"temperature": 0.0, "seed": 0, "num_ctx": 4096, "num_predict": 2048}, timeout)
    raise ValueError(f"modo desconocido: {mode} (usa {'|'.join(MODES)})")
