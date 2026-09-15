# Entregable 2 — Solución: descomposición + herramientas sobre phi4-mini

## Modelo comprometido

`phi4-mini:latest` (Phi-4-mini-instruct, 3.8B, Ollama digest `78fad5d182a7`, cuantización
Q4_K_M, 2.5 GB). Es el más pequeño de los tres candidatos de la E1 y los tres dan 0/51 con
prompting directo (`results/summary_baselines.csv`): los parámetros extra de Granite (8B) y
DeepSeek-R1 (7B) no compran corrección en esta tarea, y DeepSeek cuesta ~20× en tiempo.

## La intervención y su vínculo con el diagnóstico de la E1

El baseline pide al modelo, en una sola llamada, leer 5–9 avisos, convertir UF→CLP, comparar
5 restricciones por aviso, calcular ROI, ordenar y formatear. La E1 diagnosticó tres fallos
(atención selectiva, confusión aritmética, colapso lógico). La solución separa **percepción**
de **decisión**:

| Fallo E1 | Qué hace la solución | Módulo |
|---|---|---|
| Confusión aritmética (UF→CLP, ROI, inecuaciones) | El modelo **copia** el precio, arriendo y distancias como texto (`"3.850 UF"`); Python los parsea, convierte y compara. El LLM nunca multiplica ni compara magnitudes. | `normalize.py`, `constraints.py` |
| Colapso lógico (condicionales cruzados) | Una llamada **por propiedad**; cada hard constraint es una comparación aislada en Python sobre un campo ya normalizado. | `pipeline.py`, `constraints.py` |
| Atención selectiva (marketing) | El extractor **nunca ve el perfil del comprador**: no hay decisión que sesgar. "¡Bajo el presupuesto según el tasador!" no tiene ningún campo donde caer. | `extract.py` |
| Texto conversacional / esquema roto | Decodificación restringida (`format` = JSON Schema en Ollama) en la extracción; el JSON final lo ensambla código. | `extract.py`, `constraints.build_output` |

Lo que el modelo sigue haciendo (la parte no trivial de NLP): contar dormitorios *reales*
("escritorio convertible" no es dormitorio), leer la política de mascotas (especie, peso,
ausencia) y el tipo de estacionamiento (visitas ≠ propio). Ahí viven los fallos residuales.

Entrada, esquema de salida, criterio de corrección (`verifier.py`) y set de test son
**idénticos** a los del baseline. `constraints.py` no importa `rules.py` ni ve `truth`.

## Estrategias evaluadas (escalera de ablación)

| Modo (`run_pipeline --mode`) | Qué cambia respecto al baseline |
|---|---|
| `baseline` | prompting directo, 1 llamada (`run_model.py`) |
| `cot` | mismo prompt + procedimiento por pasos ("presupuesto primero…"); 1 llamada, sin herramientas. Es la hipótesis literal de la E1 para Phi-4-mini. |
| `decomp_llm` | extracción por propiedad (igual que la solución) pero el LLM convierte, compara y arma el JSON final. Aísla el aporte de las herramientas. |
| `tools` | **solución**: extracción por propiedad + Python decide. |
| fine-tuning | evaluado y descartado sin correr: no corrige la multiplicación 4×5 dígitos, ajusta a plantillas del generador, y QLoRA sobre prompts de 1.300 tokens es ajustado en 6 GB de VRAM. |

## Reproducir

```bash
ollama pull phi4-mini:latest
pip install -r requirements.txt
python3 -m pytest tests -q                         # 104 tests, sin Ollama

# Demo del video: baseline vs solución sobre el mismo caso, con veredicto de ambos
cd src
python3 -m matcher.demo --case case_001_e1         # el caso original de la E1
python3 -m matcher.demo --random                   # caso sorteado, no elegido a mano

# Tabla completa (51 casos held-out; ~10 min baseline + ~20 min solución en M4)
bash ../scripts/run_e2.sh                          # baseline + solución (prompt v1, el reportado)
ALL=1 bash ../scripts/run_e2.sh                    # + ablaciones cot y decomp_llm
python3 -m matcher.evaluate --runs baseline_phi4 cot_phi4 decomp_phi4 tools_phi4_v1
python3 -m matcher.extract_report --run tools_phi4_v1 --show   # errores de extracción campo a campo

# Iterar el prompt del extractor SIEMPRE en dev (train/) antes de test:
python3 -m matcher.run_pipeline --mode tools --run dev_tools_v4 --split train --limit 30 --prompt-version v4
python3 -m matcher.evaluate --runs dev_tools_v1 dev_tools_v4 --cases ../data/cases/train
```

Hardware: en la RTX 3050 (6 GB) phi4-mini Q4_K_M (2.5 GB) más el KV cache de 2048 tokens
cabe completo en VRAM; en la M4 corre en Metal. Cada llamada de extracción ve ~300 tokens y
emite ~80. Opcional en Windows para reducir memoria: `set OLLAMA_FLASH_ATTENTION=1` y
`set OLLAMA_KV_CACHE_TYPE=q8_0`.

## Resultados (51 casos held-out, temperatura 0, semilla 0, MacBook Air M4)

Fuente: `results/summary_e2.csv` (regenerable con `evaluate --runs baseline_phi4 cot_phi4 decomp_phi4 tools_phi4_v1`).

| Run | e1_strict | full_correct | fail_schema | fail_false_approval | fail_arithmetic | llamadas | tok salida | s/caso |
|---|---|---|---|---|---|---|---|---|
| baseline_phi4 (prompting directo) | 0/51 | 0 | 5 | 40 | 6 | 1 | 346 | 15.8 |
| cot_phi4 (A, procedimiento por pasos) | 0/51 | 0 | 4 | 43 | 4 | 1 | 326 | 21.0 |
| decomp_phi4 (B, extracción + LLM decide) | 0/51 | 0 | 6 | 41 | 4 | N+1 | 991 | 51.4 |
| **tools_phi4_v1 (solución)** | **30/51** (IC 95 %: 45–71 %) | 22 | 0 | 20 | 1 | N | 674 | 29.7 |

Aprobaciones indebidas por restricción (propiedades inválidas aprobadas igual):

| Restricción | inválidas | baseline | cot | decomp_llm | solución |
|---|---|---|---|---|---|
| presupuesto | 69 | 23 (33 %) | 21 (30 %) | 27 (39 %) | **0 (0 %)** |
| mascotas | 83 | 16 (19 %) | 13 (16 %) | 24 (29 %) | 7 (8 %) |
| distancia_transporte | 37 | 5 (14 %) | 3 (8 %) | 12 (32 %) | **0 (0 %)** |
| dormitorios | 41 | 11 (27 %) | 13 (32 %) | 13 (32 %) | 12 (29 %) |
| estacionamiento | 34 | 1 (3 %) | 2 (6 %) | 8 (24 %) | 8 (24 %) |

Lectura: la descomposición sola (`decomp_llm`) no repara nada —con los mismos hechos limpios,
phi4-mini sigue sin poder multiplicar UF×valor ni comparar—; lo que repara es quitarle la
aritmética y la lógica al modelo. Los 21 fallos residuales de la solución son todos de
*lectura* de un campo (ver `extract_report.py`): dormitorios "convertibles" (16) y notación
"3D/1B" (26, solo produce rechazos de más), negación en mascotas ("gatos sí, perros no" → ambas),
enum de estacionamiento ("en la calle" → asignado) y copia de los números de ejemplo del prompt
(15 precios, 4 arriendos).

### Iteración del prompt del extractor (dev = 30 casos de `train/`, nunca reportados)

| Prompt | e1_strict dev | err. precio | err. dormitorios | err. peso mascota | err. estacionamiento |
|---|---|---|---|---|---|
| v1 (reportado) | 21/30 | 13 | 27 | 6 | 5 |
| v2 (sin ejemplos numéricos, reglas reescritas) | 13/30 | 0 | 6 | 32 | 22 |
| v3 (v2 + líneas de v1 para mascotas/estacionamiento) | 8/30 | 0 | 7 | 27 | 7 |
| v4 (v3 sin la frase global "nunca inventes un número") | 8/30 | 2 | 9 | 24 | 7 |

v2–v4 arreglan lo que se les pide (precio 13→0–2, dormitorios 27→6–9) y rompen un campo cuya
línea **no cambió**: `pets_max_kg` sale `null` donde el aviso dice "hasta N kg" (y un límite nulo
se lee como "sin límite" ⇒ aprobaciones indebidas). Quitar la frase global sospechosa (v4) no lo
revirtió, así que la causa es la interacción entre las líneas reescritas y ese campo, no aislable
por inspección. En un 3.8B las instrucciones del prompt no son composicionales; por eso ninguna
versión nueva se corre en test sin ganar antes en dev. Es un límite del método que va al PDF.
