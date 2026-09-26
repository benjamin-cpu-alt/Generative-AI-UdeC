"""Comunas de la Región Metropolitana y su traducción al formato de URL de cada portal.

El alcance es la RM: es donde el cálculo de distancia al metro tiene sentido (red de
Metro de Santiago + trenes de EFE) y donde se verificaron los patrones de URL
(26-sep-2026). Los slugs de cada portal se comprobaron con peticiones reales para
Providencia, Las Condes y Ñuñoa; el resto sigue la misma regla y, si un portal
responde 404/410 para una comuna, esa combinación se registra y se omite.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Dict, List, Optional

# comuna -> provincia (iCasas anida la comuna bajo la provincia en la URL)
RM: Dict[str, str] = {
    **{c: "santiago" for c in (
        "Cerrillos", "Cerro Navia", "Conchalí", "El Bosque", "Estación Central", "Huechuraba",
        "Independencia", "La Cisterna", "La Florida", "La Granja", "La Pintana", "La Reina",
        "Las Condes", "Lo Barnechea", "Lo Espejo", "Lo Prado", "Macul", "Maipú", "Ñuñoa",
        "Pedro Aguirre Cerda", "Peñalolén", "Providencia", "Pudahuel", "Quilicura",
        "Quinta Normal", "Recoleta", "Renca", "San Joaquín", "San Miguel", "San Ramón",
        "Santiago", "Vitacura")},
    **{c: "cordillera" for c in ("Puente Alto", "Pirque", "San José de Maipo")},
    **{c: "chacabuco" for c in ("Colina", "Lampa", "Tiltil")},
    **{c: "maipo" for c in ("San Bernardo", "Buin", "Calera de Tango", "Paine")},
    **{c: "melipilla" for c in ("Melipilla", "Alhué", "Curacaví", "María Pinto", "San Pedro")},
    **{c: "talagante" for c in ("Talagante", "El Monte", "Isla de Maipo", "Padre Hurtado", "Peñaflor")},
}


def fold(s: str) -> str:
    """'Ñuñoa' -> 'nunoa' ; 'Estación  Central' -> 'estacion central'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip().casefold()


_BY_FOLD = {fold(c): c for c in RM}


def canonical(name: str) -> Optional[str]:
    """Nombre oficial de la comuna, tolerando tildes y mayúsculas; None si no es de la RM."""
    return _BY_FOLD.get(fold(name))


def suggest(name: str, n: int = 3) -> List[str]:
    """Comunas parecidas, para pedir aclaración ('providensia' -> ['Providencia'])."""
    hits = difflib.get_close_matches(fold(name), list(_BY_FOLD), n=n, cutoff=0.6)
    return [_BY_FOLD[h] for h in hits]


def slug(name: str) -> str:
    """'Estación Central' -> 'estacion-central' (Yapo, TocToc, Chilepropiedades)."""
    return re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")


_ARTICLES = ("el", "la", "las", "lo", "los")


def icasas_path(name: str) -> str:
    """iCasas: provincia/comuna, y la comuna SIN artículo inicial.

    Verificado: 'Las Condes' -> 'santiago/condes', 'Ñuñoa' -> 'santiago/nunoa'; en su
    filtro de comunas aparecen también 'bosque', 'cisterna', 'florida', 'barnechea'.
    """
    parts = slug(name).split("-")
    if len(parts) > 1 and parts[0] in _ARTICLES:
        parts = parts[1:]
    return f"{RM[canonical(name) or name]}/{'-'.join(parts)}"
