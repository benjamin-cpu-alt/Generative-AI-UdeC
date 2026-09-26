# Set REAL: avisos de portales, sorteados y anotados a mano

4 casos con 16 avisos reales, uno de cada portal por caso (Yapo, Chilepropiedades, iCasas,
TocToc), descargados el 26-sep-2026 con `src/scout`. Es el tercer conjunto de
evaluación, después de `test/` (sintético) y `ood/` (escrito a mano).

## Cómo se construyó, en orden

1. **Sorteo sin mirar** (`scripts/sample_real.py`). Se descargan solo las páginas de
   resultados de Providencia, Ñuñoa, Santiago y La Florida (departamentos y casas), se
   excluyen los proyectos con varias tipologías y se sortean 4 unidades por portal con la
   semilla 2026, de un universo de 2.198. Recién entonces se abren esos avisos. PortalPM
   no aporta: todos sus avisos son proyectos.
2. **Instantánea** (`fuente/muestra.json`). Guarda la ficha de cada aviso (el texto que
   ven baseline y solución, generado por `src/scout/ficha.py`) y la URL de origen. El
   set no depende de que los portales sigan publicando esos avisos.
3. **Anotación** (`scripts/build_real.py`). La verdad se lee de cada ficha con las mismas
   convenciones del set OOD, y cada decisión discutible queda en `note`. El script aborta
   si `rules.py` no llega al veredicto anotado.
4. **Comprador fijo**: el de la E1 (tope $150.000.000, perro de 18 kg, ≤ 1.000 m,
   2 dormitorios, estacionamiento). No se ajustó a los avisos.

## Qué mide y qué no

Con ese comprador **ningún aviso debe aprobarse**. Solo 3 de 16 declaran aceptar
mascotas, y los tres fallan en otra restricción: los avisos de venta casi nunca hablan
de mascotas. Por eso el set mide **aprobaciones indebidas y exactitud de lectura sobre
texto real**, no aciertos positivos. R08 es el caso límite: cumple todo salvo mascotas.

Las fichas incluyen una distancia a la estación más cercana **estimada** (línea recta a
la estación de OpenStreetMap × 1,3), porque casi ningún aviso la publica. La verdad
anota esa misma cifra: se evalúa la lectura del texto, no la exactitud de la estimación.

## Caso de fallo: `../real_fallo/fallo_001.json`

Aviso real (Chilepropiedades, Av. Providencia 1645) que **no** salió del sorteo: es el
que reveló la aprobación falsa del anclaje g3 ("Se aceptan ofertas" leído como "acepta
mascotas"; "opción de arriendo de estacionamientos" leído como estacionamiento propio).
Va en un split aparte para no mezclar un caso elegido con las cifras del sorteo.

**Anotación hecha por el asistente de código sobre las fichas. Pendiente de revisión
por el equipo.** Revisar en especial las notas marcadas CONFLICTO (R12, R14) y los
estudios (R04, R10).

```bash
python3 scripts/build_real.py --check      # verifica la anotación
cd src && python3 -m matcher.evaluate --runs baseline_phi4_real tools_phi4_v5_real_g3 --cases ../data/cases/real
```
