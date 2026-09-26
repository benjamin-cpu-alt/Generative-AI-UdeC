"""Paso 1 del set REAL: muestra aleatoria de avisos reales de los portales, sin mirarlos.

El sesgo que se evita: si se eligen avisos después de leerlos, se eligen (aunque sea sin
querer) los que el sistema lee bien. Aquí el azar decide ANTES de abrir ningún aviso:

  1. Se descargan SOLO las páginas de resultados (no los avisos) de cada portal, para
     las comunas y tipos fijados abajo.
  2. Se descartan los proyectos con varias tipologías: su "desde UF X" no corresponde a
     una unidad concreta, así que no tienen una verdad anotable. Por eso PortalPM (solo
     proyectos) no aporta avisos.
  3. Con semilla fija, se sortean N avisos por portal.
  4. Solo entonces se abren esos avisos, se calcula la distancia a la estación más
     cercana y se escribe la ficha (el mismo texto que ven baseline y solución).

Salida: data/cases/real/fuente/muestra.json (instantánea versionada: el set no depende de que
los portales sigan publicando esos avisos). La anotación se hace a mano después
(scripts/build_real.py).

  python3 scripts/sample_real.py            # ~5 min: respeta las pausas de cada portal
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout import geo  # noqa: E402
from scout.collect import enrich_transit  # noqa: E402
from scout.ficha import render  # noqa: E402
from scout.fetch import FetchError, PoliteFetcher  # noqa: E402
from scout.sources import REGISTRY, SearchQuery, SourceError  # noqa: E402

SEED = 2026
PER_SOURCE = 4
COMUNAS = ["Providencia", "Ñuñoa", "Santiago", "La Florida"]
TIPOS = ["departamento", "casa"]
SOURCES = ["yapo", "chilepropiedades", "icasas", "toctoc"]   # portalpm: solo proyectos
OUT = ROOT / "data" / "cases" / "real" / "fuente" / "muestra.json"


def main() -> int:
    fetcher = PoliteFetcher(cache_dir=ROOT / "results" / "scout" / "cache", log=print)
    stations = geo.load_stations()
    rng = random.Random(SEED)
    sample = []
    for name in SOURCES:
        src = REGISTRY[name]()
        pool = []
        for comuna in COMUNAS:
            for tipo in TIPOS:
                q = SearchQuery(comuna, tipo, max_pages=1)
                for url in src.search_urls(q):
                    try:
                        pool += src.parse_search(fetcher.get(url), url, q)
                    except (FetchError, SourceError) as e:
                        print(f"[{name}] {tipo} {comuna}: {e}")
        units = sorted({l.key: l for l in pool if not l.is_project}.values(), key=lambda l: l.key)
        picked = rng.sample(units, min(PER_SOURCE, len(units)))
        print(f"[{name}] {len(pool)} avisos en resultados, {len(units)} unidades, sorteados {len(picked)}")
        for l in picked:
            if l.needs_detail:
                l = src.parse_detail(fetcher.get(l.url), l)
            enrich_transit(l, stations, ["metro", "tren"])
            sample.append({"source": l.source, "source_id": l.source_id, "url": l.url,
                           "comuna": l.comuna, "tipo": l.property_type, "title": l.title,
                           "ficha": render(l)})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "descargado": time.strftime("%Y-%m-%d"), "semilla": SEED, "por_portal": PER_SOURCE,
        "comunas": COMUNAS, "tipos": TIPOS, "portales": SOURCES,
        "nota": "Fichas generadas por src/scout/ficha.py a partir de avisos públicos; cada una "
                "conserva la URL de origen. Uso académico.",
        "avisos": sample}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(sample)} avisos -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
