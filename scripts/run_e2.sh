#!/usr/bin/env bash
# Entregable 2: baseline vs solución (y ablaciones) con phi4-mini sobre los 51 casos
# held-out, juzgados por el mismo verificador. Reproduce la tabla del PDF.
#
# Requisitos: Ollama corriendo y `ollama pull phi4-mini:latest` (Q4_K_M, 3.8B, ~2.5 GB).
#   macOS (M4): Metal por defecto.
#   Windows (RTX 3050 6 GB): Ollama usa CUDA; pesos + KV cache de 2048 tokens caben en VRAM.
#     Opcional para bajar memoria:  set OLLAMA_FLASH_ATTENTION=1 & set OLLAMA_KV_CACHE_TYPE=q8_0
#
# Uso:  bash scripts/run_e2.sh              # baseline + tools (lo mínimo para la E2)
#       ALL=1 bash scripts/run_e2.sh        # además las ablaciones cot y decomp_llm
#       LIMIT=3 bash scripts/run_e2.sh      # prueba rápida
#       SPLIT=ood bash scripts/run_e2.sh    # sobre los avisos escritos a mano
# Se puede interrumpir y retomar: los casos ya respondidos se omiten.
set -euo pipefail
cd "$(dirname "$0")/../src"

MODEL="${MODEL:-phi4-mini:latest}"
PROMPT="${PROMPT:-v5}"       # prompt del extractor reportado en el PDF (ver extract.py)
GROUNDING="${GROUNDING:-g3}"  # capa de anclaje reportada (ver grounding.py)
LIMIT_ARG=""; [ -n "${LIMIT:-}" ] && LIMIT_ARG="--limit $LIMIT"

echo "================ baseline (prompting directo) ================"
# shellcheck disable=SC2086
python3 -m matcher.run_model --model "$MODEL" --run baseline_phi4 --num-predict 2048 --num-ctx 4096 $LIMIT_ARG \
  2>&1 | tee -a ../results/baseline_phi4.log

RUNS=(baseline_phi4)
MODES=(tools); [ -n "${ALL:-}" ] && MODES=(cot decomp_llm tools)
for m in "${MODES[@]}"; do
  run="${m}_phi4"; [ "$m" = "decomp_llm" ] && run="decomp_phi4"; [ "$m" = "tools" ] && run="tools_phi4_${PROMPT}_${GROUNDING}"
  echo "================ $m ================"
  # shellcheck disable=SC2086
  python3 -m matcher.run_pipeline --mode "$m" --model "$MODEL" --run "$run" \
    --prompt-version "$PROMPT" --grounding "$GROUNDING" $LIMIT_ARG \
    2>&1 | tee -a "../results/$run.log"
  RUNS+=("$run")
done

python3 -m matcher.evaluate --runs "${RUNS[@]}"
echo
python3 -m matcher.extract_report --run "tools_phi4_${PROMPT}_${GROUNDING}"
