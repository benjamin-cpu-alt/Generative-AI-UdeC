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
# Con SPLIT distinto de test las corridas llevan el sufijo _<split> (baseline_phi4_ood,
# tools_phi4_v5_ood_g3), así que nunca pisan las de test.
# Se puede interrumpir y retomar: los casos ya respondidos se omiten.
set -euo pipefail
cd "$(dirname "$0")/../src"

MODEL="${MODEL:-phi4-mini:latest}"
PROMPT="${PROMPT:-v5}"       # prompt del extractor reportado en el PDF (ver extract.py)
GROUNDING="${GROUNDING:-g3}"  # capa de anclaje reportada (ver grounding.py)
# Ablación B (decomp_llm): mismo extractor que la solución, así el LLM decide sobre los MISMOS
# hechos que Python (results/decomp_phi4_v5). DECOMP_PROMPT=v2 reproduce la primera versión
# (results/decomp_phi4), que usó otro extractor.
DECOMP_PROMPT="${DECOMP_PROMPT:-$PROMPT}"
SPLIT="${SPLIT:-test}"        # subcarpeta de data/cases (test|ood|train)
CASES="../data/cases/$SPLIT"
[ -d "$CASES" ] || { echo "no existe $CASES" >&2; exit 1; }
SFX=""; [ "$SPLIT" != "test" ] && SFX="_$SPLIT"
LIMIT_ARG=""; [ -n "${LIMIT:-}" ] && LIMIT_ARG="--limit $LIMIT"

echo "================ baseline (prompting directo, split=$SPLIT) ================"
# shellcheck disable=SC2086
python3 -m matcher.run_model --model "$MODEL" --run "baseline_phi4$SFX" --split "$SPLIT" \
  --num-predict 2048 --num-ctx 4096 $LIMIT_ARG \
  2>&1 | tee -a "../results/baseline_phi4$SFX.log"

RUNS=("baseline_phi4$SFX")
MODES=(tools); [ -n "${ALL:-}" ] && MODES=(cot decomp_llm tools)
TOOLS_RUN="tools_phi4_${PROMPT}${SFX}_${GROUNDING}"
for m in "${MODES[@]}"; do
  run="${m}_phi4$SFX"; p="$PROMPT"
  if [ "$m" = "decomp_llm" ]; then
    p="$DECOMP_PROMPT"; run="decomp_phi4_${p}$SFX"; [ "$p" = "v2" ] && run="decomp_phi4$SFX"
  fi
  [ "$m" = "tools" ] && run="$TOOLS_RUN"
  echo "================ $m (split=$SPLIT) ================"
  # shellcheck disable=SC2086
  python3 -m matcher.run_pipeline --mode "$m" --model "$MODEL" --run "$run" --split "$SPLIT" \
    --prompt-version "$p" --grounding "$GROUNDING" $LIMIT_ARG \
    2>&1 | tee -a "../results/$run.log"
  RUNS+=("$run")
done

python3 -m matcher.evaluate --runs "${RUNS[@]}" --cases "$CASES"
echo
python3 -m matcher.extract_report --run "$TOOLS_RUN" --cases "$CASES"
