# Revisión humana de la anotación de hard_test

Los avisos de `hard_test/` los escribió Claude. Antes de la primera corrida sobre test, cada
integrante del equipo revisa **por separado** al menos 10 casos (80 avisos) y anota aquí
cada desacuerdo. El criterio de "correcto" es el de las convenciones del protocolo
(`README.md`), no la intuición de cada revisor. Si una convención parece mal, se discute
aparte: cambiarla afecta a todos los sets.

Para cada aviso, revisar que `truth` diga lo que dice el texto (precio y unidad, arriendo,
dormitorios, distancia, mascotas, estacionamiento, comuna) y que `expect` sea el veredicto
correcto. Ver un caso:

```bash
python3 scripts/review_hard.py ht_01            # texto, verdad en palabras y veredicto
python3 scripts/review_hard.py ht_01 ht_02 > revision.txt   # varios, a un archivo
```

| Revisor | Casos revisados | Fecha |
|---|---|---|
| Carla Maureira | ht_01–ht_10 (80 avisos): 76 correctos, 4 objeciones | 29-oct-2026 |
| Benjamín Grandón | ht_16–ht_25 (80 avisos): 76 correctos, 4 objeciones | 29-oct-2026 |

Hojas respondidas: `revision/revision_carla_respondida.csv` y
`revision/revision_benjamin_respondida.csv` (exportadas de Numbers). ht_11–ht_15 y
ht_26–ht_30 no se revisaron (el protocolo pide 10 casos por integrante).

**Ningún error de transcripción.** Las 8 objeciones son de convención y caen en dos reglas,
que el equipo discutió y cambió para todos los sets (convención E3):

1. **Estudio, loft o monoambiente = 1 dormitorio** (antes 0). La verdad sigue registrando 0
   (no hay dormitorio separado) y `rules.py` lo cuenta como 1 (`effective_bedrooms`).
2. **Mascotas sin política declarada no descarta.** Si el aviso no habla de mascotas, o lo
   deja abierto ("a convenir", "preguntar", "consultar condiciones"), se puede conversar: el
   aviso se aprueba si cumple lo demás, pero va **después** de las aprobadas que sí confirman
   mascotas (en el JSON de la E1 no hay campo para marcarlo, así que se expresa en el orden).
   Una prohibición, otra especie o un límite de peso menor siguen descartando.

## Desacuerdos

| Aviso | Revisor | Qué dice la anotación | Qué debería decir | Resolución |
|---|---|---|---|---|
| HT-0303 | Carla | loft de ambiente único = 0 dorm. → rechazada | 1 dormitorio | convención E3 (1): aprobada |
| HT-0308 | Carla | "a convenir" = no explícita → rechazada por mascotas | preguntar | convención E3 (2): aprobada, al final |
| HT-0605 | Carla | monoambiente = 0 dorm. → rechazada | 1 dormitorio | convención E3 (1); sigue rechazada (mínimo 2) |
| HT-1007 | Carla | no habla de mascotas → rechazada | convención: no hay info | convención E3 (2): aprobada, al final |
| HT-2006 | Benjamín | estudio = 0 < 1 → rechazada | estudio = 1D | convención E3 (1): aprobada |
| HT-2105 | Benjamín | "preguntar" → rechazada | no descarta, baja la relevancia | convención E3 (2): aprobada, al final |
| HT-2308 | Benjamín | "consultar condiciones" → rechazada | no descarta, baja la relevancia | convención E3 (2): aprobada, al final |
| HT-2508 | Benjamín | no habla de mascotas → rechazada | no descarta, baja la relevancia | convención E3 (2): aprobada, al final |

## Cambios hechos después de congelar

29-oct-2026, **antes de la primera corrida sobre hard_test**: aplicada la convención E3. Cambian
`expect` y la nota de 11 avisos de hard_test (HT-0303, 0308, 1007, 1206, 1408, 1908, 2006, 2105,
2308, 2508, 2806; todos pasan de rechazados a aprobados) y de 3 de hard_dev (HD-0107, 0502,
0802). HT-0303 y HT-2006 pasan del tag `dorm_no_cuenta` a `dorm_notacion`. Textos y `truth` no
cambian. Re-congelado con `build_hard.py --freeze`: 113/240 aprobadas (47 %), cuotas cumplidas.
