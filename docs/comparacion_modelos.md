# Comparación de modelos candidatos (Entregable 2 — compromiso de modelo)

Los tres candidatos del Entregable 1 se corren con **prompting directo** y el
**mismo prompt** (`src/matcher/prompt.py`) sobre los **51 casos held-out** de
`data/cases/test/` (50 sintéticos + el caso original de la E1). Se juzgan con el
mismo verificador determinista (`src/matcher/verifier.py`).

Cómo regenerar esta tabla:

```bash
bash scripts/run_baselines.sh          # ~10-30 min por modelo según hardware
python3 -m matcher.evaluate --runs baseline_phi4 baseline_granite baseline_deepseek   # desde src/
```

## 1. Tabla de resultados (copiar de `results/summary.csv`)

| Modelo | Params | e1_strict | e1_after_extract | exact_match | ranking_ok | full_correct | fail_schema | fail_false_approval | fail_arithmetic | tokens/resp | s/resp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| phi4-mini | 3.8B | 0/51 | 0/51 | 1/51 | 1/51 | 0/51 | 5 | 40 | 6 | 346 | 15.8 |
| granite4.1 | 8.0B | 0/51 | 0/51 | 0/51 | 0/51 | 0/51 | 8 | 42 | 1 | 265 | 31.8 |
| deepseek-r1-distill-qwen | 7.0B | 0/51 | 2/51 | 2/51 | 1/51 | 0/51 | 26 | 18 | 5 | 4996 | 323.3 |

Corrida del 15-sep-2026 (`results/summary_baselines.csv`), timeout 900 s/caso. DeepSeek queda
truncado en 22/51 casos aun con `num_predict 8192` (de ahí sus 26 `fail_schema`): el `<think>`
consume el presupuesto antes de emitir el JSON.

> Resultados de la primera pasada (prompt sin soft constraints, no comparable):
> `results/archive/e2_baseline_sin_soft/README.md`.

- `e1_strict`: criterio E1 literal sobre la respuesta cruda.
- `e1_after_extract`: mismo criterio tras un extractor determinista que quita fences/`<think>`.
  Separa fallos de **formato** de fallos de **razonamiento**.
- `ranking_ok` / `full_correct`: soft constraints (orden por comuna preferida y ROI). No forman
  parte del criterio E1; `full_correct` es la métrica más exigente y la que debe crecer hasta la E4.
- `fail_*`: motivo del fallo tras extractor. Es la columna que dice *por qué* falla cada modelo.

## 2. Aprobaciones indebidas por restricción (copiar de `results/<run>_breakdown.csv`)

| Restricción | Inválidas en test | phi4 aprueba | granite aprueba | deepseek aprueba |
|---|---|---|---|---|
| presupuesto | 69 | 23 (33%) | 35 (51%) | 10 (14%) |
| mascotas | 83 | 16 (19%) | 10 (12%) | 9 (11%) |
| distancia_transporte | 37 | 5 (14%) | 14 (38%) | 1 (3%) |
| dormitorios | 41 | 11 (27%) | 11 (27%) | 12 (29%) |
| estacionamiento | 34 | 1 (3%) | 2 (6%) | 3 (9%) |

Mapea directo al diagnóstico de la E1: presupuesto/distancia ↔ atención selectiva
(frases de marketing), dormitorios/mascotas ↔ colapso lógico, `fail_arithmetic` ↔
confusión aritmética.

## 3. Criterios de decisión

El modelo elegido es el que maximiza la suma de la rúbrica, no el que mejor rinde en
baseline. Argumentar sobre estos ejes, en este orden:

1. **Economía de modelo (10 pts):** puntaje completo al modelo más pequeño que
   *funcione*. Phi-4-mini (3.8B) parte con ventaja; Granite (8B) y DeepSeek (7B)
   deben justificar los parámetros extra con una mejora que la intervención no pueda
   dar a Phi-4-mini.
2. **Naturaleza del fallo:** un modelo que falla por *formato* (`raw_wrapped` alto,
   `e1_after_extract` ≫ `e1_strict`) se arregla con decodificación restringida; uno que
   falla por *aritmética* en la misma proporción tras extractor necesita herramientas.
   Ninguno de los dos tipos de fallo se resuelve con más parámetros.
3. **Costo de inferencia:** tokens/resp y s/resp en el hardware declarado. DeepSeek-R1
   razona en `<think>` y puede emitir 5–10× más tokens; en la RTX 3050 eso pesa.

## 4. Decisión

Elegimos **Phi-4-mini (3.8B)**. Los tres candidatos dan **0/51** con prompting directo, así
que los parámetros extra no compran corrección en esta tarea: el fallo no es de capacidad
general sino de *tipo* (aritmética, inecuaciones y formato), y eso se ataca con descomposición
y herramientas, no con un modelo mayor. Siendo el más pequeño de los tres, maximiza el criterio
de economía de modelo sin ceder nada. Además, el rol que la E1 le asignó era exactamente
"resolver la tarea si se le guía dividiendo el problema en pasos simples": la E2 ejecuta esa
hipótesis y la confirma (**51/51** `e1_strict` con la solución; ver `docs/e2_pipeline.md`).

Descartamos **Granite 4.1 (8B)** porque no cumple el rol por el que fue propuesto —formato
JSON estricto—: tiene más fallos de esquema que Phi (8 vs 5) y la peor tasa de aprobación
indebida por presupuesto (51 % vs 33 %). Descartamos **DeepSeek-R1-Distill-Qwen (7B)** porque,
pese a razonar mejor (9 % de aprobación indebida por presupuesto), tampoco acierta ningún caso,
falla 26 veces por esquema al emitir `<think>` antes del JSON, y cuesta ~4.996 tokens y ~323 s
por caso con 22 respuestas truncadas: inviable como sistema en la RTX 3050 de 6 GB. Su ventaja
—razonar por pasos— es justamente lo que la descomposición le da a Phi-4-mini sin pagar 7B.

## 5. Evidencia anecdótica para el video

Caso `case_001_e1` (el de la E1): qué hizo cada modelo con PROP-A42 (trampa
"¡bajo el presupuesto!"), PROP-D05 (dormitorio convertible) y el ROI de PROP-F61.
Ver `results/<run>/case_001_e1.txt`.
