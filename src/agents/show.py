"""Muestra una traza (results/<run>/<case>.trace.jsonl) como conversación entre agentes.
Es lo que se ve en el video: cada mensaje con su emisor, su destino y su contenido.

  python -m agents.show results/agents_v1_real_e3/real_b2_003.trace.jsonl
  python -m agents.show <traza> --aviso REAL-23        # solo los mensajes de un aviso
  python -m agents.show <traza> --pausa 0.6            # mensaje a mensaje (para grabar)
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
import time

COLOR = {"Lector": "\033[36m", "Verificador": "\033[33m", "Decisor": "\033[35m",
         "orquestador": "\033[90m", "salida": "\033[32m"}
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"


def _who(name: str, color: bool) -> str:
    if not color:
        return name
    c = COLOR.get(name, "\033[34m" if name.startswith("herramienta") else "")
    return f"{c}{BOLD}{name}{RESET}"


def resumen(m: dict) -> str:
    c, t = m["contenido"], m["tipo"]
    if t == "inicio":
        return f"avisos: {', '.join(c['avisos'])}"
    if t in ("spans", "relectura"):
        return "\n".join(f"{k}: {v!r}" for k, v in c.items() if v is not None)
    if t == "hechos":
        h = c.get("hechos", c)
        extra = c.get("avisos_anclaje") if isinstance(c, dict) and "hechos" in c else None
        s = " | ".join(f"{k}={v}" for k, v in h.items())
        return s + (f"\n(anclaje: {'; '.join(extra)})" if extra else "")
    if t in ("revisar", "retro", "consulta"):
        if not c:
            return "(sin revisiones)"
        return "\n".join(f"{r.get('campo')}: {r.get('accion').upper()}"
                         + (f"  valor={r.get('valor')!r}" if r.get("valor") else "")
                         + (f"  evidencia={r.get('evidencia')!r}" if r.get("evidencia") else "") for r in c)
    if t == "resultado":
        if c["ok"]:   # si el código leyó otro valor en la evidencia, se muestra cuál
            veredicto = "ACEPTA" + (f" — {c['motivo'][4:]}" if c["motivo"].startswith("ok: ") else "")
        else:
            veredicto = "RECHAZA: " + c["motivo"]
        return f"{c['campo']} = {c['valor']!r} desde {c['evidencia']!r} -> {veredicto}"
    if t == "evaluacion":
        out = []
        for pid, est in c.items():
            malas = [f"{k}:{v}" for k, v in est.items() if v in ("falla", "no_verificable")]
            dudas = [f"{k} sin confirmar" for k, v in est.items() if v == "sin_confirmar"]
            out.append(f"{pid}: " + (", ".join(malas) if malas else
                                     "APRUEBA" + (f" ({', '.join(dudas)}: al final del orden)" if dudas else "")))
        return "\n".join(out)
    if t in ("cerrar", "consultar"):
        return t.upper() + "".join(f"\n  {q['id']} · {q['campo']}: {q['motivo']}" for q in c["consultas"])
    return json.dumps(c, ensure_ascii=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("traza")
    ap.add_argument("--aviso")
    ap.add_argument("--pausa", type=float, default=0.0)
    ap.add_argument("--sin-color", action="store_true")
    a = ap.parse_args(argv)
    color = not a.sin_color and sys.stdout.isatty()
    for line in open(a.traza, encoding="utf-8"):
        m = json.loads(line)
        if a.aviso and m.get("aviso") not in (None, a.aviso):
            continue
        head = f"{m['paso']:>3} {_who(m['de'], color)} → {_who(m['para'], color)}  [{m['tipo']}]"
        if m.get("aviso"):
            head += f"  {DIM if color else ''}{m['aviso']}{RESET if color else ''}"
        print(head)
        body = resumen(m)
        for ln in body.splitlines():
            print(textwrap.fill(ln, 110, initial_indent="      ", subsequent_indent="        "))
        if a.pausa:
            time.sleep(a.pausa)
    return 0


if __name__ == "__main__":
    sys.exit(main())
