# Real Estate AI Matcher (Generative AI - 580694)

**Miembros del Equipo:** Benjamín Grandón V, Carla Maureira V.  
**Curso:** Generative Artificial Intelligence  
**Profesor:** Carlos Navarrete, PhD  

## La Tarea
Matching Automático Comprador-Propiedad con Optimización de Restricciones Cruzadas.  
El sistema es un motor de validación que lee descripciones de propiedades no estructuradas y las evalúa frente a reglas estrictas del comprador. Esto incluye resolver operaciones matemáticas dinámicas (conversiones de UF a CLP, cálculos de ROI) y restricciones espaciales o lógicas. *(El prompt base y los datos de prueba se encuentran en la carpeta `/data`)*.

## Modelo comprometido (Entregable 2)

**`phi4-mini:latest`** — Phi-4-mini-instruct, 3.8B, Ollama digest `78fad5d182a7`, cuantización
Q4_K_M (2,5 GB). Es el más pequeño de los tres candidatos de la E1.

**Desviación declarada respecto a la E1:** el PDF de la E1 marcó a DeepSeek-R1-Distill-Qwen
(7B) como candidato *[Principal]*, por su razonamiento paso a paso. La E2 se compromete con
Phi-4-mini, el candidato que la E1 propuso para probar si un modelo compacto resuelve la
tarea cuando se la divide en pasos. El cambio se justifica con la medición de abajo: con
prompting directo DeepSeek tampoco acierta ningún caso, y su razonamiento en `<think>` cuesta
~20× más tiempo por caso y trunca 22 de 51 respuestas.

Los tres candidatos se corrieron con el mismo prompt directo sobre los 51 casos held-out y los
tres dan **0/51**: los parámetros extra no compran corrección en esta tarea.

| Candidato E1 | Params | e1_strict | Decisión |
|---|---|---|---|
| **Phi-4-mini** | **3.8B** | **0/51** | **Elegido**: mismo resultado que los grandes, con el menor costo y la menor huella. La E1 le asignó el rol de "resolver la tarea si se le guía dividiendo el problema en pasos simples": la E2 ejecuta esa hipótesis. |
| Granite 4.1 | 8.0B | 0/51 | Propuesto por su formato JSON estricto (BFCL), tiene **más** fallos de esquema que Phi (8 vs 5) y la peor tasa de aprobación indebida por presupuesto (51 %). |
| DeepSeek-R1-Distill-Qwen | 7.0B | 0/51 | Era el *[Principal]* de la E1. Razona mejor (14 % de aprobación indebida por presupuesto vs 33 %) pero no acierta un solo caso: 26 fallos de esquema, 22 de ellos respuestas truncadas (el `<think>` agota el presupuesto de 8.192 tokens antes del JSON), a ~4.996 tokens y ~323 s por caso. Inviable en la RTX 3050. |

Detalle y tablas completas en [`docs/comparacion_modelos.md`](docs/comparacion_modelos.md).

## Estado del Trabajo (Entregable 1)
* Pruebas empíricas de línea base (*zero-shot*) completadas.
* Ejecutado 100% de forma local (Edge AI) en un entorno híbrido: Workstation Windows (NVIDIA RTX 3050 6GB) y Apple Silicon (MacBook Air M4), utilizando Ollama con cuantización a 4-bits.
* Los registros de evidencia empírica están disponibles en la carpeta `/experiments`, demostrando que los modelos de 3B a 8B fallan catastróficamente en tareas matemáticas y de retención lógica si no están apoyados por descomposición y herramientas deterministas.

## Entregable 3 (en curso): un benchmark que no se sature

La E2 cerró con 51/51 en test (etiqueta `e2-final`). Antes de construir los agentes de la E3
se endureció el benchmark, por dos razones medidas:

1. **El criterio de la E1 se satura solo.** `e1_strict` castiga aprobar de más, pero no
   rechazar de más: **rechazar todo** obtiene 51/51 en test, 12/12 en OOD y 4/4 en real
   (`results/ref_reject_all*`). Desde la E3, `e1_strict` se reporta siempre junto a
   `full_correct`, las tasas de aprobación indebida y de rechazo falso por propiedad, e
   intervalos de Wilson (`python3 -m matcher.metrics`).
2. **Las plantillas.** `test/` sale del generador. OOD ya mostró la caída (9/12 ciego).

| Set | Casos × avisos | Aprobadas esperadas | Uso en la E3 |
|---|---|---|---|
| `hard_dev/` | 10 × 7 | 44 % | ajuste |
| **`hard_test/`** | 30 × 8 | 47 % | **evaluación principal**, congelado (`MANIFEST.sha256`) |
| `test/` | 51 × ~7 | 30 % | regresión (continuidad con E1 y E2) |
| `ood/` | 12 × ~6 | 27 % | pasa a ser dev: ya se usó para diagnosticar g3 |
| `real_e3/` | 20 × 4 (2 compradores) | 6 % (5/80) | evaluación sobre texto real, doble anotación humana |

Los avisos hard están escritos a mano y cubren 16 fenómenos con cuotas mínimas: jerga
("620 lucas", "3 palos"), cifras en palabras, varios montos en un aviso, arriendo en UF,
notaciones de dormitorios, mascotas condicionadas, distancias en km, cuadras o minutos,
casi-cumplimientos, distractores, correcciones dentro del aviso, comprador sin mascota o sin
auto, y otros. El protocolo se escribió antes que los casos
([`data/cases/hard_test/README.md`](data/cases/hard_test/README.md)), y `scripts/build_hard.py`
verifica cada anotación contra `rules.py`. El segundo comprador y el segundo sorteo de
avisos reales quedaron preregistrados antes de descargar nada
([`data/cases/real/PREREGISTRO_E3.md`](data/cases/real/PREREGISTRO_E3.md)).

```bash
python3 scripts/build_hard.py --check                    # anotación == rules.py, cuotas, congelamiento
cd src && python3 -m matcher.metrics --cases ../data/cases/hard_dev \
    --runs ref_reject_all_hard_dev baseline_phi4_hard_dev tools_phi4_v5_hard_dev_g3
```

**Control de dificultad sobre `hard_dev`** (16-oct-2026, M4). Es la medición que justifica
el set: la solución de la E2 ya no satura.

| Run | e1_strict | full_correct | exactitud por aviso | aprob. indebida | rechazo falso |
|---|---|---|---|---|---|
| Rechazar todo (piso) | 10/10 | 0/10 | 39/70 | 0/39 | 31/31 |
| Baseline phi4-mini | 0/10 | 0/10 | 38/70 | 5/39 | 27/31 |
| Solución E2 (v5 + g3) | **4/10** | **0/10** | 52/70 | 4/39 | 14/31 |

Mecanismo de los fallos de la E2 en dev: las 4 aprobaciones indebidas son de mascotas
("consultar reglamento", "según reglamento", "hasta cinco kilos": un límite en palabras queda
`null` y se lee como "sin límite"). Los 2 errores aritméticos son arriendos en UF tratados
como pesos (ROI 0). El resto son rechazos falsos (jerga, cifras en palabras, notaciones de
dormitorios). Son los objetivos de los agentes de la E3, y `hard_test` mide si esas mejoras
generalizan.

### Sistema multiagente (`src/agents`)

Tres agentes con el mismo phi4-mini, prompts versionados en `prompts/<agente>/v1.md`, y
diseño, técnicas y ablaciones en [`docs/e3_agentes.md`](docs/e3_agentes.md):

- **Lector:** el extractor de la E2 sin cambios. Copia el fragmento de cada tema.
- **Verificador:** revisa solo los campos que la herramienta marca como dudosos. Confirma,
  corrige con evidencia literal (la herramienta `comprobar` la valida), pide releer al Lector
  o declara el dato no verificable.
- **Decisor:** ve el resultado de la herramienta `evaluar` y decide si cierra o le consulta un
  dato al Verificador.

Cada mensaje entre agentes y herramientas queda en `results/<run>/<caso>.trace.jsonl`.

| Set de desarrollo | Run | e1_strict | full_correct | exactitud por aviso | aprob. indebida | rechazo falso |
|---|---|---|---|---|---|---|
| `hard_dev` | Solución E2 (v5 + g3) | 4/10 | 0/10 | 52/70 | 4/39 | 14/31 |
| `hard_dev` | **Agentes v1** | **10/10** | **8/10** | **69/70** | **0/39** | **1/31** |
| `ood` | Solución E2 (v5 + g3) | 11/12 | 7/12 | 67/70 | 0/51 | 3/19 |
| `ood` | **Agentes v1** | **12/12** | **10/12** | **68/70** | **0/51** | **2/19** |
| `train` (20 primeros) | **Agentes v1** | 20/20 | 20/20 | 140/140 | 0/101 | 0/39 |

Estas cifras son de **ajuste**: los agentes se iteraron mirando `hard_dev`, así que no prueban
nada por sí solas. `train` y `ood` sirvieron de control de regresión, y ahí se encontraron dos
reglas ajustadas a `hard_dev` que rompían avisos del generador («previa autorización de la
administración» leído como si remitiera a un reglamento; «Santiago Centro» ≠ «Santiago» en el
ranking). Se corrigieron antes de cualquier corrida de evaluación. La evaluación es `hard_test` (después de la revisión humana), más `test`,
`ood` y `real_e3`.

> **Convención E3 (29-oct).** En la revisión humana de `hard_test` el equipo cambió dos reglas
> para todos los sets: un aviso sin política de mascotas no se descarta (va al final del orden) y
> un estudio o loft cuenta como 1 dormitorio (`data/cases/hard_test/REVIEW.md`). El juez, la E2,
> el baseline y el Decisor (`prompts/decisor/v2.md`) se actualizaron, y todo se corre de nuevo con
> `bash scripts/run_e3.sh todo` (`baseline_e3_*`, `e2_e3_*`, `agents_v2_*`).

**Evaluación final (convención E3, agentes v2, 29-oct-2026, M4).** `hard_test` se corrió una
sola vez, después de la revisión humana. Entre corchetes, IC de Wilson al 95 %.

| Set | Run | e1_strict | full_correct | exactitud por aviso | aprob. indebida | rechazo falso |
|---|---|---|---|---|---|---|
| `hard_test` | Rechazar todo (piso) | 30/30 | 0/30 | 127/240 | 0/127 | 113/113 |
| `hard_test` | Baseline (prompt directo) | 1/30 | 0/30 | 118/240 | 38/127 | 84/113 |
| `hard_test` | Solución E2 (v5 + g3) | 11/30 | 1/30 | 193/240 | 0/127 | 47/113 [33–51 %] |
| `hard_test` | **Agentes v2** | **23/30** | **5/30** | **214/240** | 6/127 [2–10 %] | **20/113** [12–26 %] |
| `real_e3` | Rechazar todo (piso) | 20/20 | 15/20 | 75/80 | 0/75 | 5/5 |
| `real_e3` | Baseline (prompt directo) | 0/20 | 0/20 | 59/80 | 17/75 | 4/5 |
| `real_e3` | Solución E2 (v5 + g3) | 20/20 | 18/20 | 78/80 | 0/75 | 2/5 |
| `real_e3` | **Agentes v2** | **20/20** | **20/20** | **80/80** | **0/75** | **0/5** |

Ablaciones (`agents_v2_sin_*_hard_test`), `test`, `ood` y `hard_dev`: pendientes, ver
`bash scripts/run_e3.sh tablas`.

Dónde fallan los agentes en `hard_test` (todo en las herramientas de Python, no en los agentes):

- **5 aprobaciones indebidas por estacionamiento** («uso común (no asignado)», «en la vía
  pública», «opción de comprar», «ya fue vendido», «+ estacionamiento $8.000.000»). `anclar` los
  lee como propio o asignado sin marcar duda, así que el Verificador no los revisa. La E2 rechazaba
  esos 5 avisos, pero por dormitorios: no leía «2D.» ni «3D.». Los agentes arreglan esa lectura
  y queda expuesto el error de estacionamiento (`results/agents_v2_hard_test/ht_27.trace.jsonl`,
  HT-2708).
- **7 rechazos falsos por mascotas.** `comprobar` no acepta «perros OK», «gatos OK» ni «gatos y
  perros sin restricción» como permiso explícito. La duda queda sin resolver y no aprueba.

No se corrigieron: `hard_test` se corre una sola vez.

Evaluación con la convención anterior (agentes v1, historial):

| Set | Run | e1_strict | full_correct | exactitud por aviso | aprob. indebida | rechazo falso |
|---|---|---|---|---|---|---|
| `real_e3` | Rechazar todo (piso) | 20/20 | 17/20 | 77/80 | 0/77 | 3/3 |
| `real_e3` | Baseline (prompt directo) | 0/20 | 0/20 | 59/80 | 18/77 | 3/3 |
| `real_e3` | Solución E2 (v5 + g3) | 20/20 | 19/20 | 79/80 | 0/77 | 1/3 |
| `real_e3` | **Agentes v1** | **20/20** | **20/20** | **80/80** | **0/77** | **0/3** |
| `test` | Solución E2 (v5 + g3) | 51/51 | 51/51 | 352/352 | 0/246 | 0/106 |
| `test` | **Agentes v1** | **51/51** | **51/51** | **352/352** | **0/246** | **0/106** |

`real_e3` son avisos reales con doble anotación humana, pero solo 3 de 80 deben aprobarse: el
piso llega a 17/20, así que confirma que no hay regresión y discrimina poco. La única diferencia
con la E2 es REAL-23 (`real_b2_005`): el Verificador recupera «Precio: UF 2.490.», que el Lector
no había copiado. En `test`, un JSON truncado del Decisor (`test_0016`) se cerró por defecto con
el resultado de `evaluar`, y el caso salió correcto igual. El costo es ~80 s por caso (E2: ~30 s).

```bash
export PYTHONPATH=src
python3 -m agents.run --split hard_dev --run agents_v1_hard_dev     # ~70 s por caso en un M4
python3 -m agents.show results/agents_v1_hard_dev/hd_04.trace.jsonl # la conversación entre agentes
bash scripts/run_e3.sh final && bash scripts/run_e3.sh ablaciones   # evaluación, una sola vez
python3 -m pytest tests/test_agents.py -q                           # sin Ollama
```

## Entregable 2

### Estructura

```
src/matcher/
│  # infraestructura compartida por baseline y solución (no cambia entre ambos)
├── schema.py        # dataclasses del caso (hard + soft constraints, propiedades con `text` + `truth`)
├── rules.py         # las 5 hard constraints + ROI + ranking -> salida esperada (solo la ve el juez)
├── verifier.py      # juez 0/1: parseo estricto + comparación, con motivo del fallo
├── prompt.py        # el prompt del baseline (y del modo cot)
├── generate.py      # generador de casos sintéticos auto-verificados
├── run_model.py     # baseline: corre un modelo de Ollama sobre un split
├── evaluate.py      # tabla comparativa entre runs
│  # la solución de la E2 (descomposición + herramientas)
├── extract.py       # paso 1: el modelo copia spans de UNA propiedad (JSON Schema); prompts v1..v5
├── grounding.py     # ancla los spans al aviso y los parsea (v5): el código interpreta, no el modelo
├── normalize.py     # UF->CLP, ROI, distancias: la aritmética que el LLM ya no hace
├── constraints.py   # paso 2: las 5 hard constraints sobre los hechos extraídos + JSON final
├── pipeline.py      # las 4 estrategias: baseline | cot | decomp_llm | tools
├── run_pipeline.py  # corre una estrategia sobre un split (mismo layout que run_model.py)
├── reground.py      # re-decide un run existente con el grounding actual, sin llamar al modelo
├── extract_report.py# exactitud de la extracción campo a campo vs `truth` (lectura de límites)
└── demo.py          # baseline vs solución sobre el mismo caso, en vivo (para el video)
data/
├── prompt_base.txt          # prompt de la E1 (histórico)
├── perfil_comprador_ejemplo.json  # el comprador de la E1 (también el del set real)
├── prompt_e2_case_001.txt   # prompt de la E2 renderizado para el caso de la E1
├── scout/                   # estaciones de metro/tren (OpenStreetMap) y perfil de ejemplo de scout
└── cases/
    ├── test/     # 50 casos held-out + case_001_e1. Solo evaluación, una corrida por estrategia.
    ├── train/    # 300 casos. Split dev: se usan para iterar el prompt del extractor. Nunca se reportan.
    ├── ood/      # 12 casos con avisos ESCRITOS A MANO (ver su README). Control de generalización.
    ├── real/     # 4 casos con 16 avisos REALES de portales, sorteados y anotados a mano (ver su README)
    └── real_fallo/  # el aviso real que reveló la aprobación falsa de g3 (no sorteado)
results/<run>/    # <case_id>.txt (salida juzgada) + .meta.json (tokens, tiempo) + .trace.json (hechos y decisiones)
results/archive/  # runs anteriores no comparables (p.ej. baselines sin soft constraints)
results/README.md # índice: qué es cada carpeta de results/ y de dónde sale
scripts/run_baselines.sh    # los 3 candidatos con prompting directo
scripts/run_e2.sh           # baseline + solución (+ ablaciones con ALL=1) y la tabla
scripts/build_ood.py        # los avisos del set OOD, con su anotación auto-verificada
scripts/sample_real.py      # sorteo del set real (no pisa la instantánea sin --force)
scripts/build_real.py       # anotación del set real y del caso de fallo, auto-verificada
scripts/build_estaciones_rm.py  # regenera data/scout/estaciones_rm.json desde OpenStreetMap
docs/comparacion_modelos.md # compromiso de modelo, con los números
docs/e2_pipeline.md         # la solución en detalle: intervención, ablaciones, resultados, límites
docs/scout.md               # scout: supuestos sobre cada portal, ética del scraping, límites
src/scout/        # extensión posterior a la E2: busca avisos reales en 5 portales y los analiza
experiments/      # evidencia de la E1 (logs de prompting directo, benchmarks de hardware)
tests/            # 244 tests (pytest), sin Ollama ni red
```

### 1. Prompt y verificador determinista

**Prompt** (`src/matcher/prompt.py`): es el prompt del **baseline** (prompting directo).
La solución no lo usa: descompone la tarea y el modelo ve un prompt distinto, mucho más
corto, por propiedad (ver `extract.py`). Lo que se mantiene idéntico entre baseline y
solución es la **entrada** (perfil + catálogo crudo), el **esquema de salida** y el
**juez**. Usa el esquema de salida del PDF de
la E1 (`approved_matches[].{id, price_clp, roi_pct}`, `rejected[].{id,
failed_constraints}`) y conserva las **soft constraints** del prompt de la E1
(`data/prompt_base.txt`): ubicación preferida y ROI no descalifican, pero fijan
el orden de `approved_matches` (comuna preferida primero, luego ROI descendente;
las primeras 3 son el Top 3). Incluye una instrucción explícita de formato (sin
ella phi4-mini envuelve el JSON en fences en 50/51 casos y el baseline falla por
formato en vez de por lógica). Ver `data/prompt_e2_case_001.txt`.

Desviaciones declaradas respecto a `prompt_base.txt`: se quitan los campos
`distance_to_transport_m` y `ranking_score_justificacion` (no verificables, no
están en el esquema del PDF) y el ranking se expresa por el **orden** de la lista,
que sí es verificable.

**Verificador** (`src/matcher/verifier.py`): juez 0/1 sin LLM. Cada propiedad
tiene `text` (lo que ve el modelo) y `truth` (campos estructurados que solo usa
el juez). Reporta dos niveles, siempre juntos:

| Nivel | Qué mide |
|---|---|
| `e1_strict` | Las 3 condiciones de la E1 sobre la respuesta cruda: (1) aprueba una propiedad que viola una hard constraint → `false_approval`; (2) `price_clp` (±1 CLP) o ROI (±0,05 pp) mal → `arithmetic_error`; (3) texto fuera del JSON, fences, `<think>`, esquema incumplido, ids inexistentes/repetidos → `schema_error`. |
| `e1_after_extract` | Mismas 3 condiciones tras un extractor determinista que quita fences/`<think>` y recorta al JSON. Separa fallos de formato de fallos de razonamiento. |
| `exact_match` | Métrica secundaria: el conjunto aprobado y rechazado coincide exactamente con el esperado. Se reporta porque el criterio E1 no penaliza rechazos falsos. |
| `ranking_ok` | Métrica secundaria (soft constraints): `exact_match` y `approved_matches` en el orden esperado (comuna preferida → ROI desc; empates en cualquier orden). |
| `full_correct` | `e1_strict` ∧ `exact_match` ∧ `ranking_ok`: conjunto y orden esperados. Es la métrica más exigente. No compara la lista `failed_constraints` de cada rechazo (la E1 no la exige); para la solución v5 + g3 coincide en 246/246 rechazos de test y 44/51 de OOD. |

Ids se normalizan (`"[PROP-A42]"` ≡ `"PROP-A42"`); el nombre de la clave ROI
acepta `roi_pct` (PDF E1) y `roi_calculado_pct` (prompt_base.txt).

### 2. Dataset sintético

```bash
cd src && python3 -m matcher.generate --train 300 --test 50 --seed 2026
```

El generador construye primero el `truth` con un escenario intencionado por
propiedad (≈30 % pasan todo; el resto falla por presupuesto en UF/CLP, distancia,
estacionamiento, dormitorios, mascotas por peso/especie/ausencia, o dos a la vez),
luego renderiza el texto con plantillas en español y los mismos distractores que
provocaron los fallos de la E1 (precio "bajo presupuesto según el tasador",
"negociable", "15 minutos caminando", estacionamiento "de visitas", dormitorio
"convertible", límite de peso 1 kg bajo la mascota). Cada perfil tiene 1–2
comunas preferidas; ≈45 % de las propiedades caen en ellas, y las que además
violan una hard constraint llevan la trampa "¡En la comuna favorita del cliente!"
(la soft constraint no rescata). Cada caso se auto-verifica con `rules.py` antes
de escribirse. `test/` incluye además `case_001_e1.json`,
el caso original de la E1 anotado a mano.

### 3. La solución de la E2: descomposición + herramientas

El baseline pide al modelo, en una sola llamada, leer 5–9 avisos, convertir UF→CLP, comparar
5 restricciones por aviso, calcular ROI, ordenar y formatear. La solución separa **percepción**
de **decisión**:

1. **Extracción** (`extract.py` + `grounding.py`): una llamada por propiedad, con
   decodificación restringida por JSON Schema. El modelo **no ve el perfil del comprador** y no
   decide nada: solo copia el fragmento del aviso que habla de cada tema (precio, dormitorios,
   distancia, estacionamiento, mascotas) y responde tres preguntas cerradas sobre mascotas.
2. **Anclaje** (`grounding.py`): cada fragmento copiado debe existir en el aviso. La unidad del
   precio se lee del **aviso**, no del modelo; un número inventado deja el campo como *no
   verificable*, y un campo no verificable **nunca aprueba**.
3. **Decisión** (`normalize.py` + `constraints.py`): Python convierte UF→CLP, calcula el ROI,
   evalúa las 5 restricciones y ordena por las soft constraints. El LLM nunca multiplica ni
   compara magnitudes.

| Fallo diagnosticado en la E1 | Componente que lo ataca |
|---|---|
| Confusión aritmética (UF→CLP, ROI, inecuaciones) | la conversión y las comparaciones son código (`normalize.py`, `constraints.py`) |
| Colapso lógico (condicionales cruzados) | una propiedad por llamada; cada restricción es una comparación aislada |
| Atención selectiva (frases de marketing) | el extractor no ve el perfil: no hay decisión que sesgar |
| Texto conversacional / esquema roto | JSON Schema en la extracción; el JSON final lo ensambla código |

La intervención tiene dos piezas versionadas por separado y ambas reproducibles: el
**prompt del extractor** (`v1`…`v5`, lo que se le pide al modelo) y la **capa de anclaje**
(`g1`…`g3`, lo que el código hace con lo que el modelo devuelve). Se eligen con
`--prompt-version` y `--grounding`. Detalle completo, ablaciones, la iteración del prompt
(v1→v5), la de la capa (g1→g3) y los límites medidos en
[`docs/e2_pipeline.md`](docs/e2_pipeline.md).

### 4. Resultados

phi4-mini 3.8B, temperatura 0, semilla 0, mismo verificador para todas las filas.
`e1_strict` es el criterio de corrección del Entregable 1 (no aprobar lo que viola una
restricción, no errar la aritmética, no romper el esquema). `full_correct` exige además
que el conjunto aprobado y su orden sean exactamente los esperados.

**Test — 51 casos held-out** (sintéticos, generados con plantillas):

| Estrategia | e1_strict | full_correct | aprob. indebida | aritmética | esquema | tok/caso | s/caso M4 · RTX |
|---|---|---|---|---|---|---|---|
| Baseline (prompting directo) | 0/51 | 0 | 40 | 6 | 5 | 346 | 15,8 · 11,9 |
| A · CoT (procedimiento por pasos, 1 llamada) | 0/51 | 0 | 43 | 4 | 4 | 326 | 21,0 |
| B · Descomposición sin herramientas (mismos hechos que la solución) | 0/51 | 0 | 34 | 8 | 9 | 1377 | 59,3 |
| C · Solución, extractor v1 + anclaje g1 | 30/51 | 22 | 20 | 1 | 0 | 674 | 29,7 · 31,0 |
| **C · Solución, extractor v5 + anclaje g3** | **51/51** | **51** | **0** | **0** | **0** | 1056 | 35,3 · 43,2 |

La fila B es la ablación limpia: el LLM recibe **exactamente los mismos hechos** que Python
(v5 + g3; 352/352 propiedades idénticas) y solo tiene que convertir UF→CLP, comparar, calcular
el ROI y armar el JSON. Acierta 0/51, contra 51/51 cuando lo hace Python: el fallo diagnosticado
en la E1 no es de lectura sino de cálculo y decisión. (Una primera corrida de B con el extractor
v2, `decomp_phi4`, también dio 0/51; ver `docs/e2_pipeline.md`.)

Con la solución v5 + g3 el veredicto coincide **caso por caso** entre la MacBook M4 y la RTX 3050
(51/51 en ambas). En las demás filas hay diferencias menores entre máquinas (misma semilla,
distinto backend numérico): el baseline tiene 40 aprobaciones indebidas en la M4 y 38 en la
RTX, v1 + g1 acierta 30 y 29 casos, y v5 + g1 da 40 y 42 en `full_correct` (`results/*_rtx*/`).

**OOD — 12 casos escritos a mano** (`data/cases/ood/`, 70 propiedades): fichas de portal,
WhatsApp sin tildes, MAYÚSCULAS con erratas, cifras en palabras, `135 millones`,
`UF 4.250,5`, `2D+servicio`, distancias solo en minutos. Ninguna plantilla del generador.

| Estrategia | e1_strict | full_correct | aprob. indebida | aritmética |
|---|---|---|---|---|
| Baseline | 0/12 | 0 | 7 | 4 |
| Solución v5 + g1 | 8/12 | 4 | 4 | 0 |
| Solución v5 + g2 | 9/12 | 5 | 3 | 0 |
| Solución v5 + g3 | 11/12 | 7 | 0 | 1 |

**La caída de 51/51 a 9/12 entre test y OOD es el resultado más informativo del trabajo**:
mide cuánto de la solución dependía de las plantillas del generador. El 9/12 es g2, la única
medición ciega; las cinco correcciones de g3 se escribieron mirando estos casos, así que su
11/12 no cuenta como medición de generalización. El baseline también se
derrumba en OOD (0/12), así que la comparación se sostiene. Los cinco fallos que quedan
están documentados con su mecanismo en [`docs/e2_pipeline.md`](docs/e2_pipeline.md): cuatro
son rechazos falsos o de ranking (el sistema se equivoca siendo conservador) y uno rompe
`e1_strict` por una unidad de jerga (`"620 lucas"` = $620.000).

Sobre esos mismos 70 avisos, el valor final de cada campo es correcto en: precio 97 %,
distancia 99 %, mascotas 99 %, estacionamiento 94 %, arriendo 90 % y dormitorios 89 %. Si se
descuentan los casos que rescató la recuperación por código de g2/g3 (el span del modelo no
ancló y el código buscó la frase en el aviso), lo que el modelo localiza solo es: precio 97 %,
distancia 96 %, mascotas 96 %, estacionamiento 91 % y arriendo 90 %. En dormitorios localiza
solo 47 % (33/70); el resto lo recupera el fallback `ND/`. Esa es la medida de lo que aporta
el LLM una vez que la interpretación vive en el código (`extract_report --run
tools_phi4_v5_ood_g3 --cases ../data/cases/ood` y los `warnings` de cada `.trace.json`).

**Real — 16 avisos de portales, sorteados** (`data/cases/real/`): 4 casos con un aviso de
Yapo, Chilepropiedades, iCasas y TocToc cada uno. Se sortearon con semilla fija, 4 por portal
(de 160, 80, 120 y 1.838 unidades respectivamente), **antes** de leerlos; se anotaron a mano y
se evaluaron con el comprador de la E1.
El texto de cada propiedad es la ficha que arma `src/scout` (sección 6).

| Estrategia | e1_strict | full_correct | aprob. indebida | aritmética | esquema |
|---|---|---|---|---|---|
| Baseline | 0/4 | 0 | 3 | 0 | 1 |
| **Solución v5 + g3** | **4/4** | **4** | **0** | **0** | **0** |

Con ese comprador (perro de 18 kg, $150 M, estacionamiento) **ningún aviso debe aprobarse**:
solo 3 de 16 declaran aceptar mascotas, y los tres fallan en otra restricción. El set mide
aprobaciones indebidas y lectura, no aciertos positivos. El baseline aprueba, por ejemplo,
un departamento de UF 6.000 "a $60.000.000" (~$246 M reales). Campo a campo, la solución
lee bien precio, distancia, mascotas y estacionamiento en 16/16. En dormitorios falla 2/16,
justo los dos que la anotación marcó como ambiguos (un estudio y un aviso cuyo portal dice
4D y cuyo texto describe 5).

**Fallo real de la solución** (`data/cases/real_fallo/`, no sorteado): en un aviso de
Chilepropiedades, el modelo copió "Se aceptan ofertas. Se acepta canje con corredores."
como cláusula de mascotas y "La administración cuenta con opción de arriendo de
estacionamientos" como la de estacionamiento. g3 leyó "acepta" como "acepta mascotas" y
dejó el estacionamiento en la rama por defecto `propio`. Resultado: **aprobación indebida**
de un aviso que no dice nada de mascotas y no incluye estacionamiento. En los casos
sintéticos la cláusula de mascotas siempre hablaba de mascotas, así que el defecto no tenía
cómo aparecer. La versión **g4** exige que esa cláusula nombre mascotas y trata el
estacionamiento "en arriendo"/"opción de" como no incluido. Da salidas **idénticas** a g3 en
test, dev, OOD y el set real, y corrige este caso. g3 sigue siendo la versión reportada.

### 5. Reproducir lo que muestra el video

```bash
ollama pull phi4-mini:latest          # digest 78fad5d182a7, Q4_K_M, 2,5 GB
pip install -r requirements.txt       # Python ≥ 3.9
python3 -m pytest tests -q            # 244 tests, sin Ollama

cd src
# baseline y solución sobre el MISMO caso, en vivo, con el veredicto de ambos (~50 s)
python3 -m matcher.demo --case case_001_e1     # el caso original de la E1
python3 -m matcher.demo --random               # un caso al azar del set de test
python3 -m matcher.demo --split ood --case ood_002   # caso de fallo: "620 lucas" -> ROI 0,01 en vez de 6,0
python3 -m matcher.demo --split real --random --seed 7                      # aviso REAL sorteado (~30 s)
python3 -m matcher.demo --split real_fallo --case fallo_001 --grounding g3  # fallo real: aprueba de más
python3 -m matcher.demo --split real_fallo --case fallo_001 --grounding g4  # corregido

# la tabla completa a partir de los resultados versionados en results/ (no llama al modelo)
python3 -m matcher.evaluate --runs baseline_phi4 cot_phi4 decomp_phi4_v5 tools_phi4_v1 tools_phi4_v5_g3
python3 -m matcher.extract_report --run tools_phi4_v5_g3           # errores de extracción campo a campo

# el set OOD escrito a mano (avisos que ninguna plantilla generó)
python3 -m matcher.evaluate --runs baseline_phi4_ood tools_phi4_v5_ood_g3 --cases ../data/cases/ood
# el set real (avisos de portales, sorteados y anotados)
python3 -m matcher.evaluate --runs baseline_phi4_real tools_phi4_v5_real_g3 tools_phi4_v5_real_g4 --cases ../data/cases/real
python3 -m matcher.evaluate --runs baseline_phi4_real_fallo tools_phi4_v5_real_fallo_g3 tools_phi4_v5_real_fallo_g4 --cases ../data/cases/real_fallo
```

Guion sugerido para el video (≤ 3:00, todo en vivo, sin cortes que oculten la ejecución):

| Tiempo | Qué se muestra | Comando |
|---|---|---|
| 0:00–0:20 | tarea, fallo de la E1 y pipeline (diagrama del PDF) | — |
| 0:20–1:00 | **aviso real sorteado**, baseline y solución lado a lado, con veredicto | `demo --split real --random --seed 7` |
| 1:00–1:30 | resultados sobre conjuntos declarados: test, OOD, real | los `evaluate` de arriba (no llaman al modelo) |
| 1:30–2:10 | **caso de fallo real** y su mecanismo: g3 aprueba de más, g4 no | `demo --split real_fallo ... --grounding g3` y luego `g4` |
| 2:10–2:40 | búsqueda en vivo en un portal (con caché) | `python3 -m scout --perfil ../data/scout/perfil_ejemplo.json --fuentes toctoc --max-por-fuente 2` |
| 2:40–3:00 | límites: estudios, conflictos portal/texto, mascotas no declaradas | — |

La semilla 7 elige `real_003`; cualquier otra semilla sirve, y el sorteo se hace en
cámara, así que el caso no se eligió a favor del sistema.

Para regenerar los resultados desde cero (baseline + solución, ~45 min en la M4):

```bash
bash scripts/run_e2.sh          # o ALL=1 bash scripts/run_e2.sh para incluir las ablaciones
SPLIT=ood bash scripts/run_e2.sh   # el set OOD -> baseline_phi4_ood, tools_phi4_v5_ood_g3
SPLIT=real bash scripts/run_e2.sh  # el set real -> baseline_phi4_real, tools_phi4_v5_real_g3
```

Las filas `v5 + g2` y `v5 + g3` no son corridas nuevas del modelo: `matcher.reground` vuelve
a decidir sobre los spans ya extraídos por `tools_phi4_v5` con la capa nueva. Como la capa
de anclaje solo procesa la salida del modelo (temperatura 0, semilla 0), equivale a correrla
en vivo, y por eso comparten tokens y tiempos con la corrida original.

Se puede interrumpir y retomar: los casos ya respondidos se omiten. Cada corrida deja la
salida cruda, los tokens/tiempos y los hechos extraídos por propiedad en `results/<run>/`,
así que todo número de este README y del PDF es trazable a un archivo del repositorio.

### 6. Extensión: buscar avisos reales en portales (`src/scout`)

Posterior a la E2 y fuera de sus cifras. Pregunta al comprador sus filtros, busca en Yapo,
PortalPM, Chilepropiedades, iCasas y TocToc, calcula la distancia al metro con las
coordenadas del aviso y OpenStreetMap, y pasa cada aviso por el mismo analizador (phi4-mini
+ extractor v5 + anclaje). Clasifica en **aprobadas**, **por revisar** (no incumplen nada
verificable, pero falta un dato, típicamente mascotas) y **rechazadas**.

```bash
cd src
python3 -m scout                                              # cuestionario interactivo
python3 -m scout --perfil ../data/scout/perfil_ejemplo.json   # perfil desde JSON
```

Respeta robots.txt, se identifica como bot y, si un portal lo bloquea, lo registra y sigue
con los demás. Con avisos reales apareció una aprobación falsa que los casos sintéticos no
podían mostrar ("Se aceptan ofertas" leído como "acepta mascotas"). Se corrigió en una versión
nueva del anclaje, **g4**, que da salidas idénticas a g3 en test, dev, OOD y el set real. Detalle,
supuestos sobre cada portal y límites en [`docs/scout.md`](docs/scout.md).

### 7. Correr los modelos candidatos (comparación de la E1)

```bash
pip install -r requirements.txt
python3 -m pytest tests -q

ollama pull phi4-mini:latest            # ollama pull acepta un modelo por llamada
ollama pull granite4.1:8b
ollama pull deepseek-r1:7b
bash scripts/run_baselines.sh            # los tres (900 s/caso, como la tabla); o: bash scripts/run_baselines.sh phi4
LIMIT=3 bash scripts/run_baselines.sh    # prueba rápida
```

Cada modelo corre con temperatura 0 y seed 0 sobre los 51 casos de `test/`.
DeepSeek-R1 recibe `num_predict 8192` porque razona en `<think>` antes del JSON
(con 2048 se trunca sin responder); eso lo hace ~20× más lento y queda reflejado
en las columnas `truncated`, `mean_output_tokens` y `mean_wall_s`.

Tiempos medidos en MacBook Air M4: phi4-mini 15,8 s/caso, granite 31,8 s/caso,
deepseek-r1 323 s/caso.
Las respuestas crudas quedan en `results/baseline_<modelo>/` (se versionan: son la
evidencia trazable) y la tabla en `results/summary.csv`. Interrumpir y retomar es
seguro: los casos ya respondidos se omiten.


Comandos individuales:

```bash
cd src
python3 -m matcher.prompt ../data/cases/test/test_0001.json                 # ver el prompt de un caso
python3 -m matcher.run_model --model phi4-mini:latest --run baseline_phi4   # un modelo
python3 -m matcher.verifier ../data/cases/test/case_001_e1.json respuesta.txt   # un veredicto
python3 -m matcher.evaluate --runs baseline_phi4 baseline_granite baseline_deepseek
```
