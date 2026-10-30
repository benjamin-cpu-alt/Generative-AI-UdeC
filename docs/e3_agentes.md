# E3 · Sistema multiagente

Tres agentes con el **mismo modelo** (phi4-mini, 3.8B, Ollama, temperatura 0, semilla 0). Cada
agente decide qué pasa después; el orquestador (`src/agents/orchestrator.py`) solo ejecuta esa
decisión dentro de un presupuesto de rondas y registra **cada mensaje** en
`results/<run>/<caso>.trace.jsonl`. Los prompts están versionados fuera del código, en
`prompts/<agente>/v1.md` (Decisor: `v2.md`, convención E3).

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
| Prompt | `prompts/lector/v1.md` (`system` = `SYSTEM_V5` de la E2, sin cambios; `relectura` nueva) | `prompts/verificador/v1.md` (`revisar`, `retro`, `consulta`) | `prompts/decisor/v2.md` (`decidir`; `sin_herramientas` para la ablación) |
| Herramientas | `anclar` (grounding g3 de la E2 + conversión a CLP/m) | `comprobar` (la evidencia debe estar en el aviso; el código interpreta el valor, también cifras en palabras y jerga) | `evaluar` (5 restricciones, estado cumple/falla/no_verificable; mascotas también sin_confirmar), `ordenar` (JSON de la E1) |
| Entrada | Texto de un aviso (y, en relectura, los campos que devuelve el Verificador con su motivo) | Aviso + tabla campo / fragmento / dato leído, con ⚠ y la frase donde mirar | Perfil del comprador + texto y evaluación de cada aviso |
| Salida (JSON Schema) | 8 fragmentos + 3 respuestas cerradas de mascotas | `revisiones[]`: campo, acción, evidencia, valor | `accion` ∈ {cerrar, consultar}, `consultas[]`: id, campo, motivo |
| Decide | Por campo releído: fragmento nuevo o `null` («el aviso no lo dice») | Por campo: `confirmar` · `corregir` (→ `comprobar`) · `releer` (→ Lector) · `no_verificable`; tras un rechazo de `comprobar`: corregir de nuevo, `mantener` o `no_verificable` | `cerrar` (→ `ordenar`, fin) o `consultar` (→ Verificador) |
| Parada / traspaso | Entrega a `anclar`. Lo que copia (o deja en `null`) decide la ruta del aviso: sin dudas va directo al Decisor; con dudas, al Verificador. En relectura revisa su salida o responde `null`, y el Verificador vuelve a mirar ese campo | Sin objeciones → Decisor. Máx. 2 relecturas y 1 reintento por aviso | `cerrar`, o presupuesto: 1 ronda de consultas (máx. 4) |

Reglas de seguridad (deterministas, en el orquestador y las herramientas):

- Un dato que sigue sin leerse **nunca aprueba**: la restricción queda `no_verificable` y falla (igual que en la E2).
- `comprobar` rechaza evidencia que no está en el aviso, evidencia sobre **otra propiedad** («en el mismo edificio se vende otra unidad…»), montos inverosímiles (un «precio» de $720.000) y permisos de mascotas que remiten a un reglamento.
- Convención E3 (revisión humana de `hard_test`): un aviso que no declara política de mascotas
  queda `sin_confirmar`, se aprueba si cumple lo demás y va al final del orden. Un estudio o loft
  cuenta como 1 dormitorio. El Verificador anota el hecho («Estudio» = 0 dormitorios separados,
  como el `truth` de los casos) y la regla la aplican `evaluar` (`max(dormitorios, 1)`) y el juez
  (`rules.py`). Por eso `prompts/verificador/v1.md` no cambió con la convención.
- Una duda sobre el permiso de mascotas que nadie resolvió **no** es lo mismo que el silencio:
  la restricción queda `no_verificable` y falla (podría haber una restricción no leída).
- Una consulta del Decisor solo se ejecuta si el campo dejó una restricción `no_verificable` (o
  mascotas `sin_confirmar`), y una sola vez.

### Por qué el Lector es un agente, y su límite

El Lector es el agente con menos autonomía, y lo declaramos. En la primera pasada siempre
entrega a `anclar`. Su decisión está en el contenido: copiar un fragmento o responder `null` por
campo. Eso determina si `anclar` marca dudas, y por lo tanto si el aviso pasa directo al Decisor
o va al Verificador. Cuando el Verificador lo devuelve, decide por campo entre revisar su propia
salida o responder que el aviso no lo dice, que son dos de las acciones de la definición del
curso. Separarlo del Verificador es lo que permite que quien revisa no sea quien copió. El
Lector no ve la tabla de dudas, así que no puede «defender» su lectura. Y conserva el extractor
de la E2 sin cambios, de modo que la mejora de la E3 no se confunda con un extractor mejor.

## Técnicas de prompting (taxonomía: Schulhoff et al., 2024, *The Prompt Report*)

| Técnica | Agente | Dónde se ve | Ablación |
|---|---|---|---|
| Role prompting | los tres | primera línea de cada `system` | — |
| Instrucciones zero-shot con reglas por campo | Lector, Verificador | `system` | — |
| Descomposición (una llamada por aviso; leer ≠ verificar ≠ decidir) | los tres | arquitectura | — (es la E2) |
| Salida estructurada con decodificación restringida (JSON Schema, acciones como `enum`) | los tres | `format` de Ollama | **−esquema** |
| Few-shot en línea (pares «texto» → valor, con números que no están en ningún set) | Verificador | «Cómo escribir el valor» | — (no medida) |
| Grounding de la salida en evidencia literal (*verification*) | Verificador | campo `evidencia` + `comprobar` | **−literal** |
| Self-refine / relectura iterativa | Lector ↔ Verificador, Decisor → Verificador | `relectura`, `consulta` | **−refinar** |
| Crítica con herramienta (tipo CRITIC: el rechazo de la herramienta vuelve al agente con su motivo) | Verificador | `retro` | **−retro** |
| Herramientas para el cálculo (tipo PAL / *tool use*): el agente decide, el código calcula | Decisor | `evaluar`, `ordenar` | **−herramientas_A3** |
| Foco por señales de la herramienta (campos ⚠ con la frase donde mirar) | Verificador | tabla de `revisar` | — |

Qué no se ablaciona, y por qué:

- **Lector.** Su prompt es `SYSTEM_V5` de la E2 sin cambios. Sus técnicas (descomposición y copia
  literal con anclaje) se midieron en las ablaciones de la E2 ([`e2_pipeline.md`](e2_pipeline.md)).
  En la E3 solo cambia que pueda volver a leer, y eso es −refinar.
- **Role prompting, reglas zero-shot y foco ⚠** son el enunciado de la tarea de cada agente.
  Quitarlos no deja un agente degradado, sino uno sin tarea.
- **Few-shot en línea del Verificador.** No se midió. Es la ablación pendiente más clara: los
  ejemplos cubren jerga y cifras en palabras, justo donde los agentes mejoran sobre la E2.

## Lectura de las ablaciones (`hard_test`)

- **−refinar quita una técnica que actúa en dos bucles** (relectura del Lector y consulta del
  Decisor). Las trazas de la corrida full separan el aporte de cada uno. Las 5 relecturas no
  cambian ningún estado: lo que `evaluar` entrega al Decisor es idéntico con y sin refinar en los
  30 casos, y la primera propuesta del Decisor también. El Decisor consulta en 24 casos (41
  consultas). 38 no cambian nada y 3 recuperan un dato (`no_verificable` → `cumple`: HT-0903,
  HT-1008, HT-2106), pero esos avisos fallan otra restricción. Solo cambia su lista
  `failed_constraints`, que el juez no compara. Ningún bucle, por separado, cambia un veredicto.
  Post-hoc (30-oct) se corrió cada bucle por separado (`--sin releer`, `--sin consultar`):
  las dos dan las mismas cifras que el sistema completo (23/30, 5/30, 6/127, 20/113). Sin
  relectura las 30 respuestas son idénticas a las del sistema completo (603 llamadas en vez de
  614). Sin consulta cambian solo ht_09, ht_10 y ht_21, y solo en `failed_constraints`
  (533 llamadas).
- **−literal tiene más `full_correct` (7 vs 5) que el sistema completo.** `full_correct` es todo o
  nada por caso, y `comprobar` también rechaza correcciones buenas. Sin la validación se arreglan
  4 casos: «Perros sin límite de tamaño» (ht_04) y «Mascotas sin límite de peso» (ht_10) no cuentan
  como permiso explícito, la evidencia viene mal copiada como «UF 3.850.000» (ht_07), y un precio
  inverosímil rechazado deja el precio equivocado de `anclar` (ht_11). Se rompen 2 que estaban
  bien: «20 minutos caminando» y «15 minutos del metro en bus» se aceptan como 20 m y 15 m (ht_12,
  ht_30). En total, las aprobaciones indebidas pasan de 6 a 13 y `e1_strict` cae de 23 a 17. El
  criterio de la tarea castiga aprobar de más, así que la técnica se mantiene. Los 4 rechazos de
  más son el costo medido de ser estrictos.

## Reproducir

Lo que muestra el video (trazas versionadas, sin Ollama): sección
[«Reproducir lo que muestra el video de la E3»](../README.md#reproducir-lo-que-muestra-el-video-de-la-e3)
del README.

```bash
export PYTHONPATH=src
python3 -m agents.run --split hard_dev --run agents_v2_hard_dev          # iterar (solo dev)
python3 -m agents.show results/agents_v2_hard_dev/hd_01.trace.jsonl      # ver la conversación
bash scripts/run_e3.sh todo         # hard_test, real_e3, ablaciones, test, ood, hard_dev
bash scripts/run_e3.sh refinar       # −releer y −consultar por separado (post-hoc, 30-oct)
bash scripts/run_e3.sh tablas
python3 -m pytest tests/test_agents.py -q   # sin Ollama: herramientas, prompts y bucles
```
