"""Distancia a transporte: traduce "cerca del metro" en un número verificable.

Ningún portal filtra por distancia al metro en su URL, y los avisos casi nunca la dan
en metros ("a pasos del Metro Pedro de Valdivia"). Pero cuatro de los cinco publican
las coordenadas del inmueble. Con ellas y las estaciones de OpenStreetMap se calcula:

  distancia a pie estimada = distancia en línea recta × WALK_FACTOR

WALK_FACTOR = 1,3 es un factor de rodeo urbano típico (la literatura sobre "circuity"
reporta 1,2–1,4 en ciudades con grilla). Se elige el lado conservador del rango: si se
subestima la caminata, se aprobaría una propiedad que está lejos.

Cobertura: estaciones de metro (Metro de Santiago) y de tren (EFE: Nos, Metrotren,
Tren Alameda–Melipilla) de la RM, en data/scout/estaciones_rm.json.

Las estaciones son un archivo ESTÁTICO versionado, no una consulta en cada búsqueda:
son datos que cambian una vez al año, y el robots.txt de overpass-api.de prohíbe /api/
a los rastreadores. Se regenera a mano con scripts/build_estaciones_rm.py, que hace una
única consulta a la API de Overpass (uso previsto por su política: consultas
esporádicas). Datos © colaboradores de OpenStreetMap, licencia ODbL. Los paraderos de bus NO se calculan: OSM no
distingue un paradero troncal de uno cualquiera, y hay uno cada pocas cuadras en toda la
ciudad; para bus solo cuenta una distancia que el propio aviso declare.
"""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import quote

WALK_FACTOR = 1.3
STATIONS_FILE = Path(__file__).resolve().parents[2] / "data" / "scout" / "estaciones_rm.json"
OVERPASS = "https://overpass-api.de/api/interpreter"
# Caja que contiene la Región Metropolitana (sur, oeste, norte, este).
RM_BBOX = (-34.30, -71.75, -32.90, -69.75)
_QUERY = ('[out:json][timeout:60];('
          'node["railway"="station"]({b});'
          'node["public_transport"="station"]["subway"="yes"]({b});'
          ');out body;')


@dataclass
class Station:
    name: str
    kind: str      # "metro" | "tren"
    lat: float
    lon: float


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def in_service(tags: dict, year: Optional[int] = None) -> bool:
    """Estación con servicio de pasajeros HOY. OSM también trae estaciones proyectadas o en
    construcción (tren Alameda–Melipilla: start_date 2027/2029, claves `proposed:*`; Línea 7
    del metro) y estaciones de carga sin pasajeros (línea al norte: Colina, Batuco,
    Polpaico, sin `public_transport`). Contarlas aprobaría avisos "cerca" de un tren que no pasa."""
    year = year or time.localtime().tm_year
    if any(k.startswith(("proposed", "construction", "disused", "abandoned")) for k in tags):
        return False
    if tags.get("railway") in ("proposed", "construction", "disused", "abandoned"):
        return False
    start = re.match(r"\d{4}", tags.get("start_date") or "")
    if start and int(start.group(0)) > year:
        return False
    return tags.get("public_transport") == "station"


def classify(tags: dict) -> Optional[str]:
    """metro | tren | None (funiculares, teleféricos y estaciones sin servicio no cuentan)."""
    if tags.get("station") in ("funicular", "light_rail", "monorail") or not in_service(tags):
        return None
    # La caja de la RM alcanza la costa: fuera los ascensores de Valparaíso y Merval.
    if (tags.get("name") or "").startswith("Ascensor") or "valpara" in (
            (tags.get("operator") or "") + (tags.get("network") or "")).casefold():
        return None
    network = (tags.get("network") or "").casefold()
    if tags.get("station") == "subway" or tags.get("subway") == "yes" or "metro de santiago" in network:
        return "metro"
    # Tren: solo estaciones de EFE con un servicio de pasajeros declarado (network). Deja
    # fuera ferrocarriles de parque sin operador (Lo Barnechea) y estaciones de EFE sin
    # servicio identificado (Tiltil, Rungue).
    if tags.get("railway") == "station" and "efe" in (tags.get("operator") or "").casefold() and tags.get("network"):
        return "tren"
    return None


def parse_overpass(data: dict) -> List[Station]:
    out, seen = [], set()
    for e in data.get("elements", []):
        tags = e.get("tags") or {}
        kind, name = classify(tags), tags.get("name")
        if not kind or not name or "lat" not in e:
            continue
        key = (name, kind)
        if key in seen:           # una estación puede venir como varios nodos
            continue
        seen.add(key)
        out.append(Station(name=name, kind=kind, lat=float(e["lat"]), lon=float(e["lon"])))
    return out


def overpass_url() -> str:
    return f"{OVERPASS}?data={quote(_QUERY.format(b=','.join(str(x) for x in RM_BBOX)))}"


def load_stations(path: Path = STATIONS_FILE) -> List[Station]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Station(**s) for s in data["estaciones"]]


def nearest(lat: float, lon: float, stations: Iterable[Station], kinds: Iterable[str]
            ) -> Optional[Tuple[Station, int]]:
    """(estación, metros a pie estimados) de la más cercana de los tipos pedidos."""
    kinds = set(kinds)
    best = None
    for s in stations:
        if s.kind not in kinds:
            continue
        d = haversine_m(lat, lon, s.lat, s.lon)
        if best is None or d < best[1]:
            best = (s, d)
    if best is None:
        return None
    return best[0], int(round(best[1] * WALK_FACTOR))
