"""Un adaptador por portal. Para agregar uno: subclase de `base.Source` + entrada aquí."""
from typing import Dict, Type

from .base import SearchQuery, Source, SourceError
from .chilepropiedades import ChilePropiedades
from .icasas import ICasas
from .portalpm import PortalPM
from .toctoc import TocToc
from .yapo import Yapo

REGISTRY: Dict[str, Type[Source]] = {
    s.name: s for s in (Yapo, PortalPM, ChilePropiedades, ICasas, TocToc)
}

__all__ = ["REGISTRY", "SearchQuery", "Source", "SourceError"]
