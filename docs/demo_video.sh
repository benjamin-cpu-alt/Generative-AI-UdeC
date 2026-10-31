#!/usr/bin/env bash
# Video E3 en una sola toma, sin cortes: cada Enter pasa a la escena siguiente.
# Antes de mostrar cada escena, el script escribe en pantalla el comando exacto que va a correr.
#   bash docs/demo_video.sh          (desde la raíz del repositorio)
# Guion: docs/guion_video_e3.md
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src
MODELO=phi4-mini:latest

escena() {   # espera Enter, limpia, muestra el comando y lo corre; "s" + Enter se salta la escena
  read -rs
  [ "$REPLY" = s ] && return
  clear
  printf '\033[1;32m$\033[0m \033[1m%s\033[0m\n\n' "$*"
  "$@"
}

# --- preparación (antes de empezar a grabar) ---
if pmset -g batt 2>/dev/null | grep -q "Battery Power"; then
  echo "El Mac está a batería: la corrida en vivo tarda ~3,5 min en vez de ~1 min. Enchúfalo." >&2
  exit 1
fi
echo "Cargando $MODELO en memoria…"
ollama run "$MODELO" "hola" >/dev/null || { echo "Ollama no responde: ábrelo y repite." >&2; exit 1; }
clear
echo "Listo. Empieza a grabar, muestra el grafo en el PDF y vuelve aquí: Enter = corrida en vivo."

# --- escena 2: corrida en vivo sobre avisos reales ---
escena python3 -m agents.run --split real_e3 --only real_b2_004 --run demo_video --force --vivo
# --- escena 3: el aviso que la E2 rechazaba ---
escena python3 -m agents.show results/agents_v2_real_e3/real_b2_005.trace.jsonl --aviso REAL-23 --pasos 12-14,28
# --- escena 4: convención E3, sin política de mascotas ---
escena python3 -m agents.show results/agents_v2_real_e3/real_b1_004.trace.jsonl --aviso REAL-08 --pasos 28-31,35
# --- escena 5: caso de fallo ---
escena python3 -m agents.show results/agents_v2_hard_test/ht_27.trace.jsonl --aviso HT-2708 --pasos 30-31,36-37
read -rs
