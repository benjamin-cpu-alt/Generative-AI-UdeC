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
| phi4-mini | 3.8B | /51 | /51 | /51 | /51 | /51 | | | | | |
| granite4.1 | 8.0B | /51 | /51 | /51 | /51 | /51 | | | | | |
| deepseek-r1-distill-qwen | 7.0B | /51 | /51 | /51 | /51 | /51 | | | | | |

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
| presupuesto | | | | |
| mascotas | | | | |
| distancia_transporte | | | | |
| dormitorios | | | | |
| estacionamiento | | | | |

Mapea directo al diagnóstico de la E1: presupuesto/distancia ↔ atención selectiva
(frases de marketing), dormitorios/mascotas ↔ colapso lógico, `fail_arithmetic` ↔
confusión aritmética.

## 3. Criterios de decisión

El modelo elegido es el que maximiza la suma de la rúbrica, no el que mejor rinde en
baseline. Argumentar sobre estos ejes, en este orden:

1. **Economía de modelo (10 pts):** puntaje completo al modelo más pequeño que
   *funcione*. Phi-4-mini (3.8B) parte con ventaja; Granite (8B) y DeepSeek (7B)
   deben justificar los parámetros extra con una mejora que la destilación no pueda
   dar a Phi-4-mini.
2. **Naturaleza del fallo:** un modelo que falla por *formato* (`raw_wrapped` alto,
   `e1_after_extract` ≫ `e1_strict`) es arreglable con destilación; uno que falla por
   *aritmética* en la misma proporción tras extractor tiene un techo más bajo.
3. **Costo de inferencia:** tokens/resp y s/resp en el hardware declarado. DeepSeek-R1
   razona en `<think>` y puede emitir 5–10× más tokens; en la RTX 3050 eso pesa.
4. **Factibilidad de fine-tuning local:** QLoRA sobre 3.8B cabe en 6 GB de VRAM con
   margen; sobre 7–8B es ajustado.

## 4. Decisión

> _(Completar con los números.)_ Elegimos **___** porque ___. Descartamos ___ porque ___
> y ___ porque ___.

## 5. Evidencia anecdótica para el video

Caso `case_001_e1` (el de la E1): qué hizo cada modelo con PROP-A42 (trampa
"¡bajo el presupuesto!"), PROP-D05 (dormitorio convertible) y el ROI de PROP-F61.
Ver `results/<run>/case_001_e1.txt`.
