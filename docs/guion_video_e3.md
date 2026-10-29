# Guion del video E3 (máx. 3:00, avisos reales, mensajes intermedios visibles)

Se graba la terminal con `agents.show --pausa`, que reproduce una traza real mensaje a mensaje.
Los casos del video son de `real_e3/` (avisos de portales con doble anotación humana) y se eligen
**después** de la corrida final, sin repetirla: el video muestra lo que el sistema hizo.

| Tiempo | Qué se ve | Qué se dice |
|---|---|---|
| 0:00–0:20 | `docs/e3_agentes.md` (grafo) | Tres agentes, el mismo phi4-mini. El benchmark de la E2 se saturaba (rechazar todo daba 51/51). |
| 0:20–1:20 | `python3 -m agents.show results/agents_v1_real_e3/<caso con aprobación>.trace.jsonl --pausa 0.4` | Lector → anclar → Verificador (campos ⚠, corrige con evidencia) → comprobar acepta o rechaza → Decisor cierra → JSON. |
| 1:20–1:50 | Misma traza, `--aviso <id>` del aviso con el bucle más largo (releer o retro) | Un bucle con su presupuesto: el agente decide qué sigue. |
| 1:50–2:20 | El caso de fallo (`--aviso`) | Dónde falla y por qué (traza versionada). |
| 2:20–3:00 | `bash scripts/run_e3.sh tablas` | Baseline vs E2 vs agentes vs ablaciones en `hard_test`, con el piso de rechazar todo. |

Comandos (desde la raíz del repo, sin llamar al modelo):

```bash
export PYTHONPATH=src
python3 -m agents.show results/agents_v1_real_e3/<caso>.trace.jsonl --pausa 0.4
python3 -m agents.show results/agents_v1_real_e3/<caso>.trace.jsonl --aviso <REAL-xx>
bash scripts/run_e3.sh tablas
```

Para repetir el caso en vivo (llama al modelo, ~1 min):
`python3 -m agents.run --split real_e3 --only <caso> --run demo_video --force`.
