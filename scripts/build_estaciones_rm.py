"""Regenera data/scout/estaciones_rm.json con las estaciones de metro y tren de la RM
desde OpenStreetMap (una sola consulta a la API de Overpass).

  python3 scripts/build_estaciones_rm.py

Se corre a mano cuando cambia la red (p.ej. una línea nueva de metro), no en cada
búsqueda. Datos © colaboradores de OpenStreetMap, licencia ODbL 1.0.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.geo import STATIONS_FILE, overpass_url, parse_overpass  # noqa: E402

# Overpass rechaza (406) los User-Agent que empiezan con "Mozilla/5.0": se identifica como bot puro.
UA = "UdeC-GenAI-scout/0.1 (proyecto academico; +https://github.com/benjamin-cpu-alt/Generative-AI-UdeC)"


def main(out: Path) -> int | str:
    req = urllib.request.Request(overpass_url(), headers={"User-Agent": UA, "Accept": "*/*"})
    for attempt in range(4):   # Overpass responde 429/504 cuando está cargado
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                stations = parse_overpass(json.loads(r.read().decode("utf-8")))
            break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 502, 503, 504) or attempt == 3:
                raise
            print(f"Overpass HTTP {e.code}; reintento en {30 * (attempt + 1)} s")
            time.sleep(30 * (attempt + 1))
    if len(stations) < 100:
        return f"solo {len(stations)} estaciones: la respuesta parece incompleta, no se escribe"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "fuente": "OpenStreetMap vía Overpass API",
        "licencia": "ODbL 1.0 — © colaboradores de OpenStreetMap (https://www.openstreetmap.org/copyright)",
        "generado": time.strftime("%Y-%m-%d"),
        "estaciones": [s.__dict__ for s in sorted(stations, key=lambda s: (s.kind, s.name))],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(stations)} estaciones -> {out}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=STATIONS_FILE,
                    help=f"archivo de salida (por defecto {STATIONS_FILE.relative_to(ROOT)})")
    sys.exit(main(ap.parse_args().out))
