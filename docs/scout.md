# scout — búsqueda en portales + análisis con la solución de la E2

`src/scout/` le pregunta al comprador qué necesita, busca avisos reales en cinco portales
chilenos y pasa cada uno por el analizador de la E2 (phi4-mini, extractor v5, anclaje, decisión
en Python). Es una extensión posterior a la E2: **no cambia ninguna cifra reportada**. El
analizador se usa tal cual, y la única adición a `matcher/` es la versión g4 del anclaje
(ver *Integración*).

```bash
pip install -r requirements.txt           # agrega beautifulsoup4
cd src
python3 -m scout                                        # cuestionario interactivo
python3 -m scout --perfil ../data/scout/perfil_ejemplo.json
python3 -m scout --perfil ../data/scout/perfil_ejemplo.json --solo-scraping   # sin LLM
python3 -m scout --perfil p.json --fuentes toctoc,yapo --max-por-fuente 10
```

Salida en `results/scout/<fecha-hora>/` (no se versiona):
- `reporte.md`: aprobadas y por revisar, con enlace a cada aviso.
- `resultados.json`: por cada aviso, la ficha, los fragmentos que copió el modelo, los
  hechos anclados y cada comparación de la decisión.
- `salida_e1.json`: el JSON estricto de la E1 (`approved_matches` / `rejected`).

## Arquitectura

```
profile.py ──► collect.py ─────────────────────────────► analyze.py ──► report.py
cuestionario   │ sources/<portal>.py  URL + parseo           │ ficha.py   aviso -> texto compacto
(o JSON)       │ fetch.py             descarga educada        │ matcher.extract_facts (v5, g4)
               │ geo.py               distancia al metro      │ matcher.constraints.decide
               │ prefilter.py         descarte con datos      │ clasificación: aprobada /
               │                      del portal              │ revisar / rechazada
```

Cada capa solo depende de las de abajo. Agregar un portal = una subclase de
`sources.base.Source` (URL de búsqueda + `parse_search` + `parse_detail` opcional) y una
línea en `sources/__init__.py`.

## Cuestionario

Se preguntan exactamente los datos pedidos, y lo ambiguo se repregunta en vez de suponerse:

| Dato | Aclaración que se pide |
|---|---|
| Presupuesto máximo | si falta la unidad ("4500"): ¿UF o CLP? |
| ¿Mascota? + tamaño | pequeña (≤10 kg) / mediana (≤25 kg) / grande (>25 kg) |
| Distancia máxima a transporte + tipo | "cerca" no se puede filtrar: se piden metros o km; tipo: metro, tren, bus |
| Dormitorios reales mínimos | entero |
| ¿Estacionamiento? | sí / no |
| Comunas | nombres de la RM; si hay una mal escrita se sugiere la parecida ("providensia" → Providencia) |

Traducción a las restricciones del analizador, ambas **conservadoras**:
- El tamaño se convierte al **tope** de su rango (mediana = 25 kg). Un aviso que acepta
  "hasta 20 kg" no sirve para una mediana.
- La especie no se pregunta. Un aviso que la restringe ("solo gatos") no se aprueba, porque no
  se puede confirmar que la mascota del comprador califique.

## Portales: cómo se consulta cada uno

Estructura verificada el 26-sep-2026 con peticiones reales. Los supuestos sobre el DOM están
en el docstring de cada adaptador. Todas las rutas usadas están permitidas por el robots.txt
de su sitio.

| Portal | URL de búsqueda (comuna → slug) | De dónde salen los datos | ¿Abre cada aviso? | Coordenadas |
|---|---|---|---|---|
| TocToc | `/venta/{departamento\|casa}/metropolitana/{comuna}` | JSON `__NEXT_DATA__` (Next.js) | no: trae la descripción completa | sí |
| PortalPM | **API REST oficial** `/wp-json/wp/v2/properties?property_city=ID` | JSON de WordPress/Houzez | no | sí |
| Chilepropiedades | `/propiedades/venta/{tipo}/{comuna}/{página}` | JSON-LD `ItemList` y `RealEstateListing` | sí | sí (script del mapa) |
| Yapo | `/bienes-raices-venta-de-propiedades-{apartamentos\|casas}/region-metropolitana-{comuna}?page=N` | tarjetas + JSON-LD `Product` | sí | sí (iframe del mapa) |
| iCasas | `/venta/{tipo}s/{provincia}/{comuna-sin-artículo}/list[/p_N]` | microdatos `itemprop` | sí (descripción cortada) | sí |

En orden de preferencia: API oficial, luego los datos estructurados que el sitio publica para
los buscadores (JSON-LD, microdatos, el JSON de Next.js), y selectores CSS solo como último
recurso y acotados al bloque principal del aviso. Los datos estructurados cambian mucho menos
que las clases CSS, porque de ellos depende el SEO del portal.

Tres trampas encontradas en la verificación:
- **Yapo escribe "UF 9,950" con coma de miles**, al revés del formato chileno; `normalize.py` lo
  leería como 9,95 UF. El precio se toma del JSON-LD (`9950`, `CLF`) y se reescribe como "UF 9.950".
- **Chilepropiedades muestra avisos "comparables" con otros precios** en la misma página. Solo se
  lee `article.clp-publication-detail-main`, sin ese bloque, para que el extractor no copie el
  precio de otra propiedad.
- **iCasas omite el artículo en la URL** (`Las Condes` → `santiago/condes`), y
  `/venta/departamentos/region-metropolitana/...` responde 410.

## De los filtros a la búsqueda

| Filtro | ¿En la URL? | Cómo se aplica |
|---|---|---|
| Comuna | sí, en la ruta de los 5 portales | `comunas.py` |
| Tipo (depto/casa) | sí | ídem |
| Presupuesto | no (los parámetros de precio no están documentados y varían) | prefiltro con el precio estructurado del portal; después, `decide` con el precio anclado |
| Dormitorios | no | prefiltro con el dato del portal; después, dormitorios **reales** leídos del texto |
| Distancia al metro/tren | ningún portal lo ofrece | **calculada** (abajo); prefiltro y luego `decide` |
| Mascotas | ningún portal lo ofrece | solo del texto del aviso (LLM + parser) |
| Estacionamiento | no | dato estructurado si existe ("Incluye 1 estacionamiento") + texto |

**"Cerca del metro" → número.** Cuatro portales publican las coordenadas del inmueble. La
distancia es la línea recta a la estación más cercana × 1,3, un factor de rodeo urbano típico
(la literatura reporta 1,2–1,4) elegido del lado conservador. Las estaciones están en
`data/scout/estaciones_rm.json`: 126 de metro y 17 de tren (Alameda–Nos y Rancagua), tomadas
de OpenStreetMap (ODbL). Solo cuentan las estaciones **en servicio**: se excluyen las
proyectadas (tren a Melipilla, con inicio en 2027 y 2029), las de carga sin pasajeros (línea
al norte: Colina, Batuco) y los ascensores de Valparaíso. Los paraderos de bus no se calculan:
OSM no distingue un troncal de uno cualquiera, así que para bus solo vale una distancia que
declare el propio aviso. El archivo se regenera con `python3 scripts/build_estaciones_rm.py`
(una consulta a Overpass), no en cada búsqueda.

## Anti-bloqueo: la política

- **User-Agent honesto** que nombra al bot y enlaza al repositorio. Usa la convención de los
  bots conocidos (`Mozilla/5.0 (compatible; UdeC-GenAI-scout/0.1; ...; +url)`) y va en ASCII:
  una tilde en el UA provocó 403 en TocToc. **No se rotan user-agents ni se simula un
  navegador humano.** Eso es evadir la detección, y si un sitio decide no atender bots hay que
  respetarlo.
- **robots.txt** se obedece, incluido `Crawl-delay` (Chilepropiedades pide 2 s).
- **Pausa** de 3 s por dominio más un jitter aleatorio de 0 a 2 s. Reintentos con backoff ante
  429 y 5xx, respetando `Retry-After`.
- **Bloqueo** = 401/403, 429 persistente o una página de desafío (Cloudflare, DataDome,
  PerimeterX, CAPTCHA). Ese portal se omite por el resto de la ejecución y el reporte dice cuál
  falló y por qué. Nunca se intenta resolver un CAPTCHA.
- **Caché** en disco con TTL de 6 h: repetir la búsqueda no vuelve a golpear al sitio.
- No hace falta un navegador (Playwright o Selenium): los cinco portales entregan los datos en
  el HTML o en su API.

## Integración con el analizador de la E2

Cada aviso se reescribe como una **ficha** (`ficha.py`), un aviso de texto compacto en el
formato que el extractor aprendió a leer:

```
Departamento en Ñuñoa, Lo Encalada. 2D/1B, 57 m². Precio: $85.000.000.
Distancia estimada a la estación de metro Ñuble: 831 m. Estac.: 1. [descripción compactada]
```

Motivos para no pasarle la página completa:
- Los datos estructurados entran en formato chileno.
- La distancia calculada queda escrita en el texto, así que el anclaje de g3/g4 (todo número
  debe existir en el texto) sigue valiendo.
- Se quitan los montos que compiten con el precio (gastos comunes, dividendos, la "renta
  recomendada" que exigen al comprador) y los datos de contacto.

La ficha pasa por `matcher.extract.extract_facts` (v5) y `matcher.constraints.decide`, las
mismas funciones que se evaluaron en test y OOD. `analyze.py` agrega tres cosas que no existen
en el criterio de la E1:
1. Sin mascota, la restricción de mascotas no aplica.
2. **Aprobada / revisar / rechazada.** "No admite mascotas" y "el aviso no lo dice" se
   separan. Ambos siguen sin aprobarse, como exige el criterio, pero el segundo se muestra
   aparte con el dato que falta.
3. Un **proyecto** nuevo con varias tipologías nunca se aprueba solo: su precio "desde" no
   corresponde a una tipología concreta.

**Anclaje g4.** La primera corrida con avisos reales produjo una aprobación falsa por dos
defectos de g3 que los datos sintéticos no tenían cómo mostrar:
- "Se aceptan ofertas. Se acepta canje con corredores." se leyó como "acepta mascotas".
- "La administración cuenta con opción de arriendo de estacionamientos" se leyó como
  estacionamiento propio.

g4 corrige ambos. Es una versión nueva, no un cambio de g3: re-decidiendo todas las corridas
versionadas (test M4 y RTX, dev, OOD y el set real), g4 da salidas **idénticas** a g3, así que
las cifras de la E2 no cambian. El aviso quedó como caso de fallo reproducible en
`data/cases/real_fallo/`.

**Set real.** `scripts/sample_real.py` sortea avisos con `scout` (semilla fija, antes de
leerlos) y `scripts/build_real.py` los anota: son `data/cases/real/`, el tercer conjunto de
evaluación de la E2 (resultados en el README). `scout` usa g4 (`tests/test_grounding_g4.py`).

## Límites conocidos

- **Muchos avisos quedan en "revisar" por mascotas.** Los avisos de venta casi nunca hablan de
  mascotas. Es el precio de no aprobar lo que no se puede verificar.
- **Mascotas: se hereda la convención de la E1.** El caso original de la E1, anotado a mano,
  trata "ideal para mascotas grandes" como permiso explícito. Por eso un aviso real que ofrece
  "un espacio al aire libre para tus mascotas" se aprueba (Yapo 32827971, en la corrida de
  prueba). Se probó exigir un verbo de permiso ("acepta", "permite") y se descartó: cambiaba
  veredictos en test y contradecía esa anotación. Antes de comprar hay que confirmar el
  reglamento de copropiedad.
- **Dormitorios.** El parser toma el primer "N dormitorio(s)" de la cláusula. En "1 dormitorio
  de buen tamaño + 1 dormitorio pequeño ideal para escritorio" cuenta 1, aunque el portal diga
  3. Rechaza de más, nunca aprueba de más.
- **La distancia es una estimación.** Una recta × 1,3 no es la ruta real a pie. Para un filtro
  cerca del borde (700 m calculados contra 750 m pedidos), conviene verificarla en el mapa.
- **Solo la Región Metropolitana.** Las rutas de los portales se verificaron en detalle para
  Providencia, Ñuñoa y Las Condes. Si un portal responde 404/410 para otra comuna, esa
  combinación se registra y se omite.
- **Los términos de uso de cada portal** pueden restringir la extracción automatizada aunque su
  robots.txt la permita. El módulo es para uso académico y personal, con volumen bajo (topes
  por portal, caché, pausas). No se debe usar para republicar avisos.
- Los portales cambian. Si cambia un formato, el adaptador lanza `SourceError`, ese portal
  figura como fallido en el reporte y los demás siguen funcionando.
