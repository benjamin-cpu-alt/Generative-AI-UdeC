# Guion del video E3 (máx. 3:00, avisos reales, mensajes intermedios visibles)

Se graba la terminal con `agents.show --pausa`, que reproduce una traza real mensaje a mensaje.
Los casos del video son de `real_e3/` (avisos de portales con doble anotación humana) y se eligen
**después** de la corrida final, sin repetirla: el video muestra lo que el sistema hizo.

> Elegidos con la corrida v1. Tras la convención E3 se repiten con `agents_v2_real_e3`: revisar
> que las trazas sigan mostrando lo mismo y cambiar `agents_v1` por `agents_v2` en los comandos.

Casos elegidos después de la corrida final (`results/agents_v1_real_e3/`):

- **`real_b2_004`** (comprador 2): la traza más completa. REAL-08 se aprueba. REAL-12: el
  Verificador propone 3 dormitorios con evidencia «5 dormitorios» y `comprobar` lo rechaza dos
  veces. REAL-04: «3 cuadras del metro» no es una distancia medible, y el Verificador pide releer
  hasta agotar el presupuesto (2 rondas). El Decisor intenta consultas que el orquestador
  descarta por no estar `no_verificable`.
- **`real_b2_005`**, aviso REAL-23: el único aviso real que la E2 rechaza por error. El
  Verificador recupera «Precio: UF 2.490.».
- **Caso de fallo:** `OOD-502` (`results/agents_v1_ood_dev/ood_005.trace.jsonl`): «3D+E, 2B». El
  Lector copia «2B» y el Verificador insiste en esa evidencia aunque `comprobar` la rechaza, así
  que termina en un rechazo falso. Si `hard_test` deja un fallo más representativo, se usa ese.

| Tiempo | Qué se ve | Qué se dice |
|---|---|---|
| 0:00–0:20 | `docs/e3_agentes.md` (grafo) | Tres agentes, el mismo phi4-mini. El benchmark de la E2 se saturaba (rechazar todo daba 51/51). |
| 0:20–1:10 | `agents.show …/real_b2_004.trace.jsonl --pausa 0.4` (pasos 15–31) | Lector → anclar → Verificador → `comprobar` rechaza 3 con evidencia «5 dormitorios» → Decisor cierra → REAL-08 aprobado. |
| 1:10–1:35 | Misma traza, `--aviso REAL-04` | El bucle de relectura con su presupuesto: el Verificador decide releer, el orquestador corta a las 2 rondas y el dato queda no verificable (no aprueba). |
| 1:35–1:55 | `agents.show …/real_b2_005.trace.jsonl --aviso REAL-23` | El aviso que la E2 rechazaba: el Verificador encuentra el precio y la herramienta lo valida. |
| 1:55–2:25 | `agents.show results/agents_v1_ood_dev/ood_005.trace.jsonl --aviso OOD-502` | Dónde falla: el modelo se ancla a «2B». La regla de seguridad lo vuelve un rechazo falso, no una aprobación indebida. |
| 2:25–3:00 | Tablas (`bash scripts/run_e3.sh tablas` o el PDF) | Baseline vs E2 vs agentes vs ablaciones en `hard_test`, con el piso de rechazar todo; regresión en real_e3 y test. |

Comandos (desde la raíz del repo, sin llamar al modelo):

```bash
export PYTHONPATH=src
python3 -m agents.show results/agents_v1_real_e3/real_b2_004.trace.jsonl --pausa 0.4
python3 -m agents.show results/agents_v1_real_e3/real_b2_004.trace.jsonl --aviso REAL-04
python3 -m agents.show results/agents_v1_real_e3/real_b2_005.trace.jsonl --aviso REAL-23
python3 -m agents.show results/agents_v1_ood_dev/ood_005.trace.jsonl --aviso OOD-502
bash scripts/run_e3.sh tablas
```

Para repetir el caso en vivo (llama al modelo, ~1 min):
`python3 -m agents.run --split real_e3 --only real_b2_004 --run demo_video --force`.
