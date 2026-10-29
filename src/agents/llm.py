"""Prompts versionados (prompts/<agente>/<versión>.md) y la llamada al modelo.

Los tres agentes usan el mismo modelo (phi4-mini, 3.8B) por Ollama, con temperatura 0 y
semilla fija. Con `esquema=True` la salida se restringe a un JSON Schema (`format` de
Ollama); con `esquema=False` (ablación −esquema) el modelo escribe libre y se busca el
primer objeto JSON en el texto.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
from pathlib import Path
from typing import Dict, Optional, Tuple

from matcher.extract import ollama_chat

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT / "prompts"
_SECTION = re.compile(r"^=== (\w+) ===$", re.M)


def load_prompt(agent: str, version: str = "v1") -> Dict[str, str]:
    """Secciones de prompts/<agent>/<version>.md (`=== nombre ===`); lo anterior a la
    primera sección es documentación y no se envía."""
    text = (PROMPTS_DIR / agent / f"{version}.md").read_text(encoding="utf-8")
    parts = _SECTION.split(text)
    return {parts[i]: parts[i + 1].strip("\n") for i in range(1, len(parts), 2)}


def render(template: str, **kw) -> str:
    # Reemplazo literal: los prompts pueden contener llaves que no son variables.
    for k, v in kw.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def first_json(text: str) -> Optional[Dict]:
    """Primer objeto JSON del texto (para la ablación sin esquema)."""
    text = re.sub(r"```(?:json)?", "", text or "")
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        return obj if isinstance(obj, dict) else None
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def call(model: str, system: str, user: str, schema: Optional[Dict], esquema: bool = True,
         num_ctx: int = 2048, num_predict: int = 256, timeout: int = 180) -> Tuple[Dict, Dict]:
    """Devuelve (objeto JSON o {}, metadatos de la llamada)."""
    opts = {"temperature": 0.0, "seed": 0, "num_ctx": num_ctx, "num_predict": num_predict}
    t0 = time.time()
    meta = {"prompt_tokens": 0, "output_tokens": 0, "wall_s": 0.0, "raw": "", "error": None}
    try:
        if esquema:
            r = ollama_chat(model, system, user, opts, fmt=schema, timeout=timeout)
        else:
            r = ollama_chat(model, system, user + "\n\nResponde solo con un objeto JSON.", opts,
                            timeout=timeout)
        raw = r.get("message", {}).get("content", "")
        meta.update(prompt_tokens=r.get("prompt_eval_count") or 0, output_tokens=r.get("eval_count") or 0,
                    raw=raw)
        obj = json.loads(raw) if esquema else first_json(raw)
        if not isinstance(obj, dict):
            obj, meta["error"] = {}, "salida sin objeto JSON"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        obj, meta["error"] = {}, str(e)
    meta["wall_s"] = round(time.time() - t0, 2)
    return obj, meta
