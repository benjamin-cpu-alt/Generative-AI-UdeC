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

## Entregable 2: Verificador determinista

El verificador (`src/matcher/`) es el juez 0/1 del proyecto. Aplica el criterio de
corrección del Entregable 1 sobre la salida de cualquier modelo, sin usar un LLM.
Se usa tres veces: para filtrar el dataset de destilación, para evaluar el baseline
y para evaluar la solución.

### Estructura

```
src/matcher/
├── schema.py     # dataclasses del caso (perfil, propiedades con `text` + `truth`)
├── rules.py      # las 5 hard constraints + ROI -> salida esperada (ground truth)
├── verifier.py   # parseo estricto + comparación -> 0/1 y motivo del fallo
├── evaluate.py   # runner sobre data/cases/test/*.json y results/<run>/*.txt -> CSV
├── prompt.py     # renderiza el prompt (mismo para baseline y solución) desde un caso
├── generate.py   # generador de casos sintéticos auto-verificados
└── run_model.py  # corre un modelo de Ollama sobre un split y guarda respuestas crudas
results/<run>/    # <case_id>.txt (respuesta cruda) + <case_id>.meta.json (tokens, tiempo)
data/cases/
├── test/         # 50 casos held-out + case_001_e1 (el de la E1). Solo evaluación.
└── train/        # 300 casos para generar el dataset de destilación. Nunca se evalúan.
tests/            # 27 tests (pytest): juez, generador y prompt
```

Cada propiedad de un caso tiene `text` (lo que ve el modelo) y `truth` (campos
estructurados que solo usa el verificador), más `scenario`/`trap` que documentan
qué distractor se construyó.

### Criterio de corrección

**Métrica principal (`e1_correct`)** — idéntica a las 3 condiciones del Entregable 1.
Una respuesta es incorrecta (0) si:

1. Aprueba una propiedad que viola cualquier hard constraint → `false_approval`
2. Falla la aritmética: `price_clp` (±1 CLP) o ROI (±0,05 pp) → `arithmetic_error`
3. Contiene texto fuera del JSON, fences markdown, bloques `<think>`, o no cumple
   el esquema (claves faltantes, ids inexistentes o repetidos) → `schema_error`

**Métrica secundaria (`exact_match`)** — el conjunto aprobado y el rechazado
coinciden exactamente con el esperado. Se reporta porque el criterio E1 no
penaliza rechazos falsos (una respuesta que rechaza todo obtiene 1 en `e1_correct`).

### Uso

```bash
pip install -r requirements.txt
python -m pytest tests -q                       # verifica el juez

# Un caso, una respuesta:
cd src && python -m matcher.verifier ../data/cases/test/case_001_e1.json respuesta.txt

# Prompt que ve el modelo para un caso:
cd src && python -m matcher.prompt ../data/cases/test/test_0001.json

# Baseline: prompting directo con Ollama sobre los 51 casos de test (temperatura 0, seed 0)
cd src && python -m matcher.run_model --model phi4-mini:latest --run baseline_phi4

# Evaluación sobre el split test. Lee results/<run>/<case_id>.txt
cd src && python -m matcher.evaluate --runs baseline_phi4 distill_phi4
# -> results/<run>.csv (por caso) y results/summary.csv (accuracy por run)
```

`evaluate.py` reporta además una columna de **diagnóstico** `e1_if_format_ignored`:
cuántas respuestas serían correctas si se ignoraran fences markdown o bloques
`<think>`. No forma parte del criterio; separa los fallos de *formato* de los de
*lógica/aritmética* para la sección de límites.

### Dataset sintético

`data/cases/` se regenera de forma determinista con:

```bash
cd src && python -m matcher.generate --train 300 --test 50 --seed 2026
```

El generador construye primero el `truth` con un escenario intencionado por
propiedad (≈30 % pasan todo, el resto falla por presupuesto en UF/CLP, distancia,
estacionamiento, dormitorios, mascotas por peso/especie/ausencia, o dos a la vez),
luego renderiza el texto con plantillas en español y los mismos distractores que
provocaron los fallos de la E1 (precio "bajo presupuesto" según el tasador,
"negociable", "15 minutos caminando", estacionamiento "de visitas", dormitorio
"convertible", límite de peso 1 kg bajo la mascota). Cada caso se auto-verifica
con `rules.py` antes de escribirse: si el juez no coincide con el escenario, la
generación aborta.
