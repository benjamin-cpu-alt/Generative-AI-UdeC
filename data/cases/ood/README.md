# Set OOD — avisos escritos a mano

12 casos, 70 propiedades, 19 aprobadas (27 %). **Nada de esto sale de `generate.py`.**

## Para qué

`data/cases/test/` se genera con plantillas: un parser determinista puede acertar ahí
memorizando la plantilla en vez de leer el aviso. Este set existe para poder distinguir
las dos cosas. La solución de la E2 mueve la interpretación al código (`grounding.py`),
así que la pregunta legítima es *"¿queda algo que el LLM aporte, o esto es un regex?"*.
La respuesta se mide aquí: si el rendimiento se sostiene sobre avisos que ninguna
plantilla produjo, la percepción del modelo es real; si se derrumba, lo que había era
ajuste al generador. Los dos resultados se reportan.

Se usa **solo para evaluar**. Ninguna versión del prompt se ajustó mirando estos casos, y
las capas de anclaje g1 y g2 tampoco: la cifra de g2 (9/12) es la medición ciega. **g3 sí**:
sus cinco correcciones salieron de mirar los fallos de g2 aquí, así que su 11/12 no es una
medición de generalización (ver `docs/e2_pipeline.md`, *Capa de anclaje*). Las mejoras que
añadirían aprobaciones (`3D+E`, `2D 1B`, comuna al final) se dejaron fuera a propósito.

## Cómo se construyó

`scripts/build_ood.py` contiene los avisos redactados a mano junto a su `truth` y la lista
`expect` de restricciones que deben fallar. Al generar los JSON, el script comprueba que
`rules.py` llegue exactamente al mismo veredicto que la anotación manual y aborta si no
coincide — la misma auto-verificación que usa el generador sintético, aplicada a anotación
humana. En la primera pasada detectó tres errores de aritmética en la anotación (precios en
UF que, convertidos, caían al otro lado del presupuesto).

```bash
python3 scripts/build_ood.py --check    # verifica la anotación
python3 scripts/build_ood.py            # reescribe los JSON
```

Cada propiedad lleva un campo `note` que dice qué dificultad concreta introduce. El código
lo ignora; está para que una persona pueda revisar la anotación.

## Qué estresa cada caso

| Caso | Estilo |
|---|---|
| `ood_001` | Ficha de portal: prosa formal, "metros" y "kilos" escritos completos |
| `ood_002` | WhatsApp de corredor: minúsculas, sin tildes, `620 lucas`, `118 millones` |
| `ood_003` | Cifras en palabras ("ciento cuarenta y cinco millones") y `$158 millones` |
| `ood_004` | Distancias solo en minutos, "a pasos", "15 minutos en micro" |
| `ood_005` | Tipologías chilenas: `2D+servicio`, `3D+E` |
| `ood_006` | Gastos comunes compitiendo con el precio de venta |
| `ood_007` | Mascotas con fraseos poco habituales y negación invertida |
| `ood_008` | MAYÚSCULAS, erratas (`Estacionamento`), `Dpto`, `mts` |
| `ood_009` | Estacionamiento ambiguo: "opcional, se arrienda aparte", "derecho a uso" |
| `ood_010` | UF "aproximado", con decimal (`UF 4.250,5`) y en rango |
| `ood_011` | Avisos telegráficos: `2D 1B. 55m2. UF 3.300. Metro a 350m. Est. propio.` |
| `ood_012` | Avisos largos saturados de marketing (trampa de atención selectiva) |

Además hay **near misses** deliberados, donde el veredicto depende de hacer bien la
conversión UF→CLP y no de leer bien el texto:

| Propiedad | Precio | En CLP | Tope | Sobre el tope por |
|---|---|---|---|---|
| `OOD-1006` | UF 4.640 | $180.032.000 | $180.000.000 | **$32.000** |
| `OOD-506` | UF 4.490 | $175.110.000 | $175.000.000 | $110.000 |
| `OOD-404` | UF 4.900 | $190.610.000 | $190.000.000 | $610.000 |

Y un caso límite en el otro sentido: `OOD-702` acepta perros "hasta veinte kilos" y el
comprador tiene uno de 20 kg exactos — debe aprobarse (20 ≤ 20).

## Convenciones de anotación

Decisiones que un lector podría discutir, tomadas de forma explícita y uniforme:

- **`2D+servicio` = 2 dormitorios.** La pieza de servicio no es dormitorio, igual que el
  escritorio o la loggia "convertible" del criterio de la E1. Lo mismo con `3D+E`.
- **Distancia no publicada ⇒ la restricción falla.** Un aviso que solo dice "a 12 minutos
  caminando" no permite verificar la cercanía al transporte. Se representa con
  `truth.distance_transport_m = null`, y `rules.py` lo trata como incumplimiento, igual que
  una política de mascotas no explícita. Es una extensión declarada del criterio de la E1:
  los 351 casos sintéticos siempre traen un entero, y se verificó que su ground truth no
  cambia ni en un caso.
- **Estacionamiento "opcional, se arrienda aparte" = no incluido** (`ninguno`). La unidad
  que se vende no trae estacionamiento.
- **Precio en rango** (`OOD-1003`): se anota el extremo inferior, y el rango se eligió de
  modo que ambos extremos superen el presupuesto — el veredicto no depende de qué extremo
  tome el sistema.
- Una especie nombrada en positivo restringe a esa especie: "Acepta gatos hasta 4 kilos"
  significa que un perro no entra.
