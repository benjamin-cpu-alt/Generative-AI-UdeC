"""Herramientas deterministas de normalización: el modelo COPIA spans de texto,
Python los convierte a números. Aquí vive la "confusión aritmética" resuelta:
el LLM nunca multiplica, nunca convierte UF→CLP, nunca compara magnitudes.

Formatos chilenos que aparecen en el catálogo:
  "3.850 UF" | "UF 4.183" | "4698 UF" | "$148.500.000" | "$980.000/mes"
  "950m" | "1,4 km" | "1,2km" | "a 300m del metro" | "15 minutos caminando" (no es distancia)
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# Número con separador de miles chileno (punto) y decimal opcional con coma.
_NUM_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?")
_DIST_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km|kms|kilómetros?|kilometros?|m|mts|metros?)\b", re.IGNORECASE)


def parse_number(text: str) -> Optional[float]:
    """'3.850' -> 3850 ; '148.500.000' -> 148500000 ; '4698' -> 4698 ; '1,5' -> 1.5"""
    m = _NUM_RE.search(text or "")
    if not m:
        return None
    entero = m.group(1).replace(".", "")
    dec = m.group(2)
    return float(f"{entero}.{dec}") if dec else float(entero)


def parse_money(text: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """Devuelve (valor, unidad) con unidad en {"UF", "CLP"} o (None, None).

    La unidad se decide por el texto ("UF" vs "$"/"CLP"/"pesos"); si no viene, por
    magnitud (un precio de vivienda en UF está en el orden de 10^3–10^4; en CLP en 10^7–10^9).
    """
    if not text:
        return None, None
    value = parse_number(text)
    if value is None:
        return None, None
    t = text.upper()
    if "UF" in t:
        return value, "UF"
    if "$" in t or "CLP" in t or "PESO" in t:
        return value, "CLP"
    return value, ("CLP" if value >= 100_000 else "UF")


def to_clp(value: float, unit: str, uf_value: float) -> int:
    if unit == "CLP":
        return int(round(value))
    return int(round(value * uf_value))


def parse_distance_m(text: Optional[str]) -> Optional[int]:
    """'950m' -> 950 ; '1,4 km' -> 1400 ; '1,2km' -> 1200 ; 'unos 15 minutos' -> None"""
    if not text:
        return None
    m = _DIST_RE.search(text)
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    unit = m.group(2).lower()
    if unit.startswith("k"):
        return int(round(value * 1000))
    return int(round(value))


def roi_pct(rent_monthly_clp: Optional[int], price_clp: int) -> Optional[float]:
    """Misma definición que la E1: (arriendo × 12) / precio × 100, dos decimales."""
    if rent_monthly_clp is None or not price_clp:
        return None
    return round(rent_monthly_clp * 12 / price_clp * 100, 2)
