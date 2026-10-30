#!/usr/bin/env bash
# Corridas de la E3. Mismos casos y mismo criterio (matcher.evaluate + matcher.metrics) para:
#   baseline (prompting directo) · E2 (v5+g3) · agentes (full) · agentes sin cada técnica ·
#   rechazar todo (piso)
#
# Convención E3 (revisión humana de hard_test, 29-oct): un aviso sin política de mascotas no
# se descarta (va al final del orden) y un estudio/loft cuenta como 1 dormitorio. Todas las
# corridas de aquí usan esa convención: baseline_e3_*, e2_e3_*, agents_v2_*. Las corridas
# anteriores (baseline_phi4_*, tools_phi4_v5_*, agents_v1_*) quedan como historial.
#
# Uso:  bash scripts/run_e3.sh todo        # todo lo de abajo, en orden de prioridad
#       bash scripts/run_e3.sh hard_test   # UNA vez: baseline, E2, agentes y piso en hard_test
#       bash scripts/run_e3.sh final       # real_e3, test y ood (ood es dev)
#       bash scripts/run_e3.sh ablaciones  # hard_test, las 5 ablaciones
#       bash scripts/run_e3.sh refinar     # hard_test, −refinar separado en −releer y −consultar
#       bash scripts/run_e3.sh dev         # hard_dev
#       bash scripts/run_e3.sh tablas      # solo evaluate + metrics sobre lo que ya existe
#
# Cada corrida se puede interrumpir y retomar: los casos ya respondidos se omiten.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
MODEL="phi4-mini:latest"
AG="v2"   # versión del sistema de agentes (decisor v2: convención E3)
TECNICAS="esquema literal refinar retro herramientas_decisor"
REFINAR="releer consultar"   # los dos bucles de −refinar, por separado (post-hoc, 30-oct)

# corrida E2 original de cada split (para re-decidir sin llamar al modelo)
e2_fuente() { case "$1" in test) echo tools_phi4_v5_g3 ;; *) echo "tools_phi4_v5_$1_g3" ;; esac; }
piso_run()  { case "$1" in test) echo ref_reject_all ;; *) echo "ref_reject_all_$1" ;; esac; }

baseline()  { python3 -m matcher.run_model --model "$MODEL" --run "baseline_e3_$1" --split "$1"; }
e2_nuevo()  { python3 -m matcher.run_pipeline --mode tools --run "e2_e3_$1" --split "$1" --grounding g3; }
# la extracción del LLM no depende del criterio: se re-decide con el código actual
e2_redecide() { python3 -m matcher.reground --run "$(e2_fuente "$1")" --out "e2_e3_$1" --split "$1" --grounding g3; }
agentes()   { python3 -m agents.run --split "$1" --run "agents_${AG}_$1"; }
ablacion()  { python3 -m agents.run --split "$1" --run "agents_${AG}_sin_$2_$1" --sin "$2"; }
piso()      { python3 -m matcher.reference --split "$1"; }

tabla() {
  local split="$1"; shift
  python3 -m matcher.evaluate --cases "data/cases/$split" --runs "$@"
  python3 -m matcher.metrics --cases "data/cases/$split" --runs "$@"
}
tabla_split() { tabla "$1" "baseline_e3_$1" "e2_e3_$1" "agents_${AG}_$1" "$(piso_run "$1")"; }
tabla_ablaciones() {
  local runs; runs=$(for t in $TECNICAS $REFINAR; do r="agents_${AG}_sin_${t}_hard_test"; [ -d "results/$r" ] && echo "$r"; done)
  tabla hard_test "agents_${AG}_hard_test" $runs
}

hard_test() {   # SOLO después de la revisión humana (data/cases/hard_test/REVIEW.md) y una sola vez
  python3 scripts/build_hard.py --check
  baseline hard_test; e2_nuevo hard_test; agentes hard_test; piso hard_test
  tabla_split hard_test
}
final_split() { baseline "$1"; e2_redecide "$1"; agentes "$1"; piso "$1"; tabla_split "$1"; }
ablaciones() { for t in $TECNICAS; do ablacion hard_test "$t"; done; tabla_ablaciones; }
refinar()    { for t in $REFINAR; do ablacion hard_test "$t"; done; tabla_ablaciones; }

case "${1:-}" in
  todo)       hard_test; final_split real_e3; ablaciones; final_split test; final_split ood; final_split hard_dev ;;
  hard_test)  hard_test ;;
  final)      final_split real_e3; final_split test; final_split ood ;;
  ablaciones) ablaciones ;;
  refinar)    refinar ;;
  dev)        final_split hard_dev ;;
  tablas)     for s in hard_test real_e3 test ood hard_dev; do tabla_split "$s"; done; tabla_ablaciones ;;
  *) echo "uso: bash scripts/run_e3.sh todo|hard_test|final|ablaciones|refinar|dev|tablas" >&2; exit 2 ;;
esac
