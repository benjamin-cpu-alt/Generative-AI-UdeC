"""Descarte barato con datos ESTRUCTURADOS del portal, antes de abrir el aviso y antes
de gastar una llamada al LLM. Solo descarta con un dato conocido que viola el filtro;
lo desconocido pasa (lo decidirá el análisis, que lo marcará como no verificable).
"""
from __future__ import annotations

from typing import Optional

from matcher import normalize

from .listing import Listing
from .profile import BuyerProfile


def price_clp(listing: Listing, uf_value: float) -> Optional[int]:
    if listing.price_value is None or listing.price_currency not in ("UF", "CLP"):
        return None
    return normalize.to_clp(listing.price_value, listing.price_currency, uf_value)


def discard_reason(listing: Listing, profile: BuyerProfile, uf_value: float) -> Optional[str]:
    budget = profile.budget_clp(uf_value)
    clp = price_clp(listing, uf_value)
    if clp is not None and clp > budget:
        # vale también para proyectos: si el "desde" supera el presupuesto, todas las unidades lo superan
        return "presupuesto"
    beds = max(b for b in (listing.bedrooms, listing.bedrooms_max, -1) if b is not None)
    if beds >= 0 and beds < profile.dormitorios_min:
        return "dormitorios"
    if (listing.transit_walk_m is not None and "bus" not in profile.transportes
            and listing.transit_walk_m > profile.distancia_max_m):
        return "distancia_transporte"
    return None
