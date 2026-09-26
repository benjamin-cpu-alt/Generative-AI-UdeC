"""Valor de la UF del día desde mindicador.cl (API pública que replica al Banco Central).
Si no responde, el usuario debe darlo con --uf: nunca se usa un valor inventado."""
from __future__ import annotations

import json
from typing import Optional

MINDICADOR = "https://mindicador.cl/api/uf"


def uf_today(fetcher) -> Optional[float]:
    try:
        data = json.loads(fetcher.get(MINDICADOR, accept="application/json"))
        return float(data["serie"][0]["valor"])
    except Exception:
        return None
