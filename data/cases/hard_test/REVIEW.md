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
| Carla Maureira | | |
| Benjamín Grandón | | |

## Desacuerdos

| Aviso | Revisor | Qué dice la anotación | Qué debería decir | Resolución |
|---|---|---|---|---|
| | | | | |

## Cambios hechos después de congelar

Ninguno.
