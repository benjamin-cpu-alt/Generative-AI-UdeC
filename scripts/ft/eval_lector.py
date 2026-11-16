"""Mide al Lector SOLO (una llamada por aviso, sin Verificador ni Decisor), con cualquier modelo
de Ollama. Sirve para elegir el checkpoint en dev y para comparar base contra fine-tuning en el
nivel del agente, antes de mirar el sistema completo.

Para cada aviso: Lector -> `anclar` -> hechos, y por campo se compara con el `truth`:
  directo      `anclar` lee el dato verdadero desde el fragmento que copió el Lector
  con_duda     no lo lee, pero `dudas` marca el campo: lo verá el Verificador
  silencioso   queda mal leído y nadie lo revisa
Además cuenta los campos que el Lector deja sin copiar aunque el dato está en el aviso
(`origen lector`, la misma definición de scripts/atribucion_e3.py).

Sobre la validación sintética (--valid) mide además la copia exacta contra la etiqueta.

  PYTHONPATH=src python3 scripts/ft/eval_lector.py --model phi4-mini:latest --split hard_dev
  PYTHONPATH=src python3 scripts/ft/eval_lector.py --model phi4-mini-lector-ft --split hard_dev
  PYTHONPATH=src python3 scripts/ft/eval_lector.py --model phi4-mini-lector-ft --valid
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from agents import llm, tools  # noqa: E402
from agents.orchestrator import mensaje_lector  # noqa: E402
from agents.verdad import CAMPOS, fragmento_trae_dato, igual, leido, marcado, verdad  # noqa: E402
from matcher.grounding import SPAN_FIELDS  # noqa: E402
from matcher.schema import Case  # noqa: E402

OUT = ROOT / "results" / "lector_eval"


def avisos(split: str):
    for f in sorted((ROOT / "data" / "cases" / split).glob("*.json")):
        case = Case.load(f)
        for prop in case.properties:
            yield case, prop, None


def avisos_valid():
    for line in (ROOT / "data" / "ft_lector" / "ejemplos.jsonl").read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["split"] != "valid":
            continue
        case = Case.from_dict({"id": "valid", "uf_value": e["uf"],
                               "hard_constraints": dict(presupuesto_max_clp=1, mascota_especie=None, mascota_kg=None,
                                                        distancia_max_transporte_m=1, dormitorios_min=1,
                                                        estacionamiento_requerido=True),
                               "properties": [{"id": e["id"], "text": e["texto"], "truth": e["truth"]}]})
        yield case, case.properties[0], e["spans"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--split")
    ap.add_argument("--valid", action="store_true", help="la validación sintética de data/ft_lector/")
    ap.add_argument("--lector", default="v1")
    ap.add_argument("--num-ctx", type=int, default=2048)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--etiqueta", help="nombre del archivo de salida (por defecto, el del modelo)")
    a = ap.parse_args(argv)
    if bool(a.split) == a.valid:
        ap.error("usa --split o --valid")
    prompt = llm.load_prompt("lector", a.lector)
    fuente = list(avisos_valid() if a.valid else avisos(a.split))[: a.limit]
    estado, origen, exacto, filas = Counter(), Counter(), Counter(), []
    con_dudas = n_dudas = 0
    t0 = time.time()
    for i, (case, prop, gold) in enumerate(fuente, 1):
        user, schema = mensaje_lector(prompt, prop.id, prop.text)
        obj, meta = llm.call(a.model, prompt["system"], user, schema, num_ctx=a.num_ctx)
        spans = {k: obj.get(k) for k in schema["properties"]}
        h, _ = tools.anclar(spans, prop.text, case.uf_value, "g3")
        d = tools.dudas(h, prop.text)
        T, L = verdad(prop, case), leido(h)
        fila = {"aviso": prop.id, "spans": spans, "campos": {}}
        for c in CAMPOS:
            if igual(c, L[c], T[c], case.uf_value):
                e = "directo"
            else:
                e = "con_duda" if marcado(c, d) else "silencioso"
                if not fragmento_trae_dato(c, spans, T[c], case.uf_value):
                    origen[c] += 1
            estado[(c, e)] += 1
            fila["campos"][c] = e
        if gold is not None:
            for k in SPAN_FIELDS:
                exacto[k] += spans.get(k) == gold.get(k)
            exacto["todos"] += all(spans.get(k) == gold.get(k) for k in gold)
        con_dudas += bool(d)
        n_dudas += len(d)
        filas.append(fila)
        if i % 20 == 0:
            print(f"  {i}/{len(fuente)} avisos, {time.time() - t0:.0f} s", flush=True)

    n = len(fuente)
    res = {"modelo": a.model, "prompt": f"lector/{a.lector}", "set": "valid" if a.valid else a.split, "avisos": n,
           "por_campo": {c: {e: estado[(c, e)] for e in ("directo", "con_duda", "silencioso")} for c in CAMPOS},
           "campos_directos": sum(estado[(c, "directo")] for c in CAMPOS),
           "campos_con_duda": sum(estado[(c, "con_duda")] for c in CAMPOS),
           "campos_silenciosos": sum(estado[(c, "silencioso")] for c in CAMPOS),
           "campos_total": n * len(CAMPOS),
           "errores_origen_lector": dict(origen), "errores_origen_lector_total": sum(origen.values()),
           "avisos_que_van_al_verificador": con_dudas, "dudas_marcadas": n_dudas,
           "segundos": round(time.time() - t0)}
    if exacto:
        res["copia_exacta"] = {k: exacto[k] for k in list(SPAN_FIELDS) + ["todos"]}
    OUT.mkdir(parents=True, exist_ok=True)
    nombre = (a.etiqueta or a.model.replace(":", "_").replace("/", "_")) + f"_{res['set']}"
    (OUT / f"{nombre}.json").write_text(json.dumps({**res, "detalle": filas}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
