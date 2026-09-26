"""Orquestador: cuestionario -> recolección en portales -> análisis (matcher) -> reporte.

  cd src
  python3 -m scout                                   # cuestionario interactivo
  python3 -m scout --perfil ../data/scout/perfil_ejemplo.json
  python3 -m scout --perfil p.json --fuentes toctoc,yapo --max-por-fuente 10
  python3 -m scout --perfil p.json --solo-scraping   # sin LLM: solo recolecta y prefiltra

Requiere Ollama con phi4-mini (el mismo modelo de la E2), salvo con --solo-scraping.
Resultados en results/scout/<fecha-hora>/: reporte.md, resultados.json, salida_e1.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from . import geo
from .analyze import APPROVED, REJECTED, REVIEW, analyze_one, llm_extractor
from .collect import collect
from .ficha import render
from .fetch import PoliteFetcher
from .profile import BuyerProfile, parse_yes_no, questionnaire
from .report import summary_text, write_all
from .sources import REGISTRY
from .uf import uf_today

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "results" / "scout"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perfil", help="JSON con el perfil del comprador (omite el cuestionario)")
    ap.add_argument("--guardar-perfil", help="guarda el perfil del cuestionario en este JSON")
    ap.add_argument("--fuentes", default=",".join(REGISTRY), help=f"subconjunto de {','.join(REGISTRY)}")
    ap.add_argument("--max-por-fuente", type=int, default=20, help="avisos analizados por portal (tope)")
    ap.add_argument("--max-paginas", type=int, default=2, help="páginas de resultados por comuna y tipo")
    ap.add_argument("--uf", type=float, help="valor de la UF (por defecto, el del día en mindicador.cl)")
    ap.add_argument("--modelo", default="phi4-mini:latest")
    ap.add_argument("--solo-scraping", action="store_true", help="no llama al LLM")
    ap.add_argument("--pausa", type=float, default=3.0, help="segundos mínimos entre peticiones a un mismo sitio")
    ap.add_argument("--cache", default=str(OUT_ROOT / "cache"), help="caché de páginas (TTL 6 h)")
    ap.add_argument("--out", help="carpeta de salida (por defecto results/scout/<fecha-hora>)")
    a = ap.parse_args(argv)

    # 1. Necesidades del comprador --------------------------------------------------
    if a.perfil:
        profile = BuyerProfile.load(a.perfil)
    else:
        profile = questionnaire()
        if a.guardar_perfil:
            profile.save(a.guardar_perfil)
    errors = profile.errors()
    if errors:
        print("Perfil inválido:\n  - " + "\n  - ".join(errors), file=sys.stderr)
        return 2
    print("\nBuscaré con estos filtros:\n" + profile.summary())
    if not a.perfil and parse_yes_no(input("\n¿Confirma? (sí/no): ")) is not True:
        print("Búsqueda cancelada.")
        return 1

    sources = [s.strip() for s in a.fuentes.split(",") if s.strip()]
    unknown = [s for s in sources if s not in REGISTRY]
    if unknown:
        print(f"fuentes desconocidas: {unknown} (use {','.join(REGISTRY)})", file=sys.stderr)
        return 2

    fetcher = PoliteFetcher(min_delay=a.pausa, cache_dir=Path(a.cache), log=lambda m: print(f"  · {m}"))

    # 2. Datos auxiliares -------------------------------------------------------------
    uf = a.uf or uf_today(fetcher)
    if not uf:
        print("No pude obtener la UF del día desde mindicador.cl; indíquela con --uf.", file=sys.stderr)
        return 2
    print(f"\nUF del día: ${uf:,.2f}".replace(",", "§").replace(".", ",").replace("§", "."))
    try:
        stations = geo.load_stations()
        print(f"Estaciones de metro/tren (OpenStreetMap, {geo.STATIONS_FILE.name}): {len(stations)}")
    except (OSError, ValueError, KeyError) as e:
        stations = []
        print(f"  · sin archivo de estaciones ({e}); la distancia solo se tomará del texto de cada aviso")

    # 3. Recolección ------------------------------------------------------------------
    print(f"\nBuscando en: {', '.join(sources)} (pausa ≥ {a.pausa:g} s entre peticiones a un mismo sitio)")
    col = collect(profile, fetcher, uf, stations, sources, a.max_por_fuente, a.max_paginas)
    status = {k: asdict(v) for k, v in col.status.items()}
    failed = [k for k, v in col.status.items() if not v.ok]
    if failed:
        print(f"\nFuentes que fallaron: {', '.join(f'{k} ({col.status[k].error})' for k in failed)}")
    print(f"\n{len(col.listings)} avisos pasan al análisis "
          f"(descartados por datos del portal: {sum(col.discarded.values())}, duplicados entre portales: {col.duplicates})")

    out_dir = Path(a.out) if a.out else OUT_ROOT / time.strftime("%Y%m%d-%H%M%S")
    if a.solo_scraping:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "avisos.json").write_text(json.dumps(
            [dict(l.to_dict(), ficha=render(l)) for l in col.listings], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n--solo-scraping: avisos y fichas en {out_dir / 'avisos.json'}")
        return 0

    # 4. Análisis con la herramienta de la E2 -----------------------------------------
    extract = llm_extractor(a.modelo)
    results = []
    t0 = time.time()
    for i, l in enumerate(col.listings, 1):
        r = analyze_one(l, profile, uf, extract)
        results.append(r)
        tag = {APPROVED: "APROBADA", REVIEW: "revisar", REJECTED: "rechazada"}[r.bucket]
        detail = ", ".join(r.violated or r.unverifiable) or r.note
        print(f"  [{i}/{len(col.listings)}] {tag:9} {l.source}:{(l.title or l.source_id)[:50]}"
              + (f" — {detail}" if detail else ""), flush=True)
    print(f"análisis: {time.time() - t0:.0f} s")

    # 5. Reporte ----------------------------------------------------------------------
    print(summary_text(results, col.discarded, status))
    write_all(out_dir, results, col.discarded, status, profile, uf)
    print(f"\nReporte: {out_dir / 'reporte.md'}\nDetalle trazable: {out_dir / 'resultados.json'}"
          f"\nJSON de la E1: {out_dir / 'salida_e1.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
