# Datos de entrenamiento del Lector (E4)

Pares **entrada → salida para el rol del Lector**: la entrada es el mensaje que el agente recibe
en el sistema (el `system` de `prompts/lector/v1.md` y el aviso), y la salida es el JSON con el
fragmento literal de cada tema y las tres respuestas cerradas de mascotas.

Todo sale de `scripts/ft/build_lector_data.py` con semilla fija. `--check` comprueba que estos
archivos son, byte a byte, los que genera el script.

| Archivo | Qué es |
|---|---|
| `train.jsonl` | 1.038 ejemplos en formato chat (`messages`: system, user, assistant) |
| `valid.jsonl` | 108 ejemplos sintéticos apartados al azar (10 %); solo para la curva de validación y la elección del checkpoint |
| `ejemplos.jsonl` | Los 1.146 ejemplos con su origen, estilo, fenómenos, `truth` y el estado de cada campo |
| `reporte.json` | Conteos, descartes y sha256 de los tres archivos anteriores |
| `revision_manual.csv` | Muestra aleatoria de 60 ejemplos para la revisión a mano del equipo |

## De dónde sale cada ejemplo y cómo se produjo su salida correcta

Ningún modelo más grande generó ni etiquetó datos.

**Fuente A, sintética con etiqueta por construcción (1.083 ejemplos).** Un compositor arma cada
aviso uniendo frases de bancos por tema (comuna, dormitorios, precio, arriendo, metro, paradero,
estacionamiento, mascotas) con relleno, distractores y seis estilos (portal, lista con comas,
MAYÚSCULAS, WhatsApp, una frase por línea y ficha «Campo: valor»; 12 % sin tildes). Cada frase
lleva marcado el fragmento que el Lector debe copiar. La salida correcta no la escribe nadie: es,
por construcción, una subcadena literal del aviso. Las respuestas cerradas de mascotas salen de
la política con la que se generó la frase, según las definiciones del prompt. Los fenómenos son
los 16 del protocolo de `hard_test` (`data/cases/hard_test/README.md`), que se escribió antes que
los casos: notación de dormitorios, ambientes que no cuentan, jerga de montos, cifras en
palabras, varios montos, correcciones de precio, arriendo en UF, estacionamiento ambiguo,
mascotas condicionadas o sin política, distancias en km o no verificables, dos distancias, comuna
fuera de «en», distractores de otra unidad y estilos.

**Fuente B, autoetiquetada por el modelo base y filtrada con el `truth` (63 ejemplos).** Avisos
del generador de la E2 (split `train`, que siempre fue de desarrollo) con la salida del propio
phi4-mini base, tomada de las trazas de `results/agents_v1_train20/`. De 140 salidas se aceptan
63: las que tienen todos los fragmentos literales, no necesitaron ningún respaldo de `anclar`,
no dejan dudas, leen los dormitorios desde el fragmento copiado, dan la política de mascotas
solo con las tres respuestas, y coinciden con el `truth` en los 7 campos. Sirven para que el
ajuste no desaprenda lo que el Lector ya hacía en avisos de plantilla (`test`).

**Formato de relectura (113 de los 1.146).** El mismo aviso con el mensaje que el Lector recibe
cuando el Verificador le devuelve campos: la salida trae solo esos campos.

## Comprobación automática de cada etiqueta

Cada ejemplo sintético pasa por las mismas herramientas que usa el sistema antes de entrar:

1. Cada fragmento es subcadena literal del aviso.
2. `anclar(fragmentos)` da el `truth` del campo (**directo**), o `dudas` marca el campo para el
   Verificador (**con duda**: «112 palos», «tres habitaciones», «Estac. propio», cifras en
   palabras). De 7.581 campos, 6.872 quedan directos y 709 con duda.
3. Un ejemplo cuyo fragmento correcto `anclar` lee **mal y en silencio** se descarta: 13 de 1.100,
   todos con la frase «No se aceptan perros, gatos sí» (la herramienta lo lee como prohibición
   total). El límite es de la herramienta y entrenar al Lector con él no lo arregla.

## Revisión a mano

`revision_manual.csv` es una muestra aleatoria (semilla del script) de **60 ejemplos**: 45
sintéticos y 15 autoetiquetados. Para cada uno se comprueba, leyendo el aviso, que cada fragmento
es el que corresponde al tema y que las tres respuestas de mascotas siguen la definición del
prompt. El resultado se anota en `revision_manual_respondida.csv` (columnas `correcto` y
`comentario`).

## Separación de la evaluación

- Los avisos sintéticos salen de bancos de frases propios. El script lee los avisos de
  `hard_test`, `hard_dev`, `real_e3`, `real`, `real_fallo`, `test` y `ood` **solo** para descartar
  cualquier ejemplo que comparta 8 palabras seguidas con alguno (el criterio que `build_hard.py`
  usa entre dev y test). Se descartaron 4, los cuatro por una frase en común con `hard_dev`.
  Con `hard_test`, `real_e3` y `test` no hubo ninguna coincidencia.
- Los autoetiquetados son avisos del split `train` del generador. `test` sale del mismo
  generador con otros valores y el script descarta cualquier texto repetido.
- `hard_dev` se usó para elegir el checkpoint y `hard_test` se corrió una sola vez después.
- `tests/test_e4.py` repite estas comprobaciones en cada corrida de los tests.

```bash
PYTHONPATH=src python3 scripts/ft/build_lector_data.py --check     # los archivos son los del script
PYTHONPATH=src python3 scripts/ft/build_lector_data.py --muestra 8 # ver ejemplos
python3 -m pytest tests/test_e4.py -q
```
