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

Los tres candidatos se corrieron con el mismo prompt directo sobre los 51 casos held-out y los
tres dan **0/51**: los parámetros extra no compran corrección en esta tarea.

| Candidato E1 | Params | e1_strict | Decisión |
|---|---|---|---|
| **Phi-4-mini** | **3.8B** | **0/51** | **Elegido**: mismo resultado que los grandes, con el menor costo y la menor huella. La E1 le asignó el rol de "resolver la tarea si se le guía dividiendo el problema en pasos simples": la E2 ejecuta esa hipótesis. |
| Granite 4.1 | 8.0B | 0/51 | Propuesto por su formato JSON estricto (BFCL), tiene **más** fallos de esquema que Phi (8 vs 5) y la peor tasa de aprobación indebida por presupuesto (51 %). |
| DeepSeek-R1-Distill-Qwen | 7.0B | 0/51 | Razona mejor (9 % de aprobación indebida por presupuesto vs 33 %) pero no alcanza a acertar un solo caso, falla 26 veces por esquema (emite `<think>` antes del JSON) y cuesta ~4.996 tokens y ~323 s por caso, con 22 respuestas truncadas. Inviable en la RTX 3050. |

Detalle y tablas completas en [`docs/comparacion_modelos.md`](docs/comparacion_modelos.md).

## Estado del Trabajo (Entregable 1)
* Pruebas empíricas de línea base (*zero-shot*) completadas.
* Ejecutado 100% de forma local (Edge AI) en un entorno híbrido: Workstation Windows (NVIDIA RTX 3050 6GB) y Apple Silicon (MacBook Air M4), utilizando Ollama con cuantización a 4-bits.
* Los registros de evidencia empírica están disponibles en la carpeta `/experiments`, demostrando que los modelos de 3B a 8B fallan catastróficamente en tareas matemáticas y de retención lógica si no están apoyados por descomposición y herramientas deterministas.

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
├── prompt_e2_case_001.txt   # prompt de la E2 renderizado para el caso de la E1
└── cases/
    ├── test/     # 50 casos held-out + case_001_e1. Solo evaluación, una corrida por estrategia.
    └── train/    # 300 casos. Split dev: se usan para iterar el prompt del extractor. Nunca se reportan.
results/<run>/    # <case_id>.txt (salida juzgada) + .meta.json (tokens, tiempo) + .trace.json (hechos y decisiones)
results/archive/  # runs anteriores no comparables (p.ej. baselines sin soft constraints)
scripts/run_baselines.sh    # los 3 candidatos con prompting directo
scripts/run_e2.sh           # baseline + solución (+ ablaciones con ALL=1) y la tabla
docs/comparacion_modelos.md # compromiso de modelo, con los números
docs/e2_pipeline.md         # la solución en detalle: intervención, ablaciones, resultados, límites
tests/            # 163 tests (pytest), sin Ollama
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
| `full_correct` | `e1_strict` ∧ `exact_match` ∧ `ranking_ok`: la salida completa es la esperada. Es la métrica más exigente y la que debe mostrar la mejora E2→E4. |

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

Detalle completo, ablaciones e iteración del prompt del extractor (v1→v5) en
[`docs/e2_pipeline.md`](docs/e2_pipeline.md).

### 4. Resultados (51 casos held-out, temperatura 0, semilla 0)

| Estrategia (phi4-mini 3.8B) | e1_strict | full_correct | aprob. indebida | aritmética | esquema | tok/caso | s/caso M4 · RTX |
|---|---|---|---|---|---|---|---|
| Baseline (prompting directo) | 0/51 | 0 | 40 | 6 | 5 | 346 | 15,8 · 11,9 |
| A · CoT (procedimiento por pasos, 1 llamada) | 0/51 | 0 | 43 | 4 | 4 | 326 | 21,0 |
| B · Descomposición sin herramientas (decide el LLM) | 0/51 | 0 | 41 | 4 | 6 | 991 | 51,4 |
| C · Descomposición + herramientas, extractor v1 | 30/51 | 22 | 20 | 1 | 0 | 674 | 29,7 · 31,0 |
| **C · Descomposición + herramientas, extractor v5** | **51/51** | **40** | **0** | **0** | **0** | 1056 | 35,3 · 43,2 |

Las dos cifras dicen cosas distintas y las dos se reportan:

* **`e1_strict` = 51/51** — bajo el criterio de corrección de la E1 (no aprobar lo que viola una
  restricción, no errar la aritmética, no romper el esquema) la solución no falla nunca, y el
  veredicto coincide **caso por caso** entre la M4 y la RTX 3050.
* **`full_correct` = 40/51** — bajo el criterio completo (además, conjunto exacto y orden
  correcto) quedan 11 casos: 9 rechazos falsos y 2 de ranking. Nunca una aprobación indebida.
  El sistema se equivoca **siendo conservador**, que es la dirección segura para esta tarea.

Los fallos residuales son de **percepción**, no de cálculo: "Solo se admiten gatos" leído como
prohibición, y `pets_text` rellenado con los nombres del esquema cuando el aviso no menciona
mascotas. Están documentados con su mecanismo en [`docs/e2_pipeline.md`](docs/e2_pipeline.md).

### 5. Reproducir lo que muestra el video

```bash
ollama pull phi4-mini:latest          # digest 78fad5d182a7, Q4_K_M, 2,5 GB
pip install -r requirements.txt
python3 -m pytest tests -q            # 163 tests, sin Ollama

cd src
# baseline y solución sobre el MISMO caso, en vivo, con el veredicto de ambos (~50 s)
python3 -m matcher.demo --case case_001_e1     # el caso original de la E1
python3 -m matcher.demo --random               # un caso al azar del set de test

# la tabla completa a partir de los resultados versionados en results/ (no llama al modelo)
python3 -m matcher.evaluate --runs baseline_phi4 cot_phi4 decomp_phi4 tools_phi4_v1 tools_phi4_v5
python3 -m matcher.extract_report --run tools_phi4_v5     # errores de extracción campo a campo
```

Para regenerar los resultados desde cero (baseline + solución, ~45 min en la M4):

```bash
bash scripts/run_e2.sh          # o ALL=1 bash scripts/run_e2.sh para incluir las ablaciones
```

Se puede interrumpir y retomar: los casos ya respondidos se omiten. Cada corrida deja la
salida cruda, los tokens/tiempos y los hechos extraídos por propiedad en `results/<run>/`,
así que todo número de este README y del PDF es trazable a un archivo del repositorio.

### 6. Correr los modelos candidatos (comparación de la E1)

```bash
pip install -r requirements.txt
python3 -m pytest tests -q

ollama pull phi4-mini:latest granite4.1:8b deepseek-r1:7b
bash scripts/run_baselines.sh            # los tres; o: bash scripts/run_baselines.sh phi4
LIMIT=3 bash scripts/run_baselines.sh    # prueba rápida
```

Cada modelo corre con temperatura 0 y seed 0 sobre los 51 casos de `test/`.
DeepSeek-R1 recibe `num_predict 8192` porque razona en `<think>` antes del JSON
(con 2048 se trunca sin responder); eso lo hace ~10× más lento y queda reflejado
en las columnas `truncated`, `mean_output_tokens` y `mean_wall_s`.

Tiempos de referencia en MacBook Air M4: phi4-mini ≈ 10 s/caso, granite ≈ 25 s/caso,
deepseek-r1 ≈ 2–5 min/caso.
Las respuestas crudas quedan en `results/baseline_<modelo>/` (se versionan: son la
evidencia trazable) y la tabla en `results/summary.csv`. Interrumpir y retomar es
seguro: los casos ya respondidos se omiten.

Para argumentar el compromiso de modelo, llenar `docs/comparacion_modelos.md`
con `results/summary.csv` y `results/<run>_breakdown.csv`.

Comandos individuales:

```bash
cd src
python3 -m matcher.prompt ../data/cases/test/test_0001.json                 # ver el prompt de un caso
python3 -m matcher.run_model --model phi4-mini:latest --run baseline_phi4   # un modelo
python3 -m matcher.verifier ../data/cases/test/case_001_e1.json respuesta.txt   # un veredicto
python3 -m matcher.evaluate --runs baseline_phi4 baseline_granite baseline_deepseek
```
