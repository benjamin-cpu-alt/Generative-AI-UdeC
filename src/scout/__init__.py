"""scout: busca propiedades en portales inmobiliarios chilenos y las pasa por el
analizador de la E2 (`matcher`: extractor v5 + anclaje g3 + decisión determinista).

Capas, cada una en su módulo y sin dependencias hacia arriba:

  profile.py    recolección de las necesidades del comprador (cuestionario o JSON)
  fetch.py      descarga educada: robots.txt, pausas por dominio, reintentos, caché,
                detección de bloqueos (nunca los evade: registra y sigue)
  sources/      un adaptador por portal: URL de búsqueda + parseo -> `Listing`
  geo.py        distancia a la estación de metro/tren más cercana (OpenStreetMap)
  prefilter.py  descarte barato con datos estructurados del portal, antes del LLM
  ficha.py      `Listing` -> texto de aviso compacto, el formato que lee el extractor
  analyze.py    ficha -> matcher.extract_facts -> matcher.decide -> clasificación
  report.py     salida en terminal, JSON (esquema de la E1) y Markdown
  cli.py        orquestador: `python -m scout`

`matcher/` solo se extiende con la versión g4 del anclaje (aditiva: g3 sigue siendo la
por defecto y la reportada en la E2, y g4 da salidas idénticas en test, dev y OOD).
"""
