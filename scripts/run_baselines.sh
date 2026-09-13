#!/usr/bin/env bash
# Corre los tres modelos candidatos con prompting directo sobre el split test
# y produce la tabla comparativa. Requiere Ollama corriendo con los modelos:
#   ollama pull phi4-mini:latest granite4.1:8b deepseek-r1:7b
#
# Uso:  bash scripts/run_baselines.sh              # los tres
#       bash scripts/run_baselines.sh phi4         # solo uno (phi4|granite|deepseek)
#       LIMIT=3 bash scripts/run_baselines.sh phi4 # prueba rápida con 3 casos
#
# Cada ejecución se puede interrumpir y retomar: los casos ya respondidos se omiten.
# Compatible con bash 3.2 (macOS) y Git Bash (Windows).
set -euo pipefail
cd "$(dirname "$0")/../src"

model_of() {
  case "$1" in
    phi4)     echo "phi4-mini:latest" ;;
    granite)  echo "granite4.1:8b" ;;
    deepseek) echo "deepseek-r1:7b" ;;
    *) echo "modelo desconocido: $1 (usa phi4|granite|deepseek)" >&2; exit 2 ;;
  esac
}
# DeepSeek-R1 razona en <think> antes del JSON: con 2048 tokens se trunca sin responder.
# Se le da presupuesto amplio; el costo (tokens, segundos) queda registrado en la tabla.
extra_of() {
  case "$1" in
    deepseek) echo "--num-predict 8192 --num-ctx 12288" ;;
    *)        echo "--num-predict 2048 --num-ctx 4096" ;;
  esac
}

TARGETS=("$@"); [ ${#TARGETS[@]} -eq 0 ] && TARGETS=(phi4 granite deepseek)
LIMIT_ARG=""; [ -n "${LIMIT:-}" ] && LIMIT_ARG="--limit $LIMIT"

RUNS=()
for t in "${TARGETS[@]}"; do
  model="$(model_of "$t")"
  echo "================ $model ================"
  # shellcheck disable=SC2086
  python3 -m matcher.run_model --model "$model" --run "baseline_$t" $(extra_of "$t") $LIMIT_ARG \
    2>&1 | tee -a "../results/baseline_$t.log"
  RUNS+=("baseline_$t")
done

python3 -m matcher.evaluate --runs "${RUNS[@]}"
