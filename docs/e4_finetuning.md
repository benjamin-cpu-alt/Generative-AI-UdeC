# E4 · Fine-tuning del Lector

La E4 ajusta los pesos del modelo de **un** agente del sistema de la E3, el **Lector (A1)**, con
un adaptador LoRA entrenado sobre el mismo phi4-mini. El Verificador y el Decisor siguen con el
modelo base. El resto del sistema (prompts, herramientas, orquestador, juez) no cambia.

- Adaptador publicado: <https://huggingface.co/USUARIO_HF/phi4-mini-lector-lora>
- Datos: [`data/ft_lector/`](../data/ft_lector/README.md) · Entrenamiento: [`scripts/ft/`](../scripts/ft) ·
  Registro: [`ft/lector/`](../ft/lector)
- Corridas: `bash scripts/run_e4.sh ...` · Tests: `tests/test_e4.py`

## 1. Continuidad: la misma tarea, el mismo fallo, el mismo sistema

La tarea es la de la E1: dado un perfil de comprador y avisos inmobiliarios en texto libre,
devolver un JSON estricto con los avisos aprobados (ordenados) y los rechazados. El fallo
diagnosticado en la E1 es que un modelo de 3.8B con prompt directo **lee mal el aviso** y además
calcula mal. La E2 separó leer de calcular (el modelo copia fragmentos, el código calcula) y la
E3 puso tres agentes sobre esa base. Lo que queda del fallo de la E1 es la lectura: la E4 va a
la primera lectura, la del Lector.

Se usan las mismas entradas y el mismo juez que en la E3 (`matcher.evaluate`,
`matcher.metrics`): `hard_test` (30 casos, 240 avisos, congelado) como evaluación principal,
`real_e3` (avisos reales), `test` (regresión) y `ood`; `hard_dev` para elegir.

## 2. Cómo se llaman los agentes entre sí, y en qué se diferencian de las herramientas

El comentario a la E3 fue que no quedaba claro cómo corre el bucle entre agentes ni la diferencia
con las herramientas. Esta sección lo responde, y `python3 -m agents.show <traza> --roles` lo
muestra sobre cualquier traza.

| | Agente | Herramienta |
|---|---|---|
| Qué es | Una llamada al modelo (phi4-mini) con su propio prompt versionado | Una función de Python en `src/agents/tools.py` |
| Cuáles | Lector, Verificador, Decisor | `anclar`, `comprobar`, `evaluar`, `ordenar` |
| Qué produce | Una **decisión**, escrita como JSON con un `enum` de acciones: a quién le pasa el trabajo | Un cálculo o una validación: la misma salida para la misma entrada |
| Usa modelo | Sí | No |
| Decide el siguiente paso | Sí | No: devuelve su resultado al agente que la usó o al siguiente agente del camino |
| Puede equivocarse distinto cada vez | Sí (por eso se registra cada mensaje) | No (por eso tiene tests) |

El **orquestador** (`Sistema.run_case` en `src/agents/orchestrator.py`) no es un agente ni decide
nada. Es un bucle de Python que lee la acción que escribió el agente, entrega el mensaje a su
destino y cuenta las vueltas. Hay tres bucles, y los tres los abre un agente:

```
por cada aviso:
    spans  = LECTOR(aviso)                      # agente
    hechos = anclar(spans)                      # herramienta: fragmentos -> datos, y marca dudas
    si no hay dudas: el aviso pasa al Decisor
    revisiones = VERIFICADOR(aviso, hechos, dudas)          # agente: una acción por campo dudoso
    repetir:
        por cada revisión `corregir`: ok, motivo = comprobar(valor, evidencia, aviso)   # herramienta
        si comprobar rechazó algo y quedan reintentos (máx. 1):       ← BUCLE DE REINTENTO
            revisiones = VERIFICADOR(aviso, hechos, rechazos)         #   herramienta -> agente
        si el Verificador pidió `releer` y quedan relecturas (máx. 2): ← BUCLE DE RELECTURA
            spans = LECTOR(aviso, campos devueltos)                   #   agente -> agente
            hechos = anclar(spans);  revisiones = VERIFICADOR(...)
        si no: salir

estados = evaluar(hechos, comprador)            # herramienta: 5 restricciones por aviso
repetir:
    decisión = DECISOR(comprador, avisos, estados)          # agente: `cerrar` o `consultar`
    si `cerrar`, o no quedan rondas (máx. 1): salir          ← CONDICIÓN DE PARADA
    por cada consulta (id, campo):                           ← BUCLE DE CONSULTA
        VERIFICADOR revisa ese campo de ese aviso            #   agente -> agente
    estados = evaluar(hechos, comprador)
JSON final = ordenar(estados)                   # herramienta
```

- **Bucle de relectura (agente → agente).** El Verificador escribe `releer` para un campo. El
  orquestador vuelve a llamar al Lector solo con esos campos, `anclar` vuelve a leer y el
  Verificador revisa de nuevo. Máximo 2 vueltas por aviso; después el dato queda en `null`.
- **Bucle de reintento (herramienta → agente).** `comprobar` rechaza una corrección y devuelve
  el motivo. El Verificador decide de nuevo: corregir otra vez, mantener o declarar el dato no
  verificable. Máximo 1 vuelta.
- **Bucle de consulta (agente → agente).** El Decisor, al ver el resultado de `evaluar`, escribe
  `consultar(id, campo)`. El Verificador revisa ese campo y el Decisor decide otra vez con el
  resultado nuevo. Máximo 1 ronda.
- **Parada.** El sistema termina cuando el Decisor escribe `cerrar` o cuando se agota el
  presupuesto de un bucle (el orquestador lo deja escrito en la traza: `sin_relectura`,
  `sin_reintento`, `cierre_por_presupuesto`).

En la traza cada mensaje lleva `de` y `para`. Un mensaje `de: Verificador, para: Lector` es una
vuelta del bucle de relectura; `de: herramienta:comprobar, para: Verificador` es la respuesta de
una herramienta. Con `--roles` la vista lo dice en palabras:

```
    ↺ BUCLE DE RELECTURA, vuelta 1 de máx. 2: el Verificador (agente) decide `releer` y el aviso vuelve al Lector (agente)
 13 AGENTE Verificador → AGENTE Lector  [revisar]  HD-0904
      arriendo: CORREGIR  valor='70000'  evidencia='Arriendo 700 lucas'
      estacionamiento: RELEER  valor='propio'
 14 HERRAMIENTA comprobar → AGENTE Verificador  [resultado]  HD-0904
      arriendo = '70000' desde 'Arriendo 700 lucas' -> ACEPTA — la evidencia dice 700000 (el agente escribió '70000')
 15 AGENTE Lector → HERRAMIENTA anclar  [relectura]  HD-0904
```

En la corrida de la E3 sobre `hard_test` (1.440 mensajes) hubo 245 llamadas al Lector, 315 al
Verificador y 54 al Decisor; 7 vueltas de relectura, 93 de reintento y 24 rondas de consulta (41
consultas).

## 3. Qué agente se ajusta y por qué con pesos y no con más prompt

**La evidencia sale de las trazas de la E3.** `scripts/atribucion_e3.py` vuelve a ejecutar el
orquestador con las salidas grabadas en cada traza (sin llamar al modelo) y, para cada campo de
cada aviso, compara con el `truth` lo que se leyó en la primera pasada y lo que llegó a
`evaluar`. Así cada error queda atribuido a quien lo produjo: el **Lector** (el fragmento que
copió no trae el dato, o lo dejó en `null`), la herramienta **`anclar`** (el fragmento sí lo
trae y el código lo lee mal) o el **Verificador** (el dato estaba bien y lo rompió).

Corrida de la E3 sobre `hard_test` (`results/agents_v2_hard_test/`, 240 avisos, 1.680 campos):

| | Campos |
|---|---|
| Mal leídos en la primera pasada | 218 |
| — nacen en el **Lector** | **162** (74 %) |
| — nacen en `anclar` (código) | 56 |
| Del Lector: fragmento en `null` con el dato en el aviso | 132 de 162 |
| Del Lector, por campo | dormitorios 117, estacionamiento 20, precio 16, comuna 9 |
| El Verificador rompe un dato que venía bien | 15 |
| Llegan mal a `evaluar` | 75 (40 con origen en el Lector, 20 en `anclar`, 15 rotos por el Verificador) |
| Avisos mal juzgados (de 240) | 26: en 16 el dato decisivo nace en el Lector, en 6 en `anclar`, en 4 lo rompe el Verificador |

```bash
PYTHONPATH=src python3 scripts/atribucion_e3.py agents_v2_hard_test            # la tabla
PYTHONPATH=src python3 scripts/atribucion_e3.py agents_v2_hard_test --detalle  # cada campo, con su aviso
```

Lectura: el sistema de la E3 funciona porque el Verificador arregla 122 de los 162 errores del
Lector, y cada arreglo cuesta llamadas (315 al Verificador, 93 reintentos) y abre la puerta a
los 15 datos que el Verificador rompe. El Lector es el agente que origina más errores y el
único cuya salida pasa por todos los demás.

**Por qué no el Verificador ni el Decisor.** El Decisor no lee avisos: decide sobre los estados
de `evaluar`, y en la E3 quitar su bucle de consulta no cambió ningún veredicto. El Verificador
ya trabaja sobre un insumo dañado: mejorar la primera lectura le quita trabajo y errores sin
tocarlo. Los 56 errores de `anclar` son de código, no de un modelo.

**Por qué con pesos y no con más prompt.** Tres razones medidas:

1. *El fallo es de conducta, no de instrucción.* El prompt del Lector ya dice «copia el fragmento
   del aviso que habla de los dormitorios». En 117 avisos el modelo deja `null` frente a «3D»,
   «2 hab.», «3D+E» o «dos piezas». No le falta una regla: no reconoce esas formas como el tema
   pedido. Eso se enseña con ejemplos de la conducta, y los ejemplos que hacen falta no caben en
   un prompt de 2.048 tokens de contexto.
2. *Iterar el prompt del Lector ya se intentó y empeoró.* En la E2 el extractor (el mismo prompt
   que hoy usa el Lector) pasó por cuatro versiones sobre dev: **21/30 → 13/30 → 8/30 → 8/30**
   (`docs/e2_pipeline.md`, «Iteración del prompt del extractor»). Cada versión arreglaba el campo
   que se le pedía y rompía otro cuya línea no había cambiado. En un modelo de 3.8B las
   instrucciones del prompt no se componen.
3. *El control lo mide directamente.* El control de la E4 es el mismo sistema con el Lector base
   y **8 ejemplos few-shot tomados de los mismos datos de entrenamiento**
   (`prompts/lector/v2_fewshot.md`, generado por `scripts/ft/build_fewshot_prompt.py`): el
   máximo de esa información que cabe en el prompt. Si el control iguala al ajuste, los pesos no
   aportaron nada. La comparación está en la sección 6.

**Lo que el ajuste no puede arreglar** (y se sabía antes de entrenar): los errores de `anclar`
(«perros OK», la vía pública leída como estacionamiento propio) y los datos que rompe el
Verificador. Si el Lector mejora, esos pasan a ser el techo del sistema.

## 4. Datos de entrenamiento

Detalle completo en [`data/ft_lector/README.md`](../data/ft_lector/README.md). Resumen:

| | |
|---|---|
| Qué son | Pares entrada → salida para el rol del Lector: el mismo `system` y el mismo mensaje que recibe en el sistema (`mensaje_lector` en `orchestrator.py` es la única función que lo arma, para el sistema y para los datos), y el JSON que debe escribir |
| Tamaño | **1.146** ejemplos: 1.038 de entrenamiento y 108 de validación |
| Fuente A (1.083) | Sintéticos, de `scripts/ft/build_lector_data.py` (semilla fija). La salida correcta es correcta **por construcción**: cada frase del banco lleva marcado el fragmento que el Lector debe copiar |
| Fuente B (63) | Salidas del propio phi4-mini base sobre avisos de `train` (trazas de `results/agents_v1_train20/`), aceptadas solo si coinciden con el `truth` en los 7 campos sin ayuda de las herramientas (63 de 140) |
| Modelo más grande | Ninguno generó ni etiquetó datos |
| Comprobación automática | Cada ejemplo pasa por `anclar` y `dudas`: 6.872 campos se leen directo, 709 quedan marcados para el Verificador, y los 13 ejemplos que la herramienta leía mal en silencio se descartaron |
| Revisión a mano | Muestra aleatoria de 60 (45 + 15) en `revision_manual.csv`; resultado en `revision_manual_respondida.csv` |
| Formato de relectura | 113 ejemplos con el mensaje que el Lector recibe cuando el Verificador le devuelve campos |

**Separación de la evaluación.** Los bancos de frases se escribieron para la E4 a partir de los
16 fenómenos del protocolo de `hard_test` (`data/cases/hard_test/README.md`, escrito antes que
los casos), no a partir de los avisos. El script lee los avisos de `hard_test`, `hard_dev`,
`real_e3`, `real`, `real_fallo`, `test` y `ood` solo para descartar cualquier ejemplo que
comparta 8 palabras seguidas con alguno: descartó 4, los cuatro contra `hard_dev`; contra
`hard_test`, `real_e3` y `test` no hubo coincidencias. `tests/test_e4.py` repite la comprobación.
`hard_dev` se usó para elegir; `hard_test` se corrió una sola vez con el adaptador ya elegido.

*Límite declarado:* la elección del agente (sección 3) usó las trazas de la E3 sobre `hard_test`,
como pide la pauta, así que quien escribió el generador conocía qué fenómenos fallaban ahí. Los
textos no se copiaron y la separación léxica está comprobada, pero `hard_test` ya no es un set
ciego para el equipo. Por eso se reportan también `real_e3` (avisos de portales) y `ood`.

## 5. Entrenamiento

| | |
|---|---|
| Método | LoRA (adaptador de bajo rango), con `mlx-lm` 0.29.1 sobre MLX 0.29.3 |
| Modelo base | Phi-4-mini-instruct, el mismo del sistema. Para entrenar: `mlx-community/Phi-4-mini-instruct-8bit` (revisión `93b273a5`). Para correr: `phi4-mini:latest` de Ollama (digest `78fad5d182a7`, Q4_K_M) con el adaptador encima |
| Módulos adaptados | `qkv_proj`, `o_proj`, `gate_up_proj` y `down_proj` de las últimas 16 de 32 capas (64 matrices) |
| Rango / escala / dropout | 16 / 2,0 (alpha 32) / 0,05 |
| Parámetros entrenables | 11,5 M (0,30 % de 3.836 M) |
| Pérdida | Entropía cruzada solo sobre la respuesta (`mask_prompt`) |
| Optimizador | AdamW, weight decay 0,01 |
| Tasa de aprendizaje | 1,5e-4, warmup de 20 pasos y coseno hasta 1,5e-5 |
| Lote | 1 ejemplo con acumulación de gradiente de 4 (lote efectivo 4) |
| Iteraciones | 1.300 ejemplos vistos = 325 pasos de optimizador = 1,25 épocas |
| Largo máximo | 1.280 tokens (el ejemplo más largo tiene 977) |
| Semilla | 0 |
| Hardware | MacBook Air M4, 16 GB de memoria unificada, macOS 26.6 |
| Tiempo | **202,5 min** (incluye 6 validaciones completas de ~6 min cada una) |
| Memoria pico | 6,7 GB |
| Tokens entrenados | 166.223 (solo respuesta) |

La configuración está en [`scripts/ft/lector_lora.yaml`](../scripts/ft/lector_lora.yaml) y el
registro de la corrida en [`ft/lector/`](../ft/lector): `train.log` (salida completa),
`loss.csv` (la curva), `entrenamiento.json` (hardware, versiones, duración, sha256 de los datos).

**Curvas de pérdida** (`ft/lector/loss.csv`; validación completa, 108 ejemplos, cada 260 iteraciones):

| Iteración | 1 | 260 | 520 | 780 | 1.040 | 1.300 |
|---|---|---|---|---|---|---|
| Pérdida de validación | 0,690 | 0,028 | 0,017 | 0,010 | 0,007 | **0,006** |
| Pérdida de entrenamiento (media de 20 it.) | — | 0,071 | 0,012 | 0,011 | 0,010 | 0,004 |

La validación baja en cada medición y no se separa de la de entrenamiento: no hay señal de
sobreajuste dentro de la distribución sintética. Se usa el último checkpoint (iteración 1.300),
el de menor pérdida de validación. Con lote 4 real el Mac paginaba a disco (11 GB de proceso);
lote 1 con acumulación da el mismo gradiente con 6,7 GB.

**De MLX a Ollama.** `scripts/ft/export_gguf.py` convierte el adaptador a GGUF (formato de
adaptador LoRA de llama.cpp, float16, 23 MB) y `ft/lector/Modelfile` lo monta sobre el modelo
base de Ollama (`FROM phi4-mini:latest` + `ADAPTER`). Los pesos base no se tocan: el Verificador
y el Decisor siguen llamando a `phi4-mini:latest`, y el Lector llama a `phi4-mini-lector-ft`.
`ft/lector/SHA256SUMS` fija los archivos con los que se obtuvieron los resultados, y
`scripts/ft/subir_hf.py` se niega a publicar otros.

*Límite declarado:* el adaptador se entrenó sobre los pesos en 8 bits y se usa sobre los de 4
bits (Q4_K_M) de Ollama, que son los del sistema de la E3. Todos los resultados de la sección 6
se midieron en esa configuración final (Ollama, 4 bits, con esquema JSON).

## 6. Resultados

Mismas entradas, mismo juez (`matcher.evaluate` + `matcher.metrics`) y mismas corridas de la E3
para los sistemas anteriores. Entre E3, E4 y el control lo único que cambia es el Lector: el
modelo (E4) o el prompt (control). `tests/test_e4.py` comprueba en cada `meta.json` que el
Verificador y el Decisor usaron `phi4-mini:latest` con los prompts de la E3.

**Elección en `hard_dev`** (10 casos, 70 avisos; se usó para elegir, así que no prueba nada por
sí solo):

| Sistema | e1_strict | full_correct | exactitud por aviso | aprob. indebida | rechazo falso |
|---|---|---|---|---|---|
| E3 (agentes, Lector base) | 10/10 | 8/10 | 69/70 | 0/36 | 1/34 |
| **E4 (Lector con LoRA)** | **10/10** | **10/10** | **70/70** | **0/36** | **0/34** |
| Control (Lector base + 8 few-shot) | 9/10 | 7/10 | 70/70 | 0/36 | 0/34 |

`hard_dev` está casi saturado. Se eligió el último checkpoint (menor pérdida de validación) y
`hard_test` se corrió **una sola vez** después (`bash scripts/run_e4.sh hard_test`, 13-nov).

**Evaluación principal: `hard_test`** (30 casos, 240 avisos, congelado; IC de Wilson al 95 %):

| Sistema | e1_strict | full_correct | exact_match | exactitud por aviso | aprob. indebida | rechazo falso |
|---|---|---|---|---|---|---|
| Rechazar todo (piso) | 30/30 | 0/30 | 0/30 | 127/240 | 0/127 | 113/113 |
| E1 · baseline (prompt directo) | 1/30 | 0/30 | 0/30 | 118/240 | 38/127 | 84/113 |
| E2 · extractor + herramientas | 11/30 | 1/30 | 3/30 | 193/240 | 0/127 | 47/113 |
| E3 · agentes (Lector base) | **23/30** | 5/30 [7–34] | 10/30 | 214/240 [85–92] | **6/127** | 20/113 [12–26] |
| **E4 · agentes, Lector con LoRA** | 22/30 | **16/30 [36–70]** | **18/30** | **225/240 [90–96]** | 8/127 [3–12] | **7/113 [3–12]** |
| Control · Lector base + 8 few-shot | **23/30** | 11/30 [22–54] | 15/30 | 221/240 [88–95] | 7/127 | 12/113 [6–18] |

Comparación pareada por caso (`full_correct`, McNemar exacto):

| | Solo el primero acierta | Solo el segundo acierta | p |
|---|---|---|---|
| E4 vs E3 | 11 | 0 | 0,001 |
| E4 vs control | 5 | 0 | 0,06 |
| Control vs E3 | 6 | 0 | 0,03 |

**Qué cambia dentro del sistema** (desde las trazas: `scripts/atribucion_e3.py` y
`scripts/resumen_e4.py`, sin llamar al modelo):

| `hard_test` | E3 | E4 | Control |
|---|---|---|---|
| Errores de primera lectura que nacen en el Lector | 162 | **22** | 26 |
| Errores de primera lectura que nacen en `anclar` | 56 | 49 | 55 |
| Campos que llegan mal a `evaluar` | 75 | **39** | 47 |
| Datos buenos que el Verificador rompe | 15 | 13 | 16 |
| Avisos sin dudas (no pasan por el Verificador) | 64 | **167** | 156 |
| Llamadas: Lector / Verificador / Decisor | 245 / 315 / 54 | 246 / **134** / 45 | 245 / 151 / 45 |
| Vueltas: relectura / reintento / consulta (rondas) | 7 / 93 / 24 | 8 / **36** / 15 | 7 / 42 / 15 |
| Tokens de entrada (todo el sistema) | 577 k | **368 k** | 731 k |
| Minutos (M4) | 65,6 | **42,6** | no comparable* |

\*Durante la corrida del control el Mac se suspendió dos veces (casos `ht_13` y `ht_19`). Sin
esos dos casos, el control promedia ~210 s por caso, contra ~85 s de E4 y ~130 s de E3: el
prompt few-shot duplica la entrada del Lector y obliga a Ollama a usar 4.096 tokens de contexto.

**Lectura.**

1. *El ajuste hace lo que se buscaba.* Los errores que nacen en el Lector bajan de 162 a 22, y
   el resto del sistema lo nota: el Verificador recibe menos de la mitad de trabajo (315 → 134
   llamadas), los reintentos bajan de 93 a 36 y la corrida tarda un tercio menos. Las respuestas
   exactas suben de 5/30 a 16/30 y los rechazos falsos bajan de 20 a 7. En los 11 casos donde E4
   y E3 difieren en `full_correct`, acierta E4.
2. *El control recupera la mayor parte de la mejora del Lector.* Con 8 ejemplos en el prompt,
   los errores del Lector bajan a 26. La pregunta de la pauta (¿qué consiguen los pesos que el
   prompt no?) tiene una respuesta más chica que la comparación con la E3: **5 casos exactos
   más (16 vs 11, ninguno en contra, p = 0,06), 5 rechazos falsos menos, con la mitad de tokens
   de entrada y sin ampliar el contexto.** Con 30 casos los intervalos se solapan; la ventaja es
   consistente (5 a 0) pero no concluyente.
3. *Lo que no mejora.* `e1_strict` baja un caso (23 → 22) y las aprobaciones indebidas suben de
   6 a 8. Las seis de la E3 siguen ahí; las dos nuevas son de estacionamiento (sección 7). Los
   errores de `anclar` (49) y los datos que rompe el Verificador (13) quedan casi iguales: eran
   el techo esperado y ahora son la mayor parte de lo que falla. Por fenómeno, las ganancias están
   en mascotas sin política (5 → 10 de 10, también en el control), notación de dormitorios
   (14 → 16 de 19) y jerga de montos (11 → 13 de 14); la pérdida, en estacionamiento ambiguo
   (19 → 17 de 24).

### Regresión: avisos reales, `test` y `ood`

`hard_test` es el set donde la E3 fallaba. En los otros tres la E3 ya estaba cerca del techo, así
que aquí la pregunta es otra: ¿el ajuste rompe algo que funcionaba? (`full_correct` · avisos bien
juzgados · aprobaciones indebidas · rechazos falsos.)

| Set | E1 | E2 | E3 | **E4** | Control | Piso |
|---|---|---|---|---|---|---|
| `real_e3` (20 casos, 80 avisos reales) | 0 · 59 · 17/75 · 4/5 | 18 · 78 · 0/75 · 2/5 | **20** · **80** · **0/75** · 0/5 | 19 · 79 · 1/75 · 0/5 | 19 · 79 · 1/75 · 0/5 | 15 · 75 · 0/75 · 5/5 |
| `ood` (12 casos, 70 avisos) | 0 · 40 · 16/49 · 14/21 | 7 · 67 · 0/49 · 3/21 | 10 · 68 · 0/49 · 2/21 | **11** · **69** · 0/49 · **1/21** | 10 · **69** · 0/49 · **1/21** | 0 · 49 · 0/49 · 21/21 |
| `test` (51 casos, 352 avisos) | 0 · 199 · 61/227 · 92/125 | 47 · 351 · 0/227 · 1/125 | 50 · 351 · 0/227 · 1/125 | **51** · **352** · 0/227 · **0/125** | **51** · **352** · 0/227 · **0/125** | 3 · 227 · 0/227 · 125/125 |

| Llamadas al Verificador | E3 | E4 | Control |
|---|---|---|---|
| `real_e3` | 89 | 77 | 81 |
| `ood` | 72 | **36** | 50 |
| `test` | 26 | 27 | 27 |

- **`test` y `ood` no empeoran:** E4 queda en 51/51 y 11/12, un caso mejor que la E3 en cada uno, y
  en `ood` el Verificador recibe la mitad de las llamadas. Las diferencias son de un caso: sirven
  para decir que no hay regresión, no para decir que hay mejora.
- **En los avisos reales hay una regresión de un aviso** (20/20 → 19/20): `REAL-38` del caso
  `real_b1_008` se aprueba indebidamente, tanto en E4 como en el control. El Lector no es quien se
  equivoca; el detalle está en la sección 7.
- Los minutos de estas corridas no se reportan: el Mac corrió a batería y se suspendió varias
  veces (`agents_ctrl_real_e3` y `agents_ft_test`). Los conteos de llamadas y de tokens no dependen
  de eso.

## 7. Caso de fallo: HT-0906, una aprobación indebida que la E3 no tenía

Traza: [`results/agents_ft_hard_test/ht_09.trace.jsonl`](../results/agents_ft_hard_test/ht_09.trace.jsonl),
pasos 28–30. La misma entrada en la E3: `results/agents_v2_hard_test/ht_09.trace.jsonl`, pasos 30–35.

> «Macul, 2D. UF 2.900. A 300 m del metro. Gatos sí. **Estacionamiento: no; hay estacionamiento
> en calle.**»  El comprador exige estacionamiento.

| | E3 (Lector base) | E4 (Lector con LoRA) |
|---|---|---|
| Fragmento de dormitorios | `null` (no reconoce «2D») | «2D» ✔ |
| Fragmento de estacionamiento | «no; hay estacionamiento en calle.» | «Estacionamiento: no» |
| `anclar` lee | dormitorios ?, estacionamiento **calle** | dormitorios 2, estacionamiento **propio**, sin duda |
| Camino | `anclar` marca dormitorios → Verificador corrige a 2 con evidencia «2D.» → `comprobar` acepta | ningún campo con duda → directo al Decisor |
| Veredicto | rechazado (correcto: estacionamiento en la calle) | **aprobado indebidamente** |

```bash
python3 -m agents.show results/agents_ft_hard_test/ht_09.trace.jsonl --aviso HT-0906 --roles
python3 -m agents.show results/agents_v2_hard_test/ht_09.trace.jsonl --aviso HT-0906 --roles
```

**Mecanismo.** El Lector ajustado arregla dormitorios (el fallo para el que se entrenó), pero
corta el fragmento de estacionamiento en el punto y coma. «Estacionamiento: no» es una copia
literal y razonable; el problema es que la herramienta `anclar` lee «Estacionamiento: no» como
estacionamiento **propio** y no marca duda (con el fragmento completo lee «calle»). Como el aviso
ya no tiene ningún campo dudoso, no pasa por el Verificador y nadie lo revisa. En la E3 el mismo
aviso llegaba al Verificador por culpa de los dormitorios, y el error de estacionamiento nunca
aparecía.

La otra aprobación indebida nueva (HT-0107, «Estacionamiento: se puede arrendar uno en el
edificio por $45.000») tiene la misma forma: el Lector ajustado copia la etiqueta
«Estacionamiento:» y `anclar` la lee como propio. En los datos de entrenamiento hay 107
fragmentos que empiezan con «Estacionamiento:», todos con el valor completo («no tiene»,
«propio», «solo visitas»); ninguno con un «no» seguido de una aclaración.

**Qué enseña.** Es el mismo patrón que el caso de fallo de la E3 (HT-2708): arreglar un campo
destapa los errores silenciosos de otro. Con un Lector mejor, 103 avisos más se saltan al
Verificador (64 → 167), y los errores que `anclar` comete sin marcar duda ya no tienen quién los
vea. La corrección no está en el Lector sino en la herramienta (que «Estacionamiento: no» cuente
como negación o al menos como duda) y en los datos (fragmentos de estacionamiento con aclaración).
No se corrigió nada: `hard_test` se corre una sola vez.

### Segundo caso, sobre un aviso real: REAL-38 (`real_b1_008`)

Trazas: [`results/agents_ft_real_e3/real_b1_008.trace.jsonl`](../results/agents_ft_real_e3/real_b1_008.trace.jsonl)
(pasos 18–22) y la misma entrada en la E3, `results/agents_v2_real_e3/real_b1_008.trace.jsonl`
(pasos 19–26).

> «Departamento en Santiago. 2D/2B. Precio: UF 2.490. Distancia estimada a la **estación** de
> metro Toesca: 200 m. […]»  El aviso no dice nada de estacionamiento y el comprador lo exige.

| | E3 (Lector base) | E4 (Lector con LoRA) |
|---|---|---|
| Comuna que lee `anclar` | «venta» (el Lector copió la frase larga) | «Santiago» ✔ |
| Campos con duda | comuna y estacionamiento | solo estacionamiento |
| Verificador (base en los dos) | propone «200 m de Toesca» y luego «propio» con una frase que no habla del tema | propone «propio» con evidencia «…**estación** de metro Toesca: 200 m» |
| `comprobar` | rechaza las dos | **acepta** |
| Veredicto | rechazado (correcto) | **aprobado indebidamente** |

```bash
python3 -m agents.show results/agents_ft_real_e3/real_b1_008.trace.jsonl --aviso REAL-38 --roles
python3 -m agents.show results/agents_v2_real_e3/real_b1_008.trace.jsonl --aviso REAL-38 --roles
```

**Mecanismo.** Aquí el Lector ajustado lee *mejor* que el base y el sistema responde *peor*. Hay
dos defectos que ya estaban en la E3 y que el azar tapaba:

1. La herramienta decide si un texto «habla de estacionamiento» con la expresión `estac`, que
   también calza con «**estac**ión de metro». Por eso `dudas` manda al Verificador un aviso que no
   menciona estacionamiento, y por eso `comprobar` acepta como evidencia la frase del metro.
2. El Verificador (modelo base, sin ajustar) inventa «propio» en vez de responder que el dato no
   está.

En la E3 el Verificador recibía dos campos dudosos y su propuesta para estacionamiento venía con
una evidencia que `comprobar` rechazaba. Al arreglar la comuna, el mensaje que recibe el Verificador
cambia (un solo campo), su respuesta cambia, y esta vez cita la frase que pasa el filtro. El control
few-shot cae en lo mismo, paso por paso, así que no es un efecto de los pesos sino de cambiar la
entrada de un agente que no se tocó.

**Qué enseña.** Ajustar un agente cambia lo que ven los demás, y la evaluación tiene que ser del
sistema completo: a nivel del Lector este aviso es una mejora. El arreglo es de una línea en la
herramienta (`estacionam` en vez de `estac`); no se aplicó porque cambiaría el sistema de la E3
después de ver los resultados de un set de evaluación.

## 8. Reproducir

Ver la sección E4 del [README](../README.md#entregable-4-fine-tuning-del-lector). En corto:

```bash
python3 -m pytest tests -q                                       # sin Ollama ni red
bash scripts/run_e4.sh tablas                                    # todas las tablas desde results/ (sin modelo)
python3 -m agents.show results/agents_ft_hard_test/ht_09.trace.jsonl --aviso HT-0906 --roles   # caso de fallo
# con el adaptador publicado (ver README): base y ajustado sobre el mismo aviso
python3 -m agents.comparar --split hard_test --caso ht_09 --aviso HT-0906
bash scripts/run_e4.sh datos && bash scripts/run_e4.sh entrenar  # regenerar datos y reentrenar (~3,5 h en un M4)
```
