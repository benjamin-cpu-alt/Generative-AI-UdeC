"""¿En qué agente se origina cada error de lectura? (evidencia para elegir el agente de la E4)

Reproduce cada traza de la E3 SIN Ollama: el orquestador se vuelve a ejecutar con un LLM
simulado que devuelve, en orden, las respuestas grabadas en `results/<run>/<caso>.trace.jsonl`.
Como las herramientas son deterministas, el estado interno (hechos por aviso) se reconstruye
exacto; el script lo comprueba comparando el JSON final con el `.txt` de la corrida.

Para cada (aviso, campo) compara contra `truth`:
  h0  = lo que quedó leído tras la PRIMERA pasada (Lector -> anclar)
  hF  = lo que llegó a `evaluar` al cerrar el caso

y atribuye cada error de hF:
  lector            el fragmento que copió el Lector no contiene el dato (null o fragmento
                    equivocado) y el dato sí está en el aviso
  anclar            el fragmento contiene el dato, pero la herramienta lo leyó mal
  ...y dice si alguien pudo arreglarlo:
  silencioso        `dudas` no marcó el campo: ningún agente lo revisó
  verificador       el campo se marcó y el Verificador no lo dejó bien
  roto_verificador  h0 estaba bien y hF no (lo rompió una corrección)

Uso:
  PYTHONPATH=src python3 scripts/atribucion_e3.py agents_v2_hard_dev agents_v2_hard_test
  PYTHONPATH=src python3 scripts/atribucion_e3.py agents_v2_hard_test --detalle
  PYTHONPATH=src python3 scripts/atribucion_e3.py agents_v2_hard_test agents_ft_hard_test agents_ctrl_hard_test   # E4
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agents import tools  # noqa: E402
from agents.verdad import CAMPOS, fragmento_trae_dato, igual, leido, marcado as fue_marcado, verdad  # noqa: E402
from agents.orchestrator import ACCIONES, Config, Sistema  # noqa: E402
from matcher import rules  # noqa: E402
from matcher.schema import Case  # noqa: E402

# Restricción que decide cada campo (comuna y arriendo solo afectan el orden y el ROI).
RESTRICCION = {"dormitorios": rules.C_BEDROOMS, "precio": rules.C_BUDGET, "distancia": rules.C_DISTANCE,
               "estacionamiento": rules.C_PARKING, "mascotas": rules.C_PETS}


class Replay(Sistema):
    """Sistema con las respuestas grabadas; guarda spans/h0/dudas de la primera pasada."""

    def __init__(self, cfg: Config, mensajes):
        self.cola = {"Lector": [], "Verificador": [], "Decisor": []}
        for m in mensajes:
            if m["de"] == "Lector" and m["tipo"] in ("spans", "relectura"):
                self.cola["Lector"].append(m["contenido"])
            elif m["de"] == "Verificador" and m["tipo"] in ACCIONES:
                self.cola["Verificador"].append({"revisiones": m["contenido"]})
            elif m["de"] == "Decisor" and m["tipo"] in ("cerrar", "consultar"):
                self.cola["Decisor"].append(m["contenido"]["propuesta"])
            elif m["de"] == "Decisor" and m["tipo"] == "json_final_sin_herramientas":
                self.cola["Decisor"].append(m["contenido"])
        super().__init__(cfg, llm_call=None)
        self.primera = {}
        self.final = {}

    def _llm(self, tr, agente, system, user, schema, **kw):
        tr.llamadas += 1
        return self.cola[agente].pop(0)

    def revisar_aviso(self, tr, prop, case, spans, h, marcar, modo="revisar", **extra):
        if modo == "revisar":
            self.primera[prop.id] = {"spans": dict(spans), "h0": copy.deepcopy(h), "dudas": dict(marcar)}
            self.final[prop.id] = h
        super().revisar_aviso(tr, prop, case, spans, h, marcar, modo, **extra)


def analizar(run: str, split: str):
    filas = []
    cases = {p.stem: Case.load(p) for p in sorted((ROOT / "data" / "cases" / split).glob("*.json"))}
    for tp in sorted((ROOT / "results" / run).glob("*.trace.jsonl")):
        cid = tp.name.replace(".trace.jsonl", "")
        case = cases[cid]
        mensajes = [json.loads(l) for l in tp.read_text(encoding="utf-8").splitlines() if l.strip()]
        cfg = Config(**mensajes[0]["contenido"]["config"])
        rp = Replay(cfg, mensajes)
        out, _ = rp.run_case(case)
        grabado = json.loads((ROOT / "results" / run / f"{cid}.txt").read_text(encoding="utf-8"))
        assert out == grabado, f"{run}/{cid}: la reproducción no coincide con la corrida"
        esperado = rules.expected_output(case)
        aprob = {m["id"] for m in out["approved_matches"]}
        for prop in case.properties:
            T = verdad(prop, case)
            pr = rp.primera[prop.id]
            L0, LF = leido(pr["h0"]), leido(rp.final[prop.id])
            veredicto = ("ok" if (prop.id in aprob) == esperado.by_id[prop.id].approved
                         else "aprobacion_indebida" if prop.id in aprob else "rechazo_falso")
            for c in CAMPOS:
                bien0, bienF = igual(c, L0[c], T[c], case.uf_value), igual(c, LF[c], T[c], case.uf_value)
                marcado = fue_marcado(c, pr["dudas"])
                if bien0 and bienF:
                    clase = "ok"
                elif not bien0:
                    origen = "anclar" if fragmento_trae_dato(c, pr["spans"], T[c], case.uf_value) else "lector"
                    destino = ("arreglado" if bienF else "silencioso" if not marcado else "verificador")
                    clase = f"{origen}/{destino}"
                else:
                    clase = "roto_verificador"
                filas.append({"run": run, "caso": cid, "aviso": prop.id, "campo": c, "clase": clase,
                              "marcado": int(marcado), "verdad": T[c], "h0": L0[c], "hF": LF[c],
                              "fragmento": " / ".join(str(pr["spans"].get(k)) for k in tools.SPAN_DE[c]),
                              "veredicto": veredicto, "texto": prop.text})
    return filas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--detalle", action="store_true", help="imprime cada error con su aviso")
    ap.add_argument("--csv", help="escribe todas las filas en este CSV")
    a = ap.parse_args(argv)
    todas = []
    for run in a.runs:
        split = run
        for pref in ("agents_v2_", "agents_v1_", "agents_ft_", "agents_ctrl_"):     # E3, E4 y control
            split = split.split(pref)[-1]
        for s in ("sin_esquema_", "sin_literal_", "sin_refinar_", "sin_releer_", "sin_consultar_", "sin_retro_"):
            split = split.replace(s, "")
        split = {"ood_dev": "ood", "train20": "train"}.get(split, split)
        filas = analizar(run, split)
        todas += filas
        n_av = len({f["aviso"] for f in filas})
        err = [f for f in filas if f["clase"] != "ok"]
        finales = [f for f in err if not f["clase"].endswith("/arreglado")]
        print(f"\n== {run}: {n_av} avisos, {len(filas)} campos; {len(err)} mal leídos en la primera pasada "
              f"o al final; {len(finales)} llegan mal a evaluar")
        print("   clase                    n   (de ellos, en avisos con veredicto errado)")
        for clase, n in sorted(Counter(f["clase"] for f in err).items(), key=lambda kv: -kv[1]):
            mal = sum(1 for f in err if f["clase"] == clase and f["veredicto"] != "ok")
            print(f"   {clase:<24} {n:>3}   {mal}")
        print("   origen del error en la primera pasada:",
              dict(Counter(f["clase"].split("/")[0] for f in err if "/" in f["clase"])))
        print("   por campo (errores que llegan a evaluar):",
              dict(Counter(f["campo"] for f in finales)))
        if a.detalle:
            for f in err:
                print(f"\n   [{f['clase']}] {f['aviso']} · {f['campo']} · veredicto {f['veredicto']}"
                      f"\n      verdad={f['verdad']!r}  h0={f['h0']!r}  hF={f['hF']!r}  marcado={f['marcado']}"
                      f"\n      fragmento: {f['fragmento']}\n      aviso: {f['texto']}")
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(todas[0]))
            w.writeheader()
            w.writerows(todas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
