"""Representación común de un aviso, independiente del portal de origen.

Cada adaptador (`sources/`) llena lo que su portal publica de forma ESTRUCTURADA
(JSON-LD, JSON de la página, API) y deja en `description`/`features` el texto libre.
Lo estructurado se usa para prefiltrar y para escribir la ficha; lo libre lo lee el LLM.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class Listing:
    source: str                          # "toctoc" | "yapo" | ...
    source_id: str                       # id estable dentro del portal
    url: str
    title: str = ""
    property_type: str = ""              # "departamento" | "casa"
    comuna: Optional[str] = None
    address: Optional[str] = None
    price_value: Optional[float] = None
    price_currency: Optional[str] = None  # "UF" | "CLP"
    price_is_from: bool = False          # "Desde UF ...": precio mínimo de un proyecto
    bedrooms: Optional[int] = None
    bedrooms_max: Optional[int] = None   # proyectos con varias tipologías
    bathrooms: Optional[int] = None
    parking_spaces: Optional[int] = None
    area_m2: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    description: str = ""
    features: List[str] = field(default_factory=list)   # "Permite mascotas", "Bodega", ...
    is_project: bool = False             # proyecto nuevo con tipologías (no una unidad)
    needs_detail: bool = False           # la tarjeta no trae todo: hay que abrir el aviso
    # enriquecido después (geo.py)
    transit_name: Optional[str] = None
    transit_kind: Optional[str] = None   # "metro" | "tren"
    transit_walk_m: Optional[int] = None

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"

    def to_dict(self) -> Dict:
        return asdict(self)


# ------------------------------------------------------------------ números ----
# Convención chilena: punto = miles, coma = decimal ("3.656,36", "239.993.091").
# OJO: Yapo muestra "UF 9,950" con coma de MILES en sus tarjetas; por eso su precio se
# toma del JSON-LD (número puro) y nunca del texto de la tarjeta.

_CL_NUM = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def cl_number(text) -> Optional[float]:
    """'5.850' -> 5850 ; '3.656,36' -> 3656.36 ; '239.993.091' -> 239993091 ; 9950 -> 9950."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = _CL_NUM.search(str(text))
    if not m:
        return None
    return float(m.group(0).replace(".", "").replace(",", "."))


def first_int(text) -> Optional[int]:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    m = re.search(r"\d+", str(text))
    return int(m.group(0)) if m else None


def fmt_cl(value: float, decimals: int = 0) -> str:
    """4250.5 -> '4.250,5' ; 150000000 -> '150.000.000' (formato que lee normalize.py)."""
    if decimals == 0 or float(value).is_integer():
        return f"{round(value):,}".replace(",", ".")
    s = f"{value:,.{decimals}f}".rstrip("0").rstrip(".")
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_price(value: float, currency: str) -> str:
    return f"UF {fmt_cl(value, 2)}" if currency == "UF" else f"${fmt_cl(value)}"


def currency_code(code: Optional[str]) -> Optional[str]:
    """schema.org usa 'CLF' para la UF (código ISO 4217)."""
    c = (code or "").strip().upper()
    if c in ("CLF", "UF"):
        return "UF"
    if c in ("CLP", "$", "PESOS"):
        return "CLP"
    return None
