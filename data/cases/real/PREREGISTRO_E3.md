# Preregistro E3: segundo sorteo de avisos reales y comprador 2

Escrito y versionado el **16-oct-2026, antes de descargar ningún aviso nuevo**. Fija el
comprador, el sorteo, la anotación y el uso del set. Nada de esto se ajusta después de ver
los avisos o los resultados.

## Por qué

El set real de la E2 (`real/`, 16 avisos) tiene **0 aprobaciones esperadas**: con el
comprador de la E1 (perro de 18 kg), casi ningún aviso de venta habla de mascotas. Por eso
rechazar todo obtiene 4/4 incluso en `full_correct`, y el set solo mide aprobaciones
indebidas. Además, su anotación la hizo Claude y la revisión del equipo quedó pendiente
(R04, R10, R12, R14).

## Comprador 2

Comprador sin mascota y sin auto, definido sin mirar los avisos:

| Restricción | Valor |
|---|---|
| Presupuesto máximo | $180.000.000 |
| Mascota | no tiene (`mascota_especie: null`): cualquier política sirve |
| Distancia máxima a metro/tren o paradero troncal | 1.200 m |
| Dormitorios mínimos | 2 |
| Estacionamiento | no requerido |
| Comunas preferidas (ranking) | Ñuñoa, Santiago |

El comprador 1 sigue siendo el de la E1, sin cambios.

## Sorteo 2

El mismo procedimiento de `scripts/sample_real.py`, con estos cambios:

- **Semilla 2027** y **6 avisos por portal** (24 en total).
- Mismos portales (Yapo, Chilepropiedades, iCasas, TocToc), comunas (Providencia, Ñuñoa,
  Santiago, La Florida) y tipos (departamento, casa).
- Se excluyen los 16 avisos del sorteo 1 (por `portal:id`).
- La UF del día de la descarga se toma de mindicador.cl y queda en la instantánea.
- Salida: `fuente/muestra_2.json`, versionada; no se vuelve a sortear.

## Casos

- Sorteo 1: los 4 casos de `real/` (uno de cada portal por caso). Sorteo 2: 6 casos armados igual.
- Cada uno de los 10 casos se evalúa con **los dos compradores**, lo que da 20 casos y
  80 evaluaciones de aviso en `data/cases/real_e3/`. `real/` queda intacto por continuidad.

## Anotación (humana, doble y ciega)

1. `scripts/real_annotation.py sheets` genera una hoja en blanco por anotador
   (`anotacion/hoja_carla.csv`, `anotacion/hoja_benjamin.csv`) con los **40 avisos**,
   incluidos los 16 del sorteo 1. Así se cierra su revisión pendiente.
2. Cada integrante anota **sin mirar la hoja del otro ni `scripts/build_real.py`**,
   siguiendo las convenciones de `data/cases/hard_test/README.md` y de `build_real.py`.
3. `scripts/real_annotation.py agreement` calcula el acuerdo y el kappa de Cohen por campo,
   y lista los desacuerdos.
4. Los desacuerdos se resuelven en conjunto. La decisión y su motivo van a
   `anotacion/adjudicada.csv`; el kappa **antes** de resolver se reporta.
5. `scripts/real_annotation.py build` escribe `real_e3/` desde la hoja adjudicada y
   aborta si `rules.py` no coincide con el veredicto anotado.

## Uso

Solo para evaluar. Ningún prompt, parser ni agente se ajusta mirando `real_e3/`.
