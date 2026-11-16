#!/usr/bin/env bash
# Video E4 en una sola toma, sin cortes: cada Enter pasa a la escena siguiente ("s" + Enter la salta).
# Antes de cada escena el script escribe en pantalla el comando exacto que va a correr.
#   bash docs/demo_video_e4.sh            (desde la raíz del repositorio)
#   bash docs/demo_video_e4.sh --grabado  (sin Ollama: las mismas escenas desde las trazas guardadas)
#
# Escenas (la 1 es el grafo del PDF, fuera de la terminal):
#   2  Lector base contra Lector ajustado sobre el MISMO aviso real (REAL-18), en vivo
#   3  el sistema completo en vivo con el Lector ajustado: agentes, herramientas y los tres bucles
#   4  caso de fallo HT-0906 (aprobación indebida) desde su traza
#   5  tabla de los cuatro sistemas y el control en hard_test
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src
BASE=phi4-mini:latest
FT=phi4-mini-lector-ft
CASO=real_b1_006          # caso real: el comprador pide 2 dormitorios, estacionamiento y metro a 1.000 m
AVISO=REAL-18             # el Lector base lee mal comuna y dormitorios; el ajustado los copia bien
GRABADO=0; [ "${1:-}" = "--grabado" ] && GRABADO=1

escena() {   # espera Enter, limpia, muestra el comando y lo corre
  read -rs
  [ "$REPLY" = s ] && return
  clear
  printf '\033[1;32m$\033[0m \033[1m%s\033[0m\n\n' "$*"
  "$@"
}
tabla() { python3 -m matcher.metrics --cases data/cases/hard_test --runs "$@" | head -7; }

# --- preparación (antes de empezar a grabar) ---
if [ "$GRABADO" = 0 ]; then
  if pmset -g batt 2>/dev/null | grep -q "Battery Power"; then
    echo "El Mac está a batería: las escenas en vivo tardan el triple. Enchúfalo (o usa --grabado)." >&2
    exit 1
  fi
  ollama list 2>/dev/null | grep -q "^$FT" || {
    echo "Falta el modelo $FT: sigue el paso 2 de la sección E4 del README (ollama create)." >&2; exit 1; }
  echo "Cargando $BASE y $FT en memoria…"
  ollama run "$BASE" "hola" >/dev/null || { echo "Ollama no responde: ábrelo y repite." >&2; exit 1; }
  ollama run "$FT" "hola" >/dev/null
fi
clear
echo "Listo. Empieza a grabar, muestra el grafo en el PDF y vuelve aquí: Enter = base contra ajustado."

if [ "$GRABADO" = 0 ]; then
  # --- escena 2: el mismo aviso real, los dos Lectores ---
  escena python3 -m agents.comparar --split real_e3 --caso "$CASO" --aviso "$AVISO"
  # --- escena 3: sistema completo en vivo, con el Lector ajustado ---
  escena python3 -m agents.run --split real_e3 --only "$CASO" --run demo_e4 --force --vivo --roles \
      --modelo-lector "$FT"
else
  # Las mismas dos escenas desde las corridas guardadas: E3 (Lector base) y E4 (Lector ajustado).
  escena python3 -m agents.show "results/agents_v2_real_e3/$CASO.trace.jsonl" --aviso "$AVISO" --roles
  escena python3 -m agents.show "results/agents_ft_real_e3/$CASO.trace.jsonl" --roles --pausa 0.8
fi
# --- escena 4: caso de fallo ---
escena python3 -m agents.show results/agents_ft_hard_test/ht_09.trace.jsonl --aviso HT-0906 --roles \
    --pasos 28-30,44,53
# --- escena 5: resultados ---
escena tabla baseline_e3_hard_test e2_e3_hard_test agents_v2_hard_test agents_ft_hard_test agents_ctrl_hard_test
read -rs
