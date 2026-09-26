"""Necesidades del comprador: el cuestionario y su traducción a las restricciones del
analizador (`matcher.schema.HardConstraints` / `SoftConstraints`).

Se recolectan EXCLUSIVAMENTE estos datos; si una respuesta falta o es ambigua, se
repregunta en vez de suponer:
  presupuesto máximo (UF o CLP), ¿mascota? y su tamaño, distancia máxima a transporte
  (y qué transporte), dormitorios reales mínimos, ¿estacionamiento?, comunas.

Dos decisiones de traducción, ambas conservadoras (ante la duda, no aprobar):
  - Tamaño de mascota -> kg: se usa el TOPE de cada rango (pequeña 10 kg, mediana 25 kg,
    grande 45 kg). Un aviso que acepta "hasta 20 kg" no sirve para una mediana.
  - La especie no se pregunta. Se usa una especie que ningún aviso nombra, así que un
    aviso que restringe la especie ("solo gatos") no se aprueba: no se puede confirmar
    que la mascota del comprador entre. Los que aceptan mascotas sin restringir sí.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from matcher import normalize
from matcher.schema import HardConstraints, SoftConstraints

from . import comunas

PET_SIZES = {"pequeña": 10.0, "mediana": 25.0, "grande": 45.0}
UNKNOWN_SPECIES = "especie_no_indicada"
TRANSPORTS = ("metro", "tren", "bus")


@dataclass
class BuyerProfile:
    presupuesto: float
    moneda: str                              # "UF" | "CLP"
    tiene_mascota: bool
    tamano_mascota: Optional[str]            # pequeña | mediana | grande (si tiene mascota)
    distancia_max_m: int
    transportes: List[str]                   # subconjunto de TRANSPORTS
    dormitorios_min: int
    requiere_estacionamiento: bool
    comunas: List[str]
    tipos: List[str] = field(default_factory=lambda: ["departamento", "casa"])

    # ------------------------------------------------------------ validación ----
    def errors(self) -> List[str]:
        e = []
        if self.moneda not in ("UF", "CLP"):
            e.append("moneda del presupuesto debe ser UF o CLP")
        if not self.presupuesto or self.presupuesto <= 0:
            e.append("presupuesto debe ser positivo")
        if self.tiene_mascota and self.tamano_mascota not in PET_SIZES:
            e.append(f"tamaño de mascota debe ser uno de {list(PET_SIZES)}")
        if self.distancia_max_m <= 0:
            e.append("distancia máxima debe ser positiva")
        if not self.transportes or any(t not in TRANSPORTS for t in self.transportes):
            e.append(f"transportes debe ser un subconjunto de {list(TRANSPORTS)}")
        if self.dormitorios_min < 0:
            e.append("dormitorios mínimos no puede ser negativo")
        if not self.comunas:
            e.append("indique al menos una comuna")
        bad = [c for c in self.comunas if comunas.canonical(c) is None]
        if bad:
            e.append(f"comunas fuera de la Región Metropolitana o mal escritas: {bad}")
        if not self.tipos or any(t not in ("departamento", "casa") for t in self.tipos):
            e.append("tipos debe ser departamento y/o casa")
        return e

    # ------------------------------------------------------------ traducción ----
    def budget_clp(self, uf_value: float) -> int:
        return normalize.to_clp(self.presupuesto, self.moneda, uf_value)

    def hard_constraints(self, uf_value: float) -> HardConstraints:
        return HardConstraints(
            presupuesto_max_clp=self.budget_clp(uf_value),
            # sin mascota el análisis ignora la restricción (ver analyze.py); los valores
            # de aquí no importan en ese caso
            mascota_especie=UNKNOWN_SPECIES,
            mascota_kg=PET_SIZES.get(self.tamano_mascota or "", 0.0),
            distancia_max_transporte_m=self.distancia_max_m,
            dormitorios_min=self.dormitorios_min,
            estacionamiento_requerido=self.requiere_estacionamiento,
        )

    def soft_constraints(self) -> SoftConstraints:
        return SoftConstraints(ubicaciones_preferidas=[comunas.canonical(c) or c for c in self.comunas])

    # ---------------------------------------------------------------- E/S ----
    @staticmethod
    def load(path) -> "BuyerProfile":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        p = BuyerProfile(**d)
        p.comunas = [comunas.canonical(c) or c for c in p.comunas]
        return p

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def summary(self) -> str:
        mascota = f"sí, {self.tamano_mascota} (≤ {PET_SIZES[self.tamano_mascota]:g} kg)" if self.tiene_mascota else "no"
        pres = (f"UF {self.presupuesto:,.0f}" if self.moneda == "UF" else f"${self.presupuesto:,.0f}").replace(",", ".")
        return "\n".join([
            f"  Presupuesto máximo : {pres}",
            f"  Mascota            : {mascota}",
            f"  Transporte         : {' / '.join(self.transportes)} a ≤ {self.distancia_max_m} m",
            f"  Dormitorios reales : ≥ {self.dormitorios_min}",
            f"  Estacionamiento    : {'requerido' if self.requiere_estacionamiento else 'no requerido'}",
            f"  Comunas            : {', '.join(self.comunas)}",
            f"  Tipos              : {', '.join(self.tipos)}",
        ])


# --------------------------------------------------------- parseo de respuestas ----

def parse_budget(text: str) -> Tuple[Optional[float], Optional[str]]:
    """'4.500 UF' -> (4500, 'UF') ; '$180.000.000' -> (180000000, 'CLP') ;
    '180 millones' -> (180000000, 'CLP') ; '4500' -> (4500, None): sin unidad, se repregunta."""
    t = (text or "").strip()
    if not t:
        return None, None
    value = normalize.parse_number(t)
    if value is None:
        return None, None
    up = t.upper()
    if re.search(r"MILL[OÓ]N|MILLONES|\bMM\b", up):
        return value * 1_000_000, "CLP"
    if "UF" in up:
        return value, "UF"
    if "$" in up or "CLP" in up or "PESO" in up:
        return value, "CLP"
    return value, None


def parse_yes_no(text: str) -> Optional[bool]:
    t = comunas.fold(text)
    if t in ("si", "s", "yes", "y", "1", "true"):
        return True
    if t in ("no", "n", "0", "false"):
        return False
    return None


def parse_pet_size(text: str) -> Optional[str]:
    t = comunas.fold(text)
    for size in PET_SIZES:
        if t and (comunas.fold(size).startswith(t) or t.startswith(comunas.fold(size)[:4])):
            return size
    return None


def parse_distance(text: str) -> Optional[int]:
    """'800' -> 800 ; '800 m' -> 800 ; '1,2 km' -> 1200 ; 'cerca' -> None."""
    t = (text or "").strip()
    d = normalize.parse_distance_m(t)
    if d is not None:
        return d
    if re.fullmatch(r"\d+", t):
        return int(t)
    return None


def parse_transports(text: str) -> Optional[List[str]]:
    found = [t for t in TRANSPORTS if re.search(rf"\b{t}", comunas.fold(text))]
    return found or None


def parse_comunas(text: str) -> Tuple[List[str], List[Tuple[str, List[str]]]]:
    """Devuelve (reconocidas, [(no reconocida, sugerencias)])."""
    ok, bad = [], []
    for raw in re.split(r"[,;/]| y ", text or ""):
        raw = raw.strip()
        if not raw:
            continue
        c = comunas.canonical(raw)
        if c:
            if c not in ok:
                ok.append(c)
        else:
            bad.append((raw, comunas.suggest(raw)))
    return ok, bad


# ---------------------------------------------------------------- cuestionario ----

Ask = Callable[[str], str]


def _loop(ask: Ask, question: str, parse, clarify: str):
    while True:
        value = parse(ask(question))
        if value is not None:
            return value
        print(f"  ↳ {clarify}")


def questionnaire(ask: Ask = input) -> BuyerProfile:
    """Cuestionario interactivo. `ask` es inyectable para testear sin teclado."""
    print("Necesito 6 datos. Todos son filtros: una propiedad que no los cumpla no se propone.\n")

    while True:
        value, unit = parse_budget(ask("1. Presupuesto máximo de compra (ej. '4.500 UF' o '$180.000.000'): "))
        if value is None:
            print("  ↳ No encontré un monto. Escríbalo con su unidad, p.ej. 4.500 UF.")
            continue
        if unit is None:
            unit = _loop(ask, f"   ¿{value:,.0f} son UF o pesos (CLP)? ".replace(",", "."),
                         lambda s: {"uf": "UF", "clp": "CLP", "pesos": "CLP", "$": "CLP"}.get(comunas.fold(s)),
                         "Responda UF o CLP.")
        break

    has_pet = _loop(ask, "2. ¿Tiene mascota? (sí/no): ", parse_yes_no, "Responda sí o no.")
    size = None
    if has_pet:
        size = _loop(ask, "   Tamaño aproximado (pequeña ≤10 kg / mediana ≤25 kg / grande >25 kg): ",
                     parse_pet_size, "Responda pequeña, mediana o grande.")

    transports = _loop(ask, "3. ¿Qué transporte público le sirve? (metro, tren, bus; puede elegir varios): ",
                       parse_transports, "Elija entre metro, tren y bus.")
    dist = _loop(ask, "   Distancia máxima a pie hasta ese transporte (ej. '800 m' o '1 km'): ",
                 parse_distance, "Indique una distancia en metros o km; 'cerca' no se puede filtrar.")

    beds = _loop(ask, "4. Dormitorios REALES mínimos (sin contar estudios, escritorios ni closets): ",
                 lambda s: int(s) if s.strip().isdigit() else None, "Responda con un número entero.")
    parking = _loop(ask, "5. ¿Requiere estacionamiento propio o asignado? (sí/no): ",
                    parse_yes_no, "Responda sí o no.")

    while True:
        ok, bad = parse_comunas(ask("6. Comunas de interés, separadas por coma (Región Metropolitana): "))
        for raw, sug in bad:
            print(f"  ↳ No reconozco '{raw}' como comuna de la RM." + (f" ¿Quiso decir {', '.join(sug)}?" if sug else ""))
        if ok and not bad:
            break
        if ok:
            keep = parse_yes_no(ask(f"   ¿Busco solo en {', '.join(ok)}? (sí/no): "))
            if keep:
                break

    return BuyerProfile(presupuesto=value, moneda=unit, tiene_mascota=has_pet, tamano_mascota=size,
                        distancia_max_m=dist, transportes=transports, dormitorios_min=beds,
                        requiere_estacionamiento=parking, comunas=ok)
