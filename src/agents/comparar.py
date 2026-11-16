"""El Lector base y el Lector con fine-tuning sobre EL MISMO aviso, en vivo (E4, video).

Los dos reciben el mismo mensaje (mismo `system`, mismo aviso, mismo JSON Schema); lo único que
cambia es el modelo: `phi4-mini:latest` contra `phi4-mini-lector-ft` (el mismo phi4-mini con el
adaptador LoRA). Después de cada Lector se muestra lo que hace el resto del sistema con su
salida: la herramienta `anclar` la convierte en hechos y `dudas` marca qué campos tendría que
revisar el Verificador.

  python -m agents.comparar --split hard_dev --caso hd_02 --aviso HD-0201
  python -m agents.comparar --split real_e3 --caso real_b1_006 --aviso REAL-18 --guardar results/demo_e4
  python -m agents.comparar --texto "Ñuñoa. Depto 3D 2B, 112 palos, estac. propio, metro a 600 m"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from matcher.schema import Case

from . import llm, tools
from .orchestrator import mensaje_lector
from .show import BOLD, DIM, RESET

ROOT = Path(__file__).resolve().parents[2]
BASE, FT = "phi4-mini:latest", "phi4-mini-lector-ft"


def leer(modelo: str, prompt: Dict[str, str], pid: str, texto: str, uf: float) -> Dict:
    """Una llamada al Lector con `modelo` y lo que las herramientas hacen con su salida."""
    user, schema = mensaje_lector(prompt, pid, texto)
    t0 = time.time()
    obj, meta = llm.call(modelo, prompt["system"], user, schema)
    spans = {k: obj.get(k) for k in schema["properties"]}
    hechos, _ = tools.anclar(spans, texto, uf, "g3")
    return {"modelo": modelo, "spans": spans, "hechos": {c: tools.lectura(c, hechos) for c in tools.CAMPOS},
            "dudas": tools.dudas(hechos, texto), "segundos": round(time.time() - t0, 1), "error": meta.get("error")}


def mostrar(r: Dict, otro: Optional[Dict], color: bool) -> None:
    b, d, x = (BOLD, DIM, RESET) if color else ("", "", "")
    print(f"\n{b}AGENTE Lector{x}  modelo: {b}{r['modelo']}{x}  ({r['segundos']} s)"
          + (f"  ERROR {r['error']}" if r["error"] else ""))
    print("  mensaje del Lector → HERRAMIENTA anclar (fragmentos copiados del aviso):")
    for k, v in r["spans"].items():
        if k.startswith("acepta_"):
            continue
        cambia = otro is not None and otro["spans"].get(k) != v
        print(f"    {'≠' if cambia else ' '} {k:<20} {json.dumps(v, ensure_ascii=False)}")
    print("      respuestas cerradas: " + ", ".join(f"{k}={r['spans'][k]}" for k in r["spans"] if k.startswith("acepta_")))
    print("  HERRAMIENTA anclar → hechos (código, sin modelo):")
    for c, v in r["hechos"].items():
        duda = r["dudas"].get(c)
        marca = f"   ⚠ va al Verificador: {duda.split(' (mira')[0]}" if duda else "   ✔"
        print(f"      {c:<16} {v}{d}{marca}{x}")
    n = len(r["dudas"])
    print(f"  → {n} campo(s) con duda: " + ("el aviso pasa por el Verificador" if n else "el aviso va directo al Decisor"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split")
    ap.add_argument("--caso")
    ap.add_argument("--aviso")
    ap.add_argument("--texto", help="un aviso escrito a mano, en vez de uno de un caso")
    ap.add_argument("--uf", type=float, default=39_500)
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--ft", default=FT)
    ap.add_argument("--lector", default="v1", help="versión del prompt (la misma para los dos modelos)")
    ap.add_argument("--guardar", help="carpeta donde dejar el JSON de la comparación")
    a = ap.parse_args(argv)

    if a.texto:
        pid, texto, uf = "AVISO-1", a.texto, a.uf
    else:
        if not (a.split and a.caso and a.aviso):
            ap.error("usa --texto, o --split, --caso y --aviso")
        case = Case.load(ROOT / "data" / "cases" / a.split / f"{a.caso}.json")
        prop = next(p for p in case.properties if p.id == a.aviso)
        pid, texto, uf = prop.id, prop.text, case.uf_value
    prompt = llm.load_prompt("lector", a.lector)
    color = sys.stdout.isatty()
    print(f"Aviso {pid} (los dos modelos reciben exactamente este mensaje, con el prompt lector/{a.lector}):\n  «{texto}»")
    base = leer(a.base, prompt, pid, texto, uf)
    mostrar(base, None, color)
    ft = leer(a.ft, prompt, pid, texto, uf)
    mostrar(ft, base, color)
    distintos = [k for k in base["spans"] if base["spans"][k] != ft["spans"][k]]
    print(f"\nCampos donde cambia el fragmento copiado: {', '.join(distintos) if distintos else 'ninguno'}")
    print(f"Campos que tendría que revisar el Verificador: base {len(base['dudas'])}, con fine-tuning {len(ft['dudas'])}")
    if a.guardar:
        out = Path(a.guardar)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"comparar_{pid}.json").write_text(
            json.dumps({"aviso": pid, "texto": texto, "prompt": f"lector/{a.lector}", "base": base, "ft": ft},
                       ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
