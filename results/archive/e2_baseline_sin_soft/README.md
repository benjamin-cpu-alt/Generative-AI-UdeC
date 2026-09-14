# Baselines archivados — prompt SIN soft constraints (12–13 sep 2026)

Corridos sobre la versión anterior del dataset (seed 2026, sin `soft_constraints`)
y del prompt (sin ubicación preferida ni ranking). **No son comparables** con los
runs actuales: el prompt y los casos cambiaron al reincorporar las soft constraints
de la E1. Se conservan como evidencia de la primera pasada.

| Modelo | Params | e1_strict | e1_after_extract | exact_match | fail_schema | fail_false_approval | fail_arithmetic | raw_wrapped | truncated | tokens/resp | s/resp (M4) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| phi4-mini | 3.8B | 1/51 | 1/51 | 2 | 3 | 29 | 18 | 4 | 1 | 343 | 13.3 |
| granite4.1 | 8B | 0/51 | 0/51 | 2 | 8 | 32 | 11 | 0 | 0 | 316 | 29.7 |
| deepseek-r1 | 7B | 1/50 | 7/50 | 4 | 17 | 20 | 6 | 40 | 9 | 2787 | 188.0 |

Aprobaciones indebidas por restricción (tras extractor):

| Restricción | Inválidas | phi4 | granite | deepseek |
|---|---|---|---|---|
| presupuesto | 77 | 16 (21%) | 33 (43%) | 4 (5%) |
| mascotas | 95 | 24 (25%) | 4 (4%) | 14 (15%) |
| distancia_transporte | 38 | 9 (24%) | 6 (16%) | 1 (3%) |
| dormitorios | 32 | 9 (28%) | 4 (12%) | 10 (31%) |
| estacionamiento | 42 | 4 (10%) | 4 (10%) | 5 (12%) |

Hallazgos: phi4 falla por razonamiento (magnitud en UF→CLP, reglas aplicadas de forma
inconsistente) con formato casi resuelto; granite replica el fallo A42 (presupuesto 43%),
sobre-rechaza por mascotas, ROI con fórmula errónea (69–86%) y pone ids en ambas listas;
deepseek razona mejor (presupuesto 5%, distancia 3%) pero 40/50 con fences, 9/50 agotan
8192 tokens en `<think>` y devuelven vacío, 5 escriben la fórmula en vez del número, 14× el
costo de phi4.
