# E3 · Sistema multiagente

Tres agentes con el **mismo modelo** (phi4-mini, 3.8B, Ollama, temperatura 0, semilla 0). Cada
agente decide qué pasa después; el orquestador (`src/agents/orchestrator.py`) solo ejecuta esa
decisión dentro de un presupuesto de rondas y registra **cada mensaje** en
`results/<run>/<caso>.trace.jsonl`. Los prompts están versionados fuera del código, en
`prompts/<agente>/v1.md`.

```
                 spans                    hechos + dudas (⚠)
 aviso ──► LECTOR ──────► [anclar] ──────────────────────────► VERIFICADOR ──┐
             ▲                                                  │  │  │      │ sin dudas
             │ releer (≤2 rondas)                                │  │  │      ▼
             └───────────────────────────────────────────────────┘  │  │   [evaluar] ──► DECISOR ──cerrar──► [ordenar] ──► JSON
                                          corregir(evidencia, valor) │  │                  │
                                [comprobar] ◄────────────────────────┘  │                  │ consultar(id, campo) (≤1 ronda)
                                     │ rechazo + motivo (≤1 reintento)  │                  │
                                     └──────────────────────────────────┘ ◄────────────────┘
```

## Agentes

| | Lector | Verificador | Decisor |
|---|---|---|---|
| Rol | Copia del aviso el fragmento literal de cada tema. No conoce al comprador. | Revisa si lo leído dice lo mismo que el aviso, solo en los campos que `anclar` marca como dudosos. No conoce al comprador. | Ve el resultado de `evaluar` de todos los avisos del caso y decide si está listo o si falta un dato. |
| Prompt | `prompts/lector/v1.md` (`system` = `SYSTEM_V5` de la E2, sin cambios; `relectura` nueva) | `prompts/verificador/v1.md` (`revisar`, `retro`, `consulta`) | `prompts/decisor/v1.md` (`decidir`; `sin_herramientas` para la ablación) |
| Herramientas | `anclar` (grounding g3 de la E2 + conversión a CLP/m) | `comprobar` (la evidencia debe estar en el aviso; el código interpreta el valor, también cifras en palabras y jerga) | `evaluar` (5 restricciones, estado cumple/falla/no_verificable), `ordenar` (JSON de la E1) |
| Entrada | Texto de un aviso (y, en relectura, los campos que devuelve el Verificador con su motivo) | Aviso + tabla campo / fragmento / dato leído, con ⚠ y la frase donde mirar | Perfil del comprador + texto y evaluación de cada aviso |
| Salida (JSON Schema) | 8 fragmentos + 3 respuestas cerradas de mascotas | `revisiones[]`: campo, acción, evidencia, valor | `accion` ∈ {cerrar, consultar}, `consultas[]`: id, campo, motivo |
| Decide | Por campo releído: fragmento nuevo o `null` («el aviso no lo dice») | Por campo: `confirmar` · `corregir` (→ `comprobar`) · `releer` (→ Lector) · `no_verificable`; tras un rechazo de `comprobar`: corregir de nuevo, `mantener` o `no_verificable` | `cerrar` (→ `ordenar`, fin) o `consultar` (→ Verificador) |
| Parada / traspaso | Siempre entrega a `anclar` → Verificador | Sin objeciones → Decisor. Máx. 2 relecturas y 1 reintento por aviso | `cerrar`, o presupuesto: 1 ronda de consultas (máx. 4) |

Reglas de seguridad (deterministas, en el orquestador y las herramientas):

- Un dato que sigue sin leerse **nunca aprueba**: la restricción queda `no_verificable` y falla (igual que en la E2).
- `comprobar` rechaza evidencia que no está en el aviso, evidencia sobre **otra propiedad** («en el mismo edificio se vende otra unidad…»), montos inverosímiles (un «precio» de $720.000) y permisos de mascotas que remiten a un reglamento.
- Una duda sobre mascotas que nadie resolvió deja el permiso como no explícito.
- Una consulta del Decisor solo se ejecuta si el campo dejó una restricción `no_verificable`, y una sola vez.

## Técnicas de prompting (taxonomía: Schulhoff et al., 2024, *The Prompt Report*)

| Técnica | Agente | Dónde se ve | Ablación |
|---|---|---|---|
| Role prompting | los tres | primera línea de cada `system` | — |
| Instrucciones zero-shot con reglas por campo | Lector, Verificador | `system` | — |
| Descomposición (una llamada por aviso; leer ≠ verificar ≠ decidir) | los tres | arquitectura | — (es la E2) |
| Salida estructurada con decodificación restringida (JSON Schema, acciones como `enum`) | los tres | `format` de Ollama | **−esquema** |
| Few-shot en línea (pares «texto» → valor, con números que no están en ningún set) | Verificador | «Cómo escribir el valor» | — |
| Grounding de la salida en evidencia literal (*verification*) | Verificador | campo `evidencia` + `comprobar` | **−literal** |
| Self-refine / relectura iterativa | Lector ↔ Verificador, Decisor → Verificador | `relectura`, `consulta` | **−refinar** |
| Crítica con herramienta (tipo CRITIC: el rechazo de la herramienta vuelve al agente con su motivo) | Verificador | `retro` | **−retro** |
| Herramientas para el cálculo (tipo PAL / *tool use*): el agente decide, el código calcula | Decisor | `evaluar`, `ordenar` | **−herramientas_A3** |
| Foco por señales de la herramienta (campos ⚠ con la frase donde mirar) | Verificador | tabla de `revisar` | — |

## Reproducir

```bash
export PYTHONPATH=src
python3 -m agents.run --split hard_dev --run agents_v1_hard_dev          # iterar (solo dev)
python3 -m agents.show results/agents_v1_hard_dev/hd_01.trace.jsonl      # ver la conversación
bash scripts/run_e3.sh final        # una vez, después de la revisión humana de hard_test
bash scripts/run_e3.sh ablaciones
python3 -m pytest tests/test_agents.py -q   # sin Ollama: herramientas, prompts y bucles
```
