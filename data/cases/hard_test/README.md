# Set HARD (E3) — protocolo, escrito antes que los casos

Este archivo se escribió y se versionó **antes** de redactar los avisos de `hard_dev/` y
`hard_test/`. Fija qué se mide, cuántos casos de cada fenómeno debe haber, las convenciones
de anotación y las reglas de uso. Los scripts verifican las cuotas y abortan si no se cumplen.

## Por qué existe

La E2 terminó en 51/51 (`e1_strict`) sobre `test/`. El comentario de la corrección fue si
convenía complejizar el benchmark, y el análisis da dos razones para hacerlo:

1. **Las plantillas.** `test/` sale de `generate.py`, así que la solución puede acertar
   por conocer las plantillas. OOD (12 casos escritos a mano) ya lo mostró: la medición
   ciega bajó a 9/12.
2. **El criterio se satura por sí solo.** `e1_strict` solo castiga *aprobar de más*: un
   sistema que **rechaza todo** obtiene 51/51 en test, 12/12 en OOD y 4/4 en real
   (`python -m matcher.reference`). El criterio de la E1 se mantiene por continuidad,
   pero desde la E3 se reporta **siempre junto a** `full_correct` y a métricas por
   propiedad (tasa de aprobación indebida y de rechazo falso), y con la fila de
   referencia "rechazar todo" como piso.

Por eso el set hard tiene **muchas aprobaciones esperadas** (40–55 % de las propiedades,
al menos 2 por caso): ahí, ser conservador cuesta puntos.

## Conjuntos y uso

| Carpeta | Casos | Prop./caso | Uso |
|---|---|---|---|
| `hard_dev/` | 10 | 7 | ajuste de agentes y prompts de la E3 |
| `hard_test/` | 30 | 8 | **evaluación principal de la E3**, solo para medir |

- Los dos sets cubren los mismos fenómenos con **redacciones distintas**: ningún
  fragmento de 8 palabras seguidas se repite entre dev y test (lo comprueba `build_hard.py`).
- `hard_test/` se congela con `MANIFEST.sha256` antes de la primera corrida del
  sistema de agentes. `tests/test_e3_benchmark.py` falla si un archivo cambia.
- **Ningún prompt, parser ni agente se ajusta mirando `hard_test`.** Si una corrida sobre
  test revela un fallo, se documenta como límite y no se corrige para esa misma cifra
  (la misma regla que la E2 aplicó a OOD).
- `ood/` pasa a ser **dev** en la E3: se usó para diagnosticar la E2 (g3 salió de sus
  fallos), así que ya no es una medición ciega.

## Fenómenos y cuotas mínimas (en número de propiedades)

Cada propiedad lleva `tags` con los fenómenos que la afectan. Una propiedad puede tener
varios. Las cuotas se cuentan sobre los fenómenos que **deciden el veredicto o el número
reportado**, no sobre adornos.

| Tag | Qué es | dev ≥ | test ≥ |
|---|---|---|---|
| `jerga_monto` | "620 lucas", "3 palos", "MM$", "180 millones", "600k" | 3 | 10 |
| `cifra_palabras` | números escritos con palabras (precio, distancia, kg, dormitorios) | 3 | 10 |
| `multi_monto` | gastos comunes, contribuciones, pie, precio anterior y bodega o estacionamiento con precio aparte | 3 | 12 |
| `arriendo_uf` | arriendo publicado en UF (el ROI exige convertirlo) | 2 | 6 |
| `dorm_notacion` | "3D+E", "2D 1B", "2+1", "suite + 1", "dos habitaciones" | 3 | 12 |
| `dorm_no_cuenta` | escritorio, servicio, estudio, "convertible", mansarda, loggia | 3 | 10 |
| `mascota_condicion` | especie o peso condicionado, negación invertida, excepciones | 4 | 14 |
| `mascota_silencio` | el aviso no habla de mascotas, o solo "consultar" / "según reglamento" | 2 | 8 |
| `estac_ambiguo` | opcional, se vende aparte, visitas, calle, derecho a uso | 4 | 12 |
| `dist_formato` | km, coma decimal, cuadras o minutos (no verificable), "a pasos" | 4 | 12 |
| `dist_multiple` | metro y paradero (u otra estación) en el mismo aviso: vale la menor | 2 | 8 |
| `comuna_posicion` | la comuna no sigue a "en": al final, entre paréntesis o en la dirección | 4 | 14 |
| `casi_cumple` | falla una sola restricción por un margen mínimo, o la cumple justo en el límite | 4 | 14 |
| `distractor` | datos de otra unidad, del vecino o del edificio, o afirmaciones de marketing | 3 | 10 |
| `correccion` | "rebajado de UF X a UF Y", "ACTUALIZACIÓN: ahora …": vale el dato final | 2 | 6 |
| `estilo` | WhatsApp, MAYÚSCULAS, erratas, ficha telegráfica | 4 | 12 |

Cuotas por caso:

- Al menos 2 propiedades aprobadas y 2 rechazadas por caso.
- En test, al menos 6 casos donde la preferencia de comuna contradice el ROI (el ranking importa).
- En test, al menos 4 casos con **comprador sin mascota** y 4 con **estacionamiento no
  requerido**. Ambas son opciones del perfil de la E1; el generador nunca las usó.
- La UF del día varía entre casos (entre 38.500 y 41.500).

## Convenciones de anotación (las mismas de `ood/` y `real/`)

- **Precio**: el de venta de la unidad. Si se corrige ("antes UF 4.500, ahora UF 4.150"),
  vale el último. Gastos comunes, contribuciones, pie y extras con precio aparte no son el
  precio. "Lucas" = miles de pesos; "palo" = millón de pesos.
- **Arriendo**: el arriendo mensual publicado de la unidad. Si viene en UF, la verdad es
  `round(UF × valor UF del caso)`. "Actualmente arrendado" sin monto = sin arriendo (ROI `null`).
- **Dormitorios**: solo los declarados como dormitorio, habitación o pieza (las suites
  cuentan). No cuentan escritorio, pieza o dormitorio de servicio, estudio, sala
  "convertible" o "habilitable", mansarda ni loggia. Monoambiente o estudio = 0 en `truth`,
  y **cuenta como 1** para el mínimo del comprador (convención E3, ver `REVIEW.md`).
- **Distancia**: la menor entre metro (o tren) y paradero troncal, en metros. km → m.
  Minutos, cuadras y "a pasos" no son una distancia verificable (`null` → la restricción falla).
- **Mascotas** (convención E3, ver `REVIEW.md`): si el aviso no declara política, o la deja
  abierta ("consultar", "a convenir", "según reglamento"), el aviso **no se descarta**: se
  aprueba si cumple lo demás y va al final del orden. En `truth` sigue anotándose como no
  explícita. Lo que sigue es la anotación de una política declarada. "Pet friendly", "se aceptan mascotas"
  y "una mascota por depto" = cualquier especie y peso. Las especies y el peso se anotan tal
  como se publican; el límite de peso es inclusivo (20 kg ≤ 20 kg cumple). "Consultar", "a
  convenir" o "según reglamento" sin más = no explícita. Se evita "mascotas pequeñas" sin
  número como dato decisivo, porque es ambiguo.
- **Estacionamiento**: solo `propio` o `asignado`. "Derecho a uso asignado" = asignado.
  Opcional, se arrienda o se vende aparte = `ninguno`. Visitas y calle no sirven.
- **Comuna**: la de la propiedad; tiene que aparecer escrita en el aviso.

## Auto-verificación

`scripts/build_hard.py` hace con la anotación lo mismo que `build_ood.py`: cada propiedad
declara `expect` (las restricciones que deben fallar) y el script aborta si `rules.py`
llega a otro veredicto. Además comprueba las cuotas de esta tabla, la comuna escrita, la
ausencia de solapamiento entre dev y test, y el manifiesto de test.

```bash
python3 scripts/build_hard.py --check   # verifica todo, no escribe
python3 scripts/build_hard.py           # escribe hard_dev/ y hard_test/ (test solo si no está congelado)
```

## Quién lo escribió

Los avisos y su anotación los redactó Claude (el asistente de código del equipo), siguiendo
este protocolo. `hard_test/` se congeló el 16-oct-2026, antes de que existiera código de
agentes. El equipo revisa la anotación y deja registro en `REVIEW.md`. Si la revisión
encuentra un error, se corrige en `scripts/hard_cases_test*.py`, se vuelve a congelar con
`--freeze` y se anota en `REVIEW.md` qué cambió y por qué. Esto solo se permite **antes**
de la primera corrida de cualquier sistema sobre `hard_test`; después, un error de
anotación se reporta, no se corrige.
