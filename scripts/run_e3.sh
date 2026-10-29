#!/usr/bin/env bash
# Corridas de la E3. Mismos casos y mismo criterio (matcher.evaluate + matcher.metrics) para:
#   baseline (prompting directo) · E2 (v5+g3) · agentes (full) · agentes sin cada técnica ·
#   rechazar todo (piso)
#
# Uso:  bash scripts/run_e3.sh dev        # hard_dev: iterar (nunca hard_test ni real_e3)
#       bash scripts/run_e3.sh final      # test + ood + real_e3, UNA vez
#       bash scripts/run_e3.sh hard_test  # UNA vez, tras la revisión humana de hard_test
#       bash scripts/run_e3.sh ablaciones # hard_test, las 5 ablaciones
#       bash scripts/run_e3.sh tablas     # solo evaluate + metrics sobre lo que ya existe
#
# Cada corrida se puede interrumpir y retomar: los casos ya respondidos se omiten.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
MODEL="phi4-mini:latest"
AG="v1"   # versión del sistema de agentes (prompts/*/v1.md)

baseline()  { python3 -m matcher.run_model --model "$MODEL" --run "baseline_phi4_$1" --split "$1"; }
e2()        { python3 -m matcher.run_pipeline --mode tools --run "tools_phi4_v5_$1_g3" --split "$1" --grounding g3; }
agentes()   { python3 -m agents.run --split "$1" --run "agents_${AG}_$1"; }
ablacion()  { python3 -m agents.run --split "$1" --run "agents_${AG}_sin_$2_$1" --sin "$2"; }
piso()      { python3 -m matcher.reference --split "$1"; }

tablas() {
  local split="$1"; shift
  python3 -m matcher.evaluate --cases "data/cases/$split" --runs "$@"
  python3 -m matcher.metrics --cases "data/cases/$split" --runs "$@"
}

case "${1:-}" in
  dev)
    agentes hard_dev
    tablas hard_dev baseline_phi4_hard_dev tools_phi4_v5_hard_dev_g3 "agents_${AG}_hard_dev" ref_reject_all_hard_dev ;;
  final)       # no depende de la revisión de hard_test
    baseline real_e3; e2 real_e3; piso real_e3
    agentes real_e3; agentes test     # ood es dev: se usa agents_v1_ood_dev (corrida de verificación)
    tablas real_e3 baseline_phi4_real_e3 tools_phi4_v5_real_e3_g3 "agents_${AG}_real_e3" ref_reject_all_real_e3
    tablas test baseline_phi4 tools_phi4_v5_g3 "agents_${AG}_test" ref_reject_all
    tablas ood baseline_phi4_ood tools_phi4_v5_ood_g3 "agents_${AG}_ood_dev" ref_reject_all_ood ;;
  hard_test)   # SOLO después de la revisión humana (data/cases/hard_test/REVIEW.md) y una sola vez
    python3 scripts/build_hard.py --check
    baseline hard_test; e2 hard_test; agentes hard_test; piso hard_test
    tablas hard_test baseline_phi4_hard_test tools_phi4_v5_hard_test_g3 "agents_${AG}_hard_test" ref_reject_all_hard_test ;;
  ablaciones)
    for t in esquema literal refinar retro herramientas_decisor; do ablacion hard_test "$t"; done
    tablas hard_test "agents_${AG}_hard_test" $(for t in esquema literal refinar retro herramientas_decisor; do
      echo "agents_${AG}_sin_${t}_hard_test"; done) ;;
  tablas)
    tablas hard_dev baseline_phi4_hard_dev tools_phi4_v5_hard_dev_g3 "agents_${AG}_hard_dev" ref_reject_all_hard_dev ;;
  *) echo "uso: bash scripts/run_e3.sh dev|final|hard_test|ablaciones|tablas" >&2; exit 2 ;;
esac
