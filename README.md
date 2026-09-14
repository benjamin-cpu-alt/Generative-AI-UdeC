# Real Estate AI Matcher (Generative AI - 580694)

**Miembros del Equipo:** Benjamín Grandón V, Carla Maureira V.  
**Curso:** Generative Artificial Intelligence 
**Profesor:** Carlos Navarrete, PhD  

## La Tarea
Matching Automático Comprador-Propiedad con Optimización de Restricciones Cruzadas.  
El sistema actúa como un motor de validación basado en agentes que lee descripciones de propiedades no estructuradas y las evalúa frente a reglas estrictas del comprador. Esto incluye resolver operaciones matemáticas dinámicas (conversiones de UF a CLP, cálculos de ROI) y restricciones espaciales o lógicas. *(El prompt base y los datos de prueba se encuentran en la carpeta `/data`)*.

## Modelos Candidatos
1. **DeepSeek-R1-Distill-Qwen (7.0B) [PRINCIPAL]:** Resuelve las alucinaciones aritméticas mediante el uso de Cadena de Pensamiento (CoT).
2. **Granite 4.1 (8.0B):** Resuelve el colapso de formato, garantizando un esquema JSON estricto para que el sistema pueda procesarlo sin errores.
3. **Phi-4-mini (3.8B):** Propuesto para investigar si una arquitectura multi-agente puede mitigar su severo colapso lógico, manteniendo al mismo tiempo un consumo de memoria ultra-bajo (Edge AI).

## Estado del Trabajo (Entregable 1)
* Pruebas empíricas de línea base (*zero-shot*) completadas.
* Ejecutado 100% de forma local (Edge AI) en un entorno híbrido: Workstation Windows (NVIDIA RTX 3050 6GB) y Apple Silicon (MacBook Air M4), utilizando Ollama con cuantización a 4-bits.
* Los registros de evidencia empírica están disponibles en la carpeta `/experiments`, demostrando que los modelos de 3B a 8B fallan catastróficamente en tareas matemáticas y de retención lógica si no están apoyados por un sistema de agentes (Agentic Harness).

## Entregable 2

### Estructura

```
src/matcher/
├── schema.py     # dataclasses del caso (hard + soft constraints, propiedades con `text` + `truth`)
├── rules.py      # las 5 hard constraints + ROI + ranking por soft constraints -> salida esperada
├── verifier.py   # juez 0/1: parseo estricto + comparación, con motivo del fallo (+ ranking_ok)
├── prompt.py     # el prompt (único, compartido por baseline y solución)
├── generate.py   # generador de casos sintéticos auto-verificados
├── run_model.py  # corre un modelo de Ollama sobre un split y guarda respuestas crudas
└── evaluate.py   # tabla comparativa: dos niveles de corrección + desglose + costo
data/
├── prompt_base.txt          # prompt de la E1 (histórico)
├── prompt_e2_case_001.txt   # prompt de la E2 renderizado para el caso de la E1
└── cases/
    ├── test/     # 50 casos held-out + case_001_e1. Solo evaluación.
    └── train/    # 300 casos para el dataset de destilación. Nunca se evalúan.
results/<run>/    # <case_id>.txt (respuesta cruda) + <case_id>.meta.json (tokens, tiempo)
results/archive/  # runs anteriores no comparables (p.ej. baselines sin soft constraints)
scripts/run_baselines.sh   # corre los 3 candidatos y produce la tabla
docs/comparacion_modelos.md # plantilla para argumentar el compromiso de modelo
tests/            # 32 tests (pytest)
```

### 1. Prompt y verificador determinista

**Prompt** (`src/matcher/prompt.py`): mismo texto para baseline y solución; la
intervención cambia el modelo, no el prompt. Usa el esquema de salida del PDF de
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

### 3. Correr los modelos candidatos

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
