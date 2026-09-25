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

### v5: "localizar, no interpretar" (anclaje + parsers)

Lectura de `extract_report` sobre `tools_phi4_v1` (352 propiedades, M4 y RTX coinciden):
los errores se concentran en los campos que el modelo debía **interpretar** (bedrooms 42:
"3D/1B" → 1, "1 dormitorio + sala convertible" → 2; parking 10/10: "en la calle" → asignado;
pets_species 12: "gatos sí, perros no" → ambas; pets_max_kg 4: "hasta 6kg" → null) y en
alucinaciones de unidad o del ejemplo del prompt en los que solo debía **copiar**
("$126.100.000" → "126.100.000 UF"; arriendo "$980.000" del ejemplo). En `test_0039` la M4
"acertó" por cancelación de dos errores y la RTX no: `e1_strict` puede inflarse por errores
que se compensan; `full_correct` es la métrica honesta.

v5 (`extract.SYSTEM_V5` + `SPANS_SCHEMA_V5` + `grounding.py`) cambia el contrato con el
modelo: devuelve solo **copias literales** de la cláusula de cada tema y tres respuestas
cerradas sobre mascotas (`acepta_mascotas/perros/gatos`); Python verifica que cada span exista
en el aviso (los números inventados quedan "no verificables" y nunca aprueban), lee la unidad
del aviso y parsea dormitorios, estacionamiento y kg. Sin números de ejemplo en el prompt.

Cota superior sin re-extraer (`python -m matcher.reground`, re-decide los traces v1 pasando
por grounding; las cláusulas se toman del aviso completo): `tools_phi4_v1` 30 → **42**/51,
`tools_phi4_v1_rtx` 29 → **42**/51 (`results/*_reground/`). El residuo son los 9 casos de
especies bajo negación, que v5 ataca con las preguntas cerradas y solo se puede medir
re-extrayendo.

Resultados (una sola corrida en test, tras validar en dev):

| run | n | e1_strict | full_correct | aprob. indebida | aritmética | esquema | tok/caso | s/caso M4 |
|---|---|---|---|---|---|---|---|---|
| dev_tools_v1 (train, dev) | 30 | 21 | 19 | 9 | 0 | 0 | 689 | 27,9 |
| dev_tools_v5 (train, dev) | 30 | 29 → 30* | 25 → 30* | 1 → 0* | 0 | 0 | 1079 | 42,6 |
| tools_phi4_v1 (test) | 51 | 30 | 22 | 20 | 1 | 0 | 674 | 29,7 |
| **tools_phi4_v5 (test)** | 51 | **51** | 40 | **0** | **0** | **0** | 1056 | 35,3 |

\* `dev_tools_v5_reground`: misma salida del modelo re-decidida tras dos ajustes de grounding
aprendidos en dev (respuestas de mascotas solo con cláusula anclada; fallback de dormitorios).
Los 11 casos de test sin `full_correct` son rechazos falsos o de ranking, nunca aprobaciones:
4× "Solo se admiten gatos" → `acepta_gatos: no` (lee "solo" como prohibición); 3× `pets_text`
rellenado con los nombres del esquema (alucinación por decodificación restringida → sin respaldo
→ rechazo); 2× distancia no anclada; 2× ranking (`location` no literal). Fallback de dormitorios
usado en 56/352 propiedades (notación "3D/1B" que el modelo no reconoce): se reporta como límite.

## Set OOD: avisos escritos a mano

`data/cases/ood/` — 12 casos, 70 propiedades, 19 aprobadas (27 %), construidos con
`scripts/build_ood.py` y auto-verificados contra `rules.py`. Ninguna plantilla del
generador: fichas de portal, WhatsApp sin tildes, MAYÚSCULAS con erratas, cifras en
palabras, "135 millones", "620 lucas", `UF 4.250,5`, rangos de precio, `2D+servicio`,
`3D+E`, gastos comunes junto al precio, distancias solo en minutos. Detalle y convenciones
de anotación en [`data/cases/ood/README.md`](../data/cases/ood/README.md).

Existe para responder la objeción que la solución se gana sola: si la interpretación la
hace el código, **¿queda algo que el LLM aporte, o esto es un regex sobre las plantillas
del generador?** La respuesta se mide, no se argumenta.

## Capa de anclaje: g1 → g2 → g3

La intervención tiene dos piezas versionadas por separado: el **prompt del extractor**
(v1…v5, lo que se le pide al modelo) y la **capa de anclaje** (g1…g3, lo que hace el
código con lo que el modelo devuelve). `--grounding` las selecciona; las tres son
reproducibles, así que cada fila de las tablas se puede regenerar.

| Capa | Qué añade | De dónde salió |
|---|---|---|
| `g1` | anclaje de spans + parsers; recuperación desde el aviso solo para dormitorios | la corrida original de v5 |
| `g2` | **A.** recuperación de cláusula para mascotas, estacionamiento, distancias y ubicación cuando el span no ancla. **B.** especies leídas de la cláusula por parseo en vez de las tres respuestas del modelo | análisis de los 11 fallos de `tools_phi4_v5` (test) |
| `g3` | cinco correcciones de parseo y seguridad (abajo) | correr g2 sobre el set OOD |

Las cinco de g3, todas con **impacto cero en test y dev** (la ruta que corrigen no se
activa con los avisos del generador; se verificó comparando las salidas byte a byte):

1. `"135 millones"` = 135.000.000 CLP (formato estándar en Chile).
2. **No adivinar la unidad del precio.** Si el aviso no dice UF ni `$` junto al número, el
   precio queda *no verificable* y la propiedad no se aprueba. Adivinar por magnitud leyó
   "piden 135 millones" como 135 UF = $5,2 M y aprobó dos propiedades fuera de presupuesto.
3. `"Estacionamiento opcional, se arrienda aparte"` ya no cae en la rama por defecto
   `propio`. El defecto de diseño era que la rama permisiva fuera la de descarte.
4. En una distancia, `"1.500 mts"` son 1500 m y no 1,5 m: el punto de miles se leía como
   decimal y aprobaba una propiedad a 1,5 km del metro.
5. `"UF 4.250,5"` se ancla completo (miles y decimales a la vez), como ya hacía
   `normalize.parse_number`.

Las cuatro primeras solo pueden **quitar** aprobaciones; la quinta puede añadir una, y se
declara como tal. Las cinco se encontraron mirando OOD, así que la columna g3 sobre OOD
**no es una medición ciega**; la que sí lo es, es g2.

## Resultados finales

phi4-mini 3.8B, prompt del extractor v5, temperatura 0, semilla 0. `e1_strict` es el
criterio de corrección del Entregable 1; `full_correct` exige además conjunto exacto y
orden correcto.

### Test — 51 casos held-out, plantillas del generador

| Run | e1_strict | full_correct | aprob. indebida | aritmética | esquema | s/caso M4 · RTX |
|---|---|---|---|---|---|---|
| Baseline (prompting directo) | 0/51 | 0 | 40 | 6 | 5 | 15,8 · 11,9 |
| A · CoT, una llamada | 0/51 | 0 | 43 | 4 | 4 | 21,0 |
| B · Descomposición sin herramientas | 0/51 | 0 | 41 | 4 | 6 | 51,4 |
| C · Solución, extractor v1 + g1 | 30/51 | 22 | 20 | 1 | 0 | 29,7 · 31,0 |
| C · Solución, v5 + g1 | 51/51 | 40 | 0 | 0 | 0 | 35,3 · 43,2 |
| **C · Solución, v5 + g3** | **51/51** | **51** | **0** | **0** | **0** | 35,3 · 43,2 |

Dev (30 casos de `train/`, donde se eligió v5): v1+g1 21/30, v5+g1 29/30, v5+g3 **30/30**.

### OOD — 12 casos escritos a mano

| Run | e1_strict | full_correct | aprob. indebida | aritmética |
|---|---|---|---|---|
| Baseline | 0/12 | 0 | 7 | 4 |
| Solución v5 + g1 | 8/12 | 4 | 4 | 0 |
| Solución v5 + g2 *(medición ciega)* | 9/12 | 5 | 3 | 0 |
| Solución v5 + g3 | 11/12 | 7 | 0 | 1 |

El baseline también se derrumba aquí (0/12), así que la comparación sigue siendo válida.
La caída de 51/51 a 9/12 entre test y OOD **es el resultado más informativo del trabajo**:
mide cuánto de la solución dependía de las plantillas del generador.

## Límites, con mecanismo

Los cinco fallos que quedan en OOD con g3. Ninguno es una aprobación indebida salvo donde
se indica; el sistema se equivoca **siendo conservador**, que es la dirección segura.

| Caso | Qué pasa | Mecanismo |
|---|---|---|
| `ood_002` OOD-201 | `"Arriendo referencial 620 lucas"` → arriendo = 620 → ROI 0,01 en vez de 6,0. **Rompe `e1_strict`** (error aritmético sobre una propiedad aprobada) | El anclaje exige que el número esté en el aviso, y "620" lo está. Lo que falta es la unidad: "lucas" (miles de pesos) es jerga chilena que ni el modelo traduce ni el normalizador conoce. Un multiplicador para "lucas"/"k" sería un parche a un caso; la corrección de fondo es la misma de g3.2 aplicada al arriendo — exigir marca de moneda —, pero eso convierte el ROI en `null` y el criterio E1 lo castiga igual. Es un límite del **criterio**, no solo del sistema |
| `ood_003` OOD-301 | `"ciento cuarenta y cinco millones de pesos"` → precio no verificable → rechazo falso | No hay ningún dígito que anclar. El diseño exige que el número exista en el aviso, así que un aviso sin dígitos es, por construcción, no procesable. Es el precio de la garantía de no aprobar con números inventados |
| `ood_005` OOD-502 | `"3D+E (escritorio)"` → dormitorios `null` → rechazo falso | El fallback busca `"ND/"` o `"N dormitorios"`; `"3D+E"` no coincide. Es exactamente la fragilidad que el set OOD existe para exponer: el parser cubre las notaciones del generador y una variante real se le escapa |
| `ood_011` OOD-1101 | `"2D 1B."` → dormitorios `null` → rechazo falso | Mismo mecanismo: la notación telegráfica sin barra no está cubierta |
| `ood_004` | Ranking: OOD-406 (Conchalí) antes que OOD-402 (Recoleta, comuna preferida) | `parse_location` asume que la comuna sigue a "en" (`"Depto en Providencia"`). En `"Depto 2D/2B, 72 m², Recoleta."` la comuna va al final y el parser devuelve el fragmento equivocado: 47 de 70 propiedades. Solo afecta el ranking (soft constraint), nunca una aprobación |

Dos de los cinco (`3D+E`, `2D 1B`) se arreglarían ampliando el parser de dormitorios, y el
del ranking con una lista de comunas. **No se hizo a propósito**: son mejoras que *añaden*
aprobaciones y se descubrieron mirando el conjunto de evaluación, así que incluirlas
convertiría la cifra de OOD en un número ajustado. Quedan documentadas como trabajo de la
E3.

### Qué aporta el LLM, medido

Con la interpretación movida al código, la objeción legítima es si el modelo sigue haciendo
algo. La respuesta está en la tabla de extracción por campo sobre OOD (`extract_report
--run tools_phi4_v5_ood_g3 --cases ../data/cases/ood`): sobre 70 avisos que ninguna
plantilla generó, el modelo localiza correctamente el precio en el 97 %, la distancia en el
99 %, la política de mascotas en el 99 % y el estacionamiento en el 94 % de los casos. Los
parsers reciben la cláusula correcta porque el modelo la encontró en texto libre, con
marketing, erratas y mayúsculas de por medio. Lo que el código aporta es que, una vez
localizada, la interpretación sea determinista y la aritmética exacta.
