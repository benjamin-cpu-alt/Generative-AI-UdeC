# Índice de `results/`

Cada carpeta es una corrida: `<case_id>.txt` (la salida que juzga `verifier.py`),
`<case_id>.meta.json` (modelo, opciones, tokens, tiempo) y, en las estrategias
descompuestas, `<case_id>.trace.json` (hechos extraídos y decisión por propiedad). Todas se
evalúan con `cd src && python3 -m matcher.evaluate --runs <run> [--cases ../data/cases/<split>]`.

**Corrida del modelo** = se llamó a phi4-mini. **Re-decisión** = `matcher.reground` volvió a
decidir sobre los spans ya extraídos de otra corrida con otra capa de anclaje, sin llamar al
modelo (por eso comparte tokens y tiempos con su origen, que queda en `meta.json` como
`source_run`). Máquina: M4 salvo las que llevan `_rtx` (RTX 3050).

## Test (51 casos held-out)

| Carpeta | Qué es | Tipo |
|---|---|---|
| `baseline_phi4`, `baseline_phi4_rtx` | baseline: prompting directo | modelo |
| `baseline_granite`, `baseline_deepseek` | los otros dos candidatos de la E1 (`docs/comparacion_modelos.md`). 22 `.txt` de DeepSeek están vacíos: respuestas truncadas | modelo |
| `cot_phi4` | ablación A: procedimiento por pasos en una llamada | modelo |
| `decomp_phi4_v5` | ablación B limpia: el LLM decide sobre los mismos hechos que la solución | modelo |
| `decomp_phi4` | ablación B con el extractor v2 (primera versión, reemplazada por la anterior) | modelo |
| `tools_phi4_v1`, `tools_phi4_v1_rtx` | solución, extractor v1 + anclaje g1 | modelo |
| `tools_phi4_v1_reground`, `tools_phi4_v1_rtx_reground` | cota superior de v1 con la capa de anclaje, sin re-extraer | re-decisión |
| `tools_phi4_v2_partial` | extractor v2, detenida en 16 casos: v2 perdió en dev (13/30 vs 21/30). No se reporta; su `meta.run` conserva el nombre de entonces, `tools_phi4` | modelo |
| `tools_phi4_v5`, `tools_phi4_v5_rtx` | solución, extractor v5 + anclaje g1 | modelo |
| `tools_phi4_v5_g2`, `tools_phi4_v5_rtx_g2` | v5 + g2 | re-decisión |
| **`tools_phi4_v5_g3`**, `tools_phi4_v5_rtx_g3` | **v5 + g3: la solución reportada** | re-decisión |

## Dev (los primeros 30 casos de `train/`, solo para iterar el extractor)

| Carpeta | Qué es | Tipo |
|---|---|---|
| `dev_tools_v1` … `dev_tools_v5` | una por versión del prompt del extractor | modelo |
| `dev_tools_v5_reground` | v5 re-decidida tras los dos ajustes de anclaje aprendidos en dev (antes de versionar la capa) | re-decisión |
| `dev_tools_v5_g2`, `dev_tools_v5_g3` | v5 + g2 y v5 + g3 | re-decisión |

## OOD (12 casos escritos a mano, `--cases ../data/cases/ood`)

| Carpeta | Qué es | Tipo |
|---|---|---|
| `baseline_phi4_ood` | baseline | modelo |
| `tools_phi4_v5_ood` | la corrida del modelo, hecha con g2: **la medición ciega** | modelo |
| `tools_phi4_v5_ood_g1`, `_g2`, `_g3` | la misma extracción con cada capa (`_g2` repite la decisión de la corrida original) | re-decisión |

## Real (avisos de portales, `--cases ../data/cases/real` y `../data/cases/real_fallo`)

| Carpeta | Qué es | Tipo |
|---|---|---|
| `baseline_phi4_real`, `baseline_phi4_real_fallo` | baseline | modelo |
| `tools_phi4_v5_real_g3`, `tools_phi4_v5_real_fallo_g3` | solución v5 + g3 | modelo |
| `tools_phi4_v5_real_g4`, `tools_phi4_v5_real_fallo_g4` | la misma extracción con g4 (posterior a la E2) | re-decisión |

## Otros

- `archive/e2_baseline_sin_soft/`: baselines con el prompt y el dataset anteriores a
  reincorporar las soft constraints. No comparables (ver su README).
- `archive/baseline_deepseek_timeout600_25casos/`: primera corrida de DeepSeek con timeout
  de 600 s; quedó con 25 de 51 respuestas y se reemplazó por `baseline_deepseek` (900 s).
- `baseline_phi4.log`: registro de consola de la corrida del baseline. Los demás `.log` y
  todos los `.csv` de esta carpeta no se versionan: se regeneran con `matcher.evaluate`.
- `scout/`: caché y reportes de `python3 -m scout` (no se versiona).
