"""Muestra una traza (results/<run>/<case>.trace.jsonl) como conversación entre agentes.
Es lo que se ve en el video: cada mensaje con su emisor, su destino y su contenido.

  python -m agents.show results/agents_v1_real_e3/real_b2_003.trace.jsonl
  python -m agents.show <traza> --aviso REAL-23        # solo los mensajes de un aviso
  python -m agents.show <traza> --pausa 0.6            # mensaje a mensaje (para grabar)
  python -m agents.show <traza> --pasos 12-14,28       # solo esos pasos (para que quepan en pantalla)
  python -m agents.show <traza> --roles                # marca AGENTE / HERRAMIENTA y cada vuelta de bucle

Con --roles cada mensaje dice qué es quien lo envía y quien lo recibe:
  AGENTE        llama al modelo y DECIDE qué pasa después (Lector, Verificador, Decisor)
  HERRAMIENTA   función de Python, sin modelo: calcula o valida, nunca decide (anclar, comprobar,
                evaluar, ordenar)
  orquestador   el bucle de Python que entrega cada mensaje y corta por presupuesto
y cada vez que un agente le devuelve trabajo a otro agente se anuncia la vuelta del bucle
(↺ relectura, ↺ reintento, ↺ consulta) con su número y su máximo.
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


AGENTES = ("Lector", "Verificador", "Decisor")
LEYENDA = """AGENTE       llama al modelo (phi4-mini) y DECIDE el siguiente paso: Lector · Verificador · Decisor
HERRAMIENTA  función de Python, sin modelo; calcula o valida, no decide: anclar · comprobar · evaluar · ordenar
orquestador  bucle de Python: entrega cada mensaje a su destino y corta los bucles por presupuesto
↺            un agente le devuelve trabajo a otro agente (bucle entre agentes), con su vuelta y su máximo"""


def rol(nombre: str) -> str:
    if nombre in AGENTES:
        return "AGENTE "
    if nombre.startswith("herramienta:"):
        return "HERRAMIENTA "
    return ""


class Bucles:
    """Reconoce, mensaje a mensaje, cada vuelta de un bucle entre agentes y la numera.
    Los máximos salen de la configuración que el orquestador escribe en el primer mensaje."""

    def __init__(self):
        self.max = {"relectura": 2, "reintento": 1, "consulta": 1}
        self.n = {}
        self.ronda_consulta = 0
        self.en_consulta = False

    def anotar(self, m: dict):
        de, para, tipo, av = m["de"], m["para"], m["tipo"], m.get("aviso")
        if tipo == "inicio":
            c = m["contenido"].get("config", {})
            self.max = {"relectura": c.get("max_relecturas", 2), "reintento": c.get("max_retro", 1),
                        "consulta": c.get("max_consultas", 1)}
            return None
        if de == "Verificador" and para == "Lector":
            k = self._mas(("relectura", av))
            return (f"↺ BUCLE DE RELECTURA, vuelta {k} de máx. {self.max['relectura']}: el Verificador (agente) "
                    f"decide `releer` y el aviso vuelve al Lector (agente)")
        if de == "Verificador" and tipo == "retro":
            k = self._mas(("reintento", av))
            return (f"↺ BUCLE DE REINTENTO, vuelta {k} de máx. {self.max['reintento']}: la herramienta comprobar "
                    f"rechazó la corrección y el Verificador (agente) decide de nuevo")
        if de == "Decisor" and para == "Verificador":
            self.ronda_consulta += 1
            return (f"↺ BUCLE DE CONSULTA, vuelta {self.ronda_consulta} de máx. {self.max['consulta']}: el Decisor "
                    f"(agente) decide `consultar` y el aviso vuelve al Verificador (agente)")
        if de == "orquestador" and tipo in ("sin_relectura", "sin_reintento", "cierre_por_presupuesto"):
            return "■ FIN DEL BUCLE por presupuesto: el orquestador no ejecuta otra vuelta"
        if de == "Decisor" and tipo == "cerrar":
            return "■ CONDICIÓN DE PARADA: el Decisor (agente) decide `cerrar`; la herramienta ordenar arma el JSON"
        return None

    def _mas(self, clave) -> int:
        self.n[clave] = self.n.get(clave, 0) + 1
        return self.n[clave]


def imprimir(m: dict, color: bool, bucles: "Bucles" = None) -> None:
    """Imprime un mensaje. Con `bucles` (opción --roles) marca el rol de emisor y receptor
    (AGENTE / HERRAMIENTA) y anuncia cada vuelta de un bucle entre agentes."""
    nota = bucles.anotar(m) if bucles else None
    if nota:
        print(f"    {BOLD if color else ''}{nota}{RESET if color else ''}")
    def nombre(n: str) -> str:      # con roles: «HERRAMIENTA comprobar», no «herramienta:comprobar»
        if not bucles:
            return _who(n, color)
        corto = n.split(":", 1)[1] if n.startswith("herramienta:") else n
        return rol(n) + (_who(n, color).replace(n, corto) if color else corto)
    de, para = nombre(m["de"]), nombre(m["para"])
    head = f"{m['paso']:>3} {de} → {para}  [{m['tipo']}]"
    if m.get("modelo"):
        head += f"  modelo: {BOLD if color else ''}{m['modelo']}{RESET if color else ''}"
    if m.get("aviso"):
        head += f"  {DIM if color else ''}{m['aviso']}{RESET if color else ''}"
    print(head)
    for ln in resumen(m).splitlines():
        print(textwrap.fill(ln, 110, initial_indent="      ", subsequent_indent="        "))
    sys.stdout.flush()


def pasos(spec: str) -> set:
    out = set()
    for parte in spec.split(","):
        a, _, b = parte.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("traza")
    ap.add_argument("--aviso")
    ap.add_argument("--pausa", type=float, default=0.0)
    ap.add_argument("--pasos", type=pasos)
    ap.add_argument("--sin-color", action="store_true")
    ap.add_argument("--roles", action="store_true",
                    help="marca AGENTE / HERRAMIENTA en cada mensaje y anuncia cada vuelta de bucle")
    a = ap.parse_args(argv)
    color = not a.sin_color and sys.stdout.isatty()
    bucles = Bucles() if a.roles else None
    if a.roles:
        print(LEYENDA + "\n")
    for line in open(a.traza, encoding="utf-8"):
        m = json.loads(line)
        if (a.aviso and m.get("aviso") not in (None, a.aviso)) or (a.pasos and m["paso"] not in a.pasos):
            if bucles:
                bucles.anotar(m)      # los mensajes ocultos también cuentan vueltas
            continue
        imprimir(m, color, bucles)
        if a.pausa:
            time.sleep(a.pausa)
    return 0


if __name__ == "__main__":
    sys.exit(main())
