#!/usr/bin/env bash
# Corridas de la E4: fine-tuning del Lector (A1) del sistema de agentes de la E3.
#
# Los cuatro sistemas y el control, sobre las mismas entradas y con el mismo juez
# (matcher.evaluate + matcher.metrics):
#   baseline_e3_<set>   E1  prompt directo, phi4-mini base                      (corrida de la E3)
#   e2_e3_<set>         E2  extractor + herramientas (v5 + g3)                   (corrida de la E3)
#   agents_v2_<set>     E3  tres agentes, los tres con phi4-mini base            (corrida de la E3)
#   agents_ft_<set>     E4  los mismos agentes; el Lector usa phi4-mini-lector-ft (base + adaptador LoRA)
#   agents_ctrl_<set>   control: Lector BASE + 8 ejemplos few-shot de los datos de entrenamiento
#   ref_reject_all_<set> piso: rechazar todo
# Entre E3, E4 y el control lo único que cambia es el Lector: el modelo (E4) o el prompt (control).
#
# Uso:  bash scripts/run_e4.sh datos       # regenera y verifica data/ft_lector/ y el prompt del control
#       bash scripts/run_e4.sh entrenar    # LoRA con mlx-lm (Apple Silicon, entorno .venv-ft)
#       bash scripts/run_e4.sh modelo      # adaptador -> GGUF -> `ollama create phi4-mini-lector-ft`
#       bash scripts/run_e4.sh dev         # hard_dev: E4 y control (selección de checkpoint y de diseño)
#       bash scripts/run_e4.sh hard_test   # UNA vez: E4 y control sobre hard_test
#       bash scripts/run_e4.sh final       # real_e3, test y ood
#       bash scripts/run_e4.sh tablas      # tablas, atribución de errores y costo/bucles desde results/ (sin modelo)
#       bash scripts/run_e4.sh todo        # dev, hard_test, final, tablas
#
# Cada corrida se puede interrumpir y retomar: los casos ya respondidos se omiten.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
FT_MODEL="phi4-mini-lector-ft"
PY_FT=".venv-ft/bin/python"       # entorno de entrenamiento (scripts/ft/requirements.txt)

piso_run() { case "$1" in test) echo ref_reject_all ;; *) echo "ref_reject_all_$1" ;; esac; }
ft()       { python3 -m agents.run --split "$1" --run "agents_ft_$1" --modelo-lector "$FT_MODEL"; }
control()  { python3 -m agents.run --split "$1" --run "agents_ctrl_$1" --lector v2_fewshot --num-ctx-lector 4096; }

tabla() {
  local s="$1"
  local runs="baseline_e3_$s e2_e3_$s agents_v2_$s"
  for r in "agents_ft_$s" "agents_ctrl_$s" "$(piso_run "$s")"; do [ -d "results/$r" ] && runs="$runs $r"; done
  python3 -m matcher.evaluate --cases "data/cases/$s" --runs $runs
  python3 -m matcher.metrics --cases "data/cases/$s" --runs $runs
}
atribucion() {   # ¿en qué agente nace cada error de lectura? E3 vs E4 vs control, desde las trazas
  local runs=""
  for s in hard_dev hard_test; do
    for r in "agents_v2_$s" "agents_ft_$s" "agents_ctrl_$s"; do [ -d "results/$r" ] && runs="$runs $r"; done
  done
  python3 scripts/atribucion_e3.py $runs
}
costo() {        # llamadas por agente, vueltas de cada bucle, tokens y minutos, desde las trazas
  for s in hard_test hard_dev real_e3 test ood; do
    local runs=""
    for r in "agents_v2_$s" "agents_ft_$s" "agents_ctrl_$s"; do [ -d "results/$r" ] && runs="$runs $r"; done
    echo; python3 scripts/resumen_e4.py $runs
  done
}

datos() {
  python3 scripts/ft/build_lector_data.py
  python3 scripts/ft/build_lector_data.py --check
  python3 scripts/ft/build_fewshot_prompt.py
}
entrenar() { "$PY_FT" scripts/ft/train_lector.py; }
modelo() {
  "$PY_FT" scripts/ft/export_gguf.py ft/lector
  ollama create "$FT_MODEL" -f ft/lector/Modelfile
  ollama show "$FT_MODEL" | head -20
}
hard_test() {   # una sola vez, con el adaptador ya elegido en dev
  python3 scripts/build_hard.py --check
  ft hard_test; control hard_test; tabla hard_test
}

case "${1:-}" in
  datos)      datos ;;
  entrenar)   entrenar ;;
  modelo)     modelo ;;
  dev)        ft hard_dev; control hard_dev; tabla hard_dev ;;
  hard_test)  hard_test ;;
  final)      for s in real_e3 test ood; do ft "$s"; control "$s"; tabla "$s"; done ;;
  tablas)     for s in hard_test real_e3 test ood hard_dev; do tabla "$s"; done; atribucion; costo ;;
  atribucion) atribucion; costo ;;
  todo)       ft hard_dev; control hard_dev; hard_test; for s in real_e3 test ood; do ft "$s"; control "$s"; done
              for s in hard_test real_e3 test ood hard_dev; do tabla "$s"; done; atribucion; costo ;;
  *) echo "uso: bash scripts/run_e4.sh datos|entrenar|modelo|dev|hard_test|final|tablas|atribucion|todo" >&2; exit 2 ;;
esac
