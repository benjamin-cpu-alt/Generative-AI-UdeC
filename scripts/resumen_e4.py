"""Costo y bucles de cada corrida de agentes, contados desde las trazas (sin llamar al modelo).

Por corrida: llamadas a cada agente, avisos que no necesitaron al Verificador, vueltas de cada
bucle entre agentes (relectura, reintento, consulta), tokens y minutos. Es la tabla que muestra
qué cambia en la conversación entre agentes cuando solo cambia el Lector.

  PYTHONPATH=src python3 scripts/resumen_e4.py agents_v2_hard_test agents_ft_hard_test agents_ctrl_hard_test
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNAS = ("casos", "avisos", "llamadas", "Lector", "Verificador", "Decisor", "sin_dudas", "relecturas",
            "reintentos", "rondas_consulta", "consultas", "comprobar_rechaza", "tokens_entrada", "tokens_salida",
            "minutos", "errores")


def resumen(run: str) -> Counter:
    d, c = ROOT / "results" / run, Counter()
    for meta in sorted(d.glob("*.meta.json")):
        m = json.loads(meta.read_text(encoding="utf-8"))
        a = m.get("acciones", {})
        c["casos"] += 1
        c["llamadas"] += m["calls"]
        c["Lector"] += a.get("llamadas_lector", 0)
        c["Verificador"] += a.get("llamadas_verificador", 0)
        c["Decisor"] += a.get("llamadas_decisor", 0)
        c["sin_dudas"] += a.get("avisos_sin_dudas", 0)
        c["comprobar_rechaza"] += a.get("comprobar_rechaza", 0)
        c["tokens_entrada"] += m.get("prompt_tokens", 0)
        c["tokens_salida"] += m.get("output_tokens", 0)
        c["segundos"] += m.get("wall_s", 0)
        c["errores"] += len(m.get("errors", []))
        traza = meta.with_name(meta.name.replace(".meta.json", ".trace.jsonl"))
        for line in traza.read_text(encoding="utf-8").splitlines():
            t = json.loads(line)
            de, para, tipo = t["de"], t["para"], t["tipo"]
            if tipo == "inicio":
                c["avisos"] += len(t["contenido"].get("avisos", []))
            elif de == "Verificador" and para == "Lector":
                c["relecturas"] += 1
            elif de == "Verificador" and tipo == "retro":
                c["reintentos"] += 1
            elif de == "Decisor" and para == "Verificador":
                c["rondas_consulta"] += 1
                c["consultas"] += len(t["contenido"].get("consultas", [])) if isinstance(t["contenido"], dict) else 0
    c["minutos"] = round(c["segundos"] / 60, 1)
    return c


def main(argv=None) -> int:
    runs = (argv if argv is not None else sys.argv[1:])
    if not runs:
        print(__doc__)
        return 2
    filas = {r: resumen(r) for r in runs if (ROOT / "results" / r).is_dir()}
    ancho = max(len(r) for r in filas) + 2
    print(f"{'':<18}" + "".join(f"{r:>{ancho}}" for r in filas))
    for k in COLUMNAS:
        print(f"{k:<18}" + "".join(f"{filas[r][k]:>{ancho}}" for r in filas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
