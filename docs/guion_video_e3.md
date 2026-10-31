# Guion del video E3 (≤ 3:00, una sola toma)

La pauta pide grabar el sistema **corriendo sobre avisos reales**, con los mensajes entre agentes
y la salida final a la vista, **sin cortes ni edición**. Por eso todo sale en una sola toma y con
la voz en directo.

La espera de la corrida en vivo es parte del video. Con `--vivo`, `agents.run` imprime cada
mensaje entre agentes en el momento en que se produce, así que mientras Phi-4-mini trabaja la
pantalla va mostrando la conversación. Las otras tres escenas salen de las trazas de la corrida
final (`results/agents_v2_*`) y aparecen al instante.

`docs/demo_video.sh` corre todo. Cada Enter pasa a la escena siguiente, y antes de cada una el
script escribe en pantalla el comando exacto que va a correr: no hay que tipear nada durante la
toma.

Verificado el 31-oct en la M4: la corrida en vivo de `real_b2_004` produce los mismos 31 mensajes y
el mismo JSON final que `results/agents_v2_real_e3/real_b2_004.trace.jsonl`. Lo único distinto es
la configuración del paso 1, que ahora lista los flags `releer` y `consultar`, agregados después.
**Enchufado tarda ~70 s; a batería, ~220 s**, más que el video entero.

## Antes de grabar (no sale en el video)

1. **Enchufa el Mac.** Activa *No molestar* y cierra lo que no uses.
2. Abre el PDF del informe en una ventana, con zoom al grafo.
3. Abre una terminal a pantalla completa, con fondo oscuro, fuente de 16 pt y
   **al menos 120 columnas**. Desde la raíz del repositorio:

   ```bash
   bash docs/demo_video.sh
   ```

   El script revisa que el Mac esté enchufado y deja el modelo cargado en memoria (~10 s). Cuando
   aparece "Listo. Empieza a grabar…", **no aprietes nada todavía**.
4. Deja el PDF al frente. Ten el texto de la voz en el celular o en otra pantalla.
5. Graba con **Cmd+Shift+5 → Grabar toda la pantalla**. En *Opciones*, elige el **micrófono**
   (si no, el video queda sin voz). Para terminar: el botón ■ de la barra de menú, o
   Cmd+Ctrl+Esc.
6. Ensaya la toma completa al menos una vez, con cronómetro.
7. Sube el video a YouTube como *No listado* (o a Drive con "Cualquier persona con el enlace") y
   prueba el link en una ventana de incógnito.

Si algo sale mal durante la toma: Ctrl+C, vuelve a correr `bash docs/demo_video.sh` y graba de
nuevo desde el principio. `--force` sobrescribe `results/demo_video/`.

## La toma

Cmd+Tab cambia entre el PDF y la terminal. En la terminal, **Enter** pasa a la escena siguiente;
**s + Enter** se la salta (es para la escena 4 si van atrasados: la `s` no se ve en pantalla).

| Tiempo | Escena | Pantalla | Al terminar |
|---|---|---|---|
| 0:00–0:20 | 1 · El sistema | PDF, grafo | Cmd+Tab y Enter |
| 0:20–1:35 | 2 · Corrida en vivo | terminal (~70 s) | Enter cuando sale `[1/1] real_b2_004…` |
| 1:35–1:55 | 3 · REAL-23 | terminal | Enter |
| 1:55–2:10 | 4 · REAL-08, convención | terminal | Enter (o `s` + Enter si pasaron 2:00) |
| 2:10–2:35 | 5 · Caso de fallo | terminal | Cmd+Tab al PDF |
| 2:35–2:55 | 6 · Resultados | PDF, tabla | detener la grabación |

### 1 · 0:00–0:20 · El sistema

**Pantalla:** PDF, zoom al grafo. Al nombrar cada agente, pasa el cursor por su caja azul; al
decir "bucles", por las flechas rojas discontinuas.

> Somos Benjamín Grandón y Carla Maureira. Reconstruimos la solución de la E2 con tres agentes
> —Lector, Verificador y Decisor— sobre el mismo modelo, Phi-4-mini. En verde están las
> herramientas en Python; en rojo, los bucles, cada uno con su límite y su condición de parada.

**Cmd+Tab a la terminal y Enter.**

### 2 · 0:20–1:35 · Corrida en vivo

**Comando** (lo escribe el script):

```bash
python3 -m agents.run --split real_e3 --only real_b2_004 --run demo_video --force --vivo
```

Los mensajes salen a ráfagas, una por cada respuesta del modelo (unos 5 s cada una). Cada bloque
de voz va **con lo que aparece en pantalla, no con el reloj**. Si el modelo va más rápido que la
voz, sigue hablando; si va más lento, espera en silencio.

| Cuando aparece | Voz |
|---|---|
| (al apretar Enter) | > Lo corremos en vivo sobre un caso real: un comprador y cuatro avisos de portales chilenos, anotados por nosotros dos. Cada mensaje aparece apenas el modelo responde. |
| pasos 2–3, `Lector → anclar` | > El Lector copia del aviso, literal, el fragmento de cada tema, y la herramienta anclar lo convierte en datos. |
| pasos 4–14, REAL-04, `RELEER` | > En REAL-04 la distancia dice «3 cuadras de la salida del Metro»: no hay un número. El Verificador pide releer dos veces y el orquestador corta el bucle. El dato queda no verificable, y un dato no verificable nunca aprueba. |
| pasos 15–17, REAL-08, `[sin_dudas]` | > REAL-08 no tiene dudas: pasa directo al Decisor. |
| pasos 18–23, REAL-12, `RECHAZA` | > En REAL-12 el Verificador cita una frase que no está textual en el aviso, y comprobar la rechaza dos veces. |
| pasos 24–27, REAL-16, `ACEPTA` | > En REAL-16 escribe tres dormitorios citando «dos dormitorios», y comprobar se queda con lo que dice el texto. |
| pasos 28–31, `json_final` | > Evaluar entrega el estado de cada restricción, el Decisor cierra y ordenar escribe el JSON final: aprueba REAL-08 y rechaza los otros tres, cada uno con su motivo. |
| línea `[1/1] real_b2_004: 14 llamadas, 31 mensajes…` | > Catorce llamadas al modelo y treinta y un mensajes, todos guardados en la traza. |

**Enter.**

### 3 · 1:35–1:55 · El aviso que la E2 rechazaba

```bash
python3 -m agents.show results/agents_v2_real_e3/real_b2_005.trace.jsonl --aviso REAL-23 --pasos 12-14,28
```

Señala con el cursor: paso 12 `precio=NO SE PUDO LEER` → paso 13 `evidencia='Precio: UF 2.490.'`
→ paso 14 `ACEPTA` → paso 28 `REAL-23: APRUEBA`.

> Esto es de la corrida final. A REAL-23 la E2 lo rechazaba por presupuesto, porque no leía el
> precio. Anclar tampoco lo lee, pero el Verificador lo encuentra —«Precio: UF 2.490»—, comprobar
> confirma que la cita está en el aviso, y el aviso se aprueba.

**Enter** (o **s + Enter** si el reloj ya pasó 2:00).

### 4 · 1:55–2:10 · Convención E3: sin política de mascotas

```bash
python3 -m agents.show results/agents_v2_real_e3/real_b1_004.trace.jsonl --aviso REAL-08 --pasos 28-31,35
```

Señala: paso 28 `APRUEBA (mascotas sin confirmar: al final del orden)` → paso 29 `CONSULTAR` →
paso 30 `NO_VERIFICABLE … 'no declara política'` → paso 35 `json_final`.

> Otro comprador, con perro. REAL-08 no dice nada de mascotas: el Decisor consulta, el
> Verificador confirma que no declara política y, por la convención que acordamos, no se
> descarta: se aprueba y va al final del orden.

**Enter.**

### 5 · 2:10–2:35 · Caso de fallo

```bash
python3 -m agents.show results/agents_v2_hard_test/ht_27.trace.jsonl --aviso HT-2708 --pasos 30-31,36-37
```

Señala: paso 30 `parking_text: 'Estacionamiento en la vía pública…'` → paso 31
`estacionamiento=propio` → paso 36 `HT-2708: APRUEBA` → paso 37, la consulta descartada
`HT-2708 … Estacionamiento en vía pública`.

> Y un caso de fallo, de hard_test. El aviso dice «estacionamiento en la vía pública», pero anclar
> lo leyó como propio y no marcó duda. El Decisor se dio cuenta y quiso consultarlo, pero solo
> puede consultar datos no verificables o sin confirmar, así que el aviso se aprueba indebidamente.
> Cinco de las seis aprobaciones indebidas son de este tipo.

**Cmd+Tab al PDF.**

### 6 · 2:35–2:55 · Resultados

**Pantalla:** PDF, zoom a la tabla de resultados. Señala la fila "Agentes (full)", luego "E2" y
"Baseline", luego "−herramientas_A3" y "−literal". Termina con el link del repositorio a la vista
(encabezado del PDF).

> Con las mismas entradas y el mismo juez, en los treinta casos de hard_test los agentes aciertan
> veintitrés en el criterio de la E1, contra once de la E2 y uno del prompt directo, y bajan los
> rechazos falsos de 42 a 18 por ciento. Sin herramientas, el Decisor acierta cero; sin evidencia
> literal, se duplican las aprobaciones indebidas. Todo se reproduce desde el README.

**Detén la grabación.**

## Comandos exactos (lo que corre `docs/demo_video.sh`)

```bash
export PYTHONPATH=src
ollama run phi4-mini:latest "hola"     # antes de grabar: deja el modelo cargado
python3 -m agents.run --split real_e3 --only real_b2_004 --run demo_video --force --vivo
python3 -m agents.show results/agents_v2_real_e3/real_b2_005.trace.jsonl --aviso REAL-23 --pasos 12-14,28
python3 -m agents.show results/agents_v2_real_e3/real_b1_004.trace.jsonl --aviso REAL-08 --pasos 28-31,35
python3 -m agents.show results/agents_v2_hard_test/ht_27.trace.jsonl --aviso HT-2708 --pasos 30-31,36-37
```

`results/demo_video/` no hace falta commitearla: tiene los mismos mensajes que la traza versionada.
