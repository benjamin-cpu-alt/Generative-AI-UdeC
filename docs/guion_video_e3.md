# Guion del video E3 (máx. 3:00, avisos reales, mensajes intermedios visibles)

Se graba la terminal con `agents.show --pausa`, que reproduce una traza real mensaje a mensaje.
Los casos del video son de `real_e3/` (avisos de portales con doble anotación humana) y se eligen
**después** de la corrida final, sin repetirla: el video muestra lo que el sistema hizo.

Casos (corrida final con la convención E3, `results/agents_v2_real_e3/`; se eligieron con la
corrida v1 y se revisó que las trazas v2 muestran lo mismo):

- **`real_b2_004`** (comprador 2): la traza más completa.
  - REAL-04: «3 cuadras de salida Metro» no es una distancia medible. El Verificador pide releer
    hasta agotar el presupuesto de 2 rondas (pasos 4–14).
  - REAL-12: el Verificador propone 3 dormitorios con evidencia «5 dormitorios» y `comprobar` lo
    rechaza dos veces (pasos 18–23).
  - REAL-16: el Verificador escribe 3 y `comprobar` acepta la evidencia pero toma el valor que dice
    el texto, «dos dormitorios» = 2 (pasos 24–27).
  - El Decisor intenta consultas que el orquestador descarta y REAL-08 queda aprobado (28–31).
- **`real_b2_005`**, aviso REAL-23: el único aviso real que la E2 rechaza por error. El
  Verificador recupera «Precio: UF 2.490.».
- **`real_b1_004`**, aviso REAL-08 (comprador 1, con perro): la convención E3. El aviso no dice nada
  de mascotas, `evaluar` lo deja *sin confirmar* y el Decisor consulta. El Verificador confirma que
  el texto no declara política: es silencio, no una duda. El aviso se aprueba y va al final del
  orden (pasos 28–35).
- **Caso de fallo:** `HT-2708` (`results/agents_v2_hard_test/ht_27.trace.jsonl`; hard_test es
  sintético, pero es la falla más frecuente). El Verificador arregla «3D.», que la E2 no leía, y eso
  destapa que `anclar` leyó «estacionamiento en la vía pública» como *propio* sin marcar duda:
  aprobación indebida.

| Tiempo | Qué se ve | Qué se dice |
|---|---|---|
| 0:00–0:20 | `docs/e3_agentes.md` (grafo) | Tres agentes, el mismo phi4-mini. El benchmark de la E2 se saturaba (rechazar todo daba 51/51). |
| 0:20–1:00 | `agents.show …/real_b2_004.trace.jsonl --pausa 0.4` (pasos 15–31) | Lector → anclar → Verificador → `comprobar` rechaza 3 con evidencia «5 dormitorios» → Decisor cierra → REAL-08 aprobado. |
| 1:00–1:20 | Misma traza, `--aviso REAL-04` | El bucle de relectura con su presupuesto: el orquestador corta a las 2 rondas y el dato queda no verificable (no aprueba). |
| 1:20–1:40 | `agents.show …/real_b2_005.trace.jsonl --aviso REAL-23` | El aviso que la E2 rechazaba: el Verificador encuentra el precio y la herramienta lo valida. |
| 1:40–1:55 | `agents.show …/real_b1_004.trace.jsonl --aviso REAL-08` | Convención acordada en la revisión: sin política de mascotas no se descarta, va al final. |
| 1:55–2:25 | `agents.show results/agents_v2_hard_test/ht_27.trace.jsonl --aviso HT-2708` | Dónde falla: el Verificador solo revisa lo que la herramienta marca; la E2 acertaba por la razón equivocada. |
| 2:25–3:00 | Tablas (`bash scripts/run_e3.sh tablas` o el PDF) | hard_test: E1 23/30 vs 11/30 de la E2, rechazos falsos 18 % vs 42 %, 6 aprobaciones indebidas; ablaciones; real_e3 20/20. |

Comandos (desde la raíz del repo, sin llamar al modelo):

```bash
export PYTHONPATH=src
python3 -m agents.show results/agents_v2_real_e3/real_b2_004.trace.jsonl --pausa 0.4
python3 -m agents.show results/agents_v2_real_e3/real_b2_004.trace.jsonl --aviso REAL-04
python3 -m agents.show results/agents_v2_real_e3/real_b2_005.trace.jsonl --aviso REAL-23
python3 -m agents.show results/agents_v2_real_e3/real_b1_004.trace.jsonl --aviso REAL-08
python3 -m agents.show results/agents_v2_hard_test/ht_27.trace.jsonl --aviso HT-2708
bash scripts/run_e3.sh tablas
```

Para repetir un caso en vivo (llama al modelo, ~1 min):
`python3 -m agents.run --split real_e3 --only real_b2_004 --run demo_video --force`.
