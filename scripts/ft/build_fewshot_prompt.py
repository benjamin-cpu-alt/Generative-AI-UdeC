"""Prompt del CONTROL de la E4: el Lector base (sin pesos nuevos) con ejemplos few-shot
tomados de los mismos datos con los que se entrena el adaptador.

La pregunta que responde el control: ¿lo que logra el fine-tuning se consigue también
mostrándole al modelo base esos ejemplos en el prompt? Todo lo demás queda igual: mismo
phi4-mini, mismo `system` (SYSTEM_V5), mismas herramientas, mismos Verificador y Decisor.

Selección (determinista): K ejemplos sintéticos del split de entrenamiento, elegidos de modo
codicioso para cubrir los fenómenos del protocolo hard (notación de dormitorios, comuna fuera
de «en», jerga, cifras en palabras, varios montos, arriendo en UF, estacionamiento ambiguo,
mascotas condicionadas o sin política, dos distancias, distractor). Entre los que cubren lo
mismo se prefiere el aviso más corto, para que el prompt quepa en 4.096 tokens de contexto.

Uso:
  PYTHONPATH=src python3 scripts/ft/build_fewshot_prompt.py            # escribe prompts/lector/v2_fewshot.md
  PYTHONPATH=src python3 scripts/ft/build_fewshot_prompt.py --check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from agents import llm  # noqa: E402
from matcher.grounding import ANSWER_FIELDS, SPAN_FIELDS  # noqa: E402

K = 8
FENOMENOS = ["dorm_notacion", "comuna_posicion", "jerga_monto", "cifra_palabras", "multi_monto", "correccion",
             "arriendo_uf", "estac_ambiguo", "mascota_condicion", "mascota_silencio", "dist_multiple",
             "distractor", "dorm_no_cuenta", "dist_formato", "estilo"]
SALIDA = ROOT / "prompts" / "lector" / "v2_fewshot.md"

CABECERA = """# Lector · v2_fewshot (control de la E4)

Mismo `system` que `v1` (SYSTEM_V5 de la E2) más {k} ejemplos few-shot. Lo usa SOLO la corrida de
control: el modelo base sin adaptador, con ejemplos sacados de los datos de entrenamiento del
fine-tuning (`data/ft_lector/`, ids {ids}). Sirve para separar qué aporta el cambio de pesos y
qué se consigue solo con más prompting. Las secciones `inicial` y `relectura` son las de `v1`.

Generado por `scripts/ft/build_fewshot_prompt.py` (no editar a mano). Necesita
`--num-ctx-lector 4096`: con los ejemplos el prompt ya no cabe en 2.048 tokens.

Formato: cada sección empieza con una línea `=== nombre ===`. Las llaves `{{...}}` se
rellenan en `src/agents/llm.py`.
"""


def elegir(ejemplos, k: int = K):
    cand = [e for e in ejemplos if e["fuente"] == "sintetico" and e["split"] == "train" and not e["relectura"]
            and e["estilo"] in ("portal", "comas", "mayusculas", "ficha") and len(e["texto"]) <= 330]
    cand.sort(key=lambda e: e["id"])
    elegidos, cubiertos = [], set()
    while len(elegidos) < k:
        pend = [f for f in FENOMENOS if f not in cubiertos]
        def valor(e):
            return (len(set(e["tags"]) & set(pend)), e["estilo"] not in {x["estilo"] for x in elegidos},
                    -len(e["texto"]))
        mejor = max((e for e in cand if e not in elegidos), key=valor)
        elegidos.append(mejor)
        cubiertos |= set(mejor["tags"])
    return elegidos


def render(ejemplos) -> str:
    v1 = llm.load_prompt("lector", "v1")
    bloques = []
    for e in ejemplos:
        salida = {k: e["spans"][k] for k in SPAN_FIELDS + ANSWER_FIELDS}
        bloques.append(f'Aviso: "{e["texto"]}"\nJSON: {json.dumps(salida, ensure_ascii=False)}')
    system = (v1["system"] + "\n\nEjemplos resueltos. Son OTROS avisos: sirven para ver qué fragmento se copia "
              "en cada campo. Los fragmentos y números de tu respuesta deben salir solo del aviso que recibes, "
              "nunca de estos ejemplos.\n\n" + "\n\n".join(bloques))
    cab = CABECERA.format(k=len(ejemplos), ids=", ".join(e["id"] for e in ejemplos))
    return (f"{cab}\n=== system ===\n{system}\n\n=== inicial ===\n{v1['inicial']}\n\n"
            f"=== relectura ===\n{v1['relectura']}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    ejemplos = [json.loads(l) for l in (ROOT / "data" / "ft_lector" / "ejemplos.jsonl").read_text(encoding="utf-8").splitlines()]
    elegidos = elegir(ejemplos)
    texto = render(elegidos)
    if a.check:
        ok = SALIDA.exists() and SALIDA.read_text(encoding="utf-8") == texto
        print("OK" if ok else "DIFIERE: prompts/lector/v2_fewshot.md")
        return 0 if ok else 1
    SALIDA.write_text(texto, encoding="utf-8")
    for e in elegidos:
        print(e["id"], e["estilo"], ",".join(e["tags"]))
    print(f"{len(texto)} caracteres -> {SALIDA.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
