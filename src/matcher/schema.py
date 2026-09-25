"""Estructuras de datos de un caso de evaluación.

Cada propiedad tiene dos capas:
  - `text`: lo que ve el modelo (texto crudo del corredor, con distractores).
  - `truth`: campos estructurados que SOLO usa el verificador.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class PetsPolicy:
    explicit: bool                      # el texto declara política de mascotas
    allowed: bool = False               # se aceptan mascotas
    species: List[str] = field(default_factory=list)  # [] = cualquier especie
    max_kg: Optional[float] = None      # None = sin límite de peso


@dataclass
class Truth:
    bedrooms: int
    # Menor distancia a metro o paradero troncal. None = el aviso NO publica una distancia
    # verificable (p.ej. solo "a 10 minutos caminando"): la restricción no se puede comprobar
    # y por tanto falla, igual que una política de mascotas no explícita. Los 351 casos
    # sintéticos siempre traen un entero; esto solo ocurre en el set OOD escrito a mano.
    distance_transport_m: Optional[int]
    pets: PetsPolicy
    parking: str                        # "propio" | "asignado" | "visitas" | "calle" | "ninguno"
    price_uf: Optional[float] = None
    price_clp: Optional[int] = None
    rent_monthly_clp: Optional[int] = None
    location: Optional[str] = None


@dataclass
class Property:
    id: str
    text: str
    truth: Truth


@dataclass
class HardConstraints:
    presupuesto_max_clp: int
    mascota_especie: str
    mascota_kg: float
    distancia_max_transporte_m: int
    dormitorios_min: int
    estacionamiento_requerido: bool


@dataclass
class SoftConstraints:
    """No descalifican: determinan el ranking de las aprobadas (E1, prompt_base.txt).
    Ubicación preferida primero; dentro de cada grupo, mayor ROI = mejor."""
    ubicaciones_preferidas: List[str] = field(default_factory=list)


@dataclass
class Case:
    id: str
    uf_value: float
    hard_constraints: HardConstraints
    properties: List[Property]
    soft_constraints: SoftConstraints = field(default_factory=SoftConstraints)

    @staticmethod
    def from_dict(d: dict) -> "Case":
        hc = d["hard_constraints"]
        sc = d.get("soft_constraints") or {}
        props = []
        for p in d["properties"]:
            t = p["truth"]
            pets = PetsPolicy(**t["pets"])
            truth = Truth(
                bedrooms=t["bedrooms"],
                distance_transport_m=t["distance_transport_m"],
                pets=pets,
                parking=t["parking"],
                price_uf=t.get("price_uf"),
                price_clp=t.get("price_clp"),
                rent_monthly_clp=t.get("rent_monthly_clp"),
                location=t.get("location"),
            )
            props.append(Property(id=p["id"], text=p["text"], truth=truth))
        return Case(
            id=d["id"],
            uf_value=d["uf_value"],
            hard_constraints=HardConstraints(**hc),
            properties=props,
            soft_constraints=SoftConstraints(**sc),
        )

    @staticmethod
    def load(path) -> "Case":
        with open(Path(path), encoding="utf-8") as f:
            return Case.from_dict(json.load(f))
