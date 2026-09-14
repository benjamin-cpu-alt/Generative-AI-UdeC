"""Generador de casos sintéticos (perfil + catálogo) para destilación y evaluación.

Orden de construcción (inverso al caso E1 anotado a mano):
  1. Se elige un ESCENARIO por propiedad (pasa todo / falla por X con trampa Y).
  2. Se genera el `truth` estructurado que realiza ese escenario.
  3. Se renderiza el `text` con plantillas en español y distractores de marketing
     (incluida la trampa "comuna preferida" sobre propiedades que violan una hard).
  4. Se AUTO-VERIFICA con rules.py que el juez llega al mismo veredicto que el
     escenario intencionado. Un caso mal etiquetado aborta la generación.

Uso:
  python -m matcher.generate --train 300 --test 50 --seed 2026
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .rules import (C_BEDROOMS, C_BUDGET, C_DISTANCE, C_PARKING, C_PETS,
                    evaluate_property, expected_output)
from .schema import (Case, HardConstraints, PetsPolicy, Property, SoftConstraints,
                     Truth)

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "data" / "cases"

# ---------------------------------------------------------------- vocabulario

COMUNAS = ["Providencia", "Ñuñoa", "Las Condes", "Santiago Centro", "San Miguel",
           "La Florida", "Macul", "La Reina", "Vitacura", "Independencia",
           "Recoleta", "Maipú", "Peñalolén", "Estación Central", "La Cisterna"]

METROS = ["Los Leones", "Manquehue", "Plaza Egaña", "Irarrázaval", "Ñuñoa",
          "Tobalaba", "Baquedano", "Bellas Artes", "Franklin", "Lo Vial",
          "Vicente Valdés", "Príncipe de Gales", "Escuela Militar", "Cal y Canto"]

MARKETING = ["¡Oportunidad única!", "Ideal para inversionistas.", "Precio rebajado.",
             "Excelente conectividad.", "Luminoso y con vista despejada.",
             "Recién remodelado.", "Entrega inmediata.", "Piso alto, orientación norte."]

# Frases que intentan persuadir hacia una aprobación indebida.
BUDGET_TRAPS = [
    "(¡bajo el presupuesto del cliente según nuestro tasador!)",
    "(precio negociable, el propietario está abierto a ofertas)",
    "(ligeramente sobre el techo del cliente, pero el corredor indica que es negociable)",
    "(el mejor valor por m² del sector)",
]
DISTANCE_TRAPS = ["unos {min} minutos caminando", "muy bien conectado", "a pasos de todo"]
# Frases que explotan la soft constraint de ubicación para colar una propiedad inválida.
LOCATION_TRAPS = ["¡En la comuna favorita del cliente!", "Justo en el sector que busca el comprador.",
                  "Ubicación premium, la más solicitada por sus clientes."]
# Probabilidad de que una propiedad esté en una comuna preferida (para que el ranking importe).
P_PREFERRED = 0.45

FAIL_WEIGHTS = {
    "budget_uf": 4, "budget_clp": 2, "distance": 3, "parking": 3,
    "bedrooms": 3, "pets_weight": 3, "pets_species": 2, "pets_unspecified": 2,
    "pets_none": 1, "multi": 2,
}


# ------------------------------------------------------------------ helpers

def _round_to(x: float, step: int) -> int:
    return int(round(x / step) * step)


def _uf_price_for(clp: int, uf: float) -> int:
    """Precio en UF (entero) cuyo valor en CLP es aproximadamente `clp`."""
    return int(round(clp / uf))


def _minutes(m: int) -> int:
    return max(3, int(round(m / 80)))  # ~80 m/min caminando


# ----------------------------------------------------------- generación truth

def gen_profile(rng: random.Random) -> Tuple[HardConstraints, SoftConstraints]:
    especie = rng.choice(["perro", "perro", "gato"])
    kg = rng.choice([4, 5, 6, 8, 10, 12, 15, 18, 20, 22, 25, 30]) if especie == "perro" \
        else rng.choice([3, 4, 5, 6, 7])
    hc = HardConstraints(
        presupuesto_max_clp=_round_to(rng.uniform(85e6, 230e6), 500_000),
        mascota_especie=especie,
        mascota_kg=kg,
        distancia_max_transporte_m=rng.choice([500, 600, 800, 1000, 1000, 1200, 1500]),
        dormitorios_min=rng.choice([1, 2, 2, 2, 3]),
        estacionamiento_requerido=True,
    )
    sc = SoftConstraints(ubicaciones_preferidas=rng.sample(COMUNAS, rng.choice([1, 2, 2])))
    return hc, sc


def gen_property(rng: random.Random, hc: HardConstraints, sc: SoftConstraints, uf: float,
                 scenario: str, pid: str) -> Tuple[Property, List[str]]:
    """Devuelve (propiedad, restricciones que DEBEN fallar según el escenario)."""
    fails: List[str] = []
    notes: List[str] = []

    # --- valores que cumplen por defecto ---------------------------------
    price_clp = _round_to(rng.uniform(0.72, 0.995) * hc.presupuesto_max_clp, 100_000)
    in_uf = rng.random() < 0.55
    bedrooms = min(4, hc.dormitorios_min + rng.choice([0, 0, 1, 1, 2]))
    distance = rng.randint(150, hc.distancia_max_transporte_m)
    pets = PetsPolicy(explicit=True, allowed=True, species=[], max_kg=None)
    parking = rng.choice(["propio", "asignado"])
    rent = _round_to(price_clp * rng.uniform(0.0045, 0.0085), 10_000)

    # variantes "near miss" que cumplen por poco (fuerzan aritmética exacta)
    if scenario == "pass":
        r = rng.random()
        if r < 0.35:
            price_clp = _round_to(rng.uniform(0.975, 0.995) * hc.presupuesto_max_clp, 100_000)
            in_uf = True
            notes.append("precio en UF a <2.5% del presupuesto")
        elif r < 0.55:
            pets = PetsPolicy(explicit=True, allowed=True, species=[], max_kg=hc.mascota_kg)
            notes.append("límite de peso igual al de la mascota")
        elif r < 0.70:
            distance = hc.distancia_max_transporte_m
            notes.append("distancia exactamente en el límite")
        elif r < 0.85:
            pets = PetsPolicy(explicit=True, allowed=True, species=[hc.mascota_especie], max_kg=None)
            notes.append("solo se acepta la especie del comprador (la otra está prohibida)")

    # --- escenarios de fallo ----------------------------------------------
    active = [scenario] if scenario != "multi" else rng.sample(
        ["budget_uf", "distance", "parking", "bedrooms", "pets_weight"], 2)

    for s in active:
        if s == "budget_uf":
            price_clp = _round_to(rng.uniform(1.003, 1.06) * hc.presupuesto_max_clp, 100_000)
            in_uf = True
            fails.append(C_BUDGET)
            notes.append("precio en UF sobre presupuesto + frase de marketing")
        elif s == "budget_clp":
            price_clp = _round_to(rng.uniform(1.002, 1.05) * hc.presupuesto_max_clp, 500_000)
            if price_clp <= hc.presupuesto_max_clp:
                price_clp = hc.presupuesto_max_clp + 500_000
            in_uf = False
            fails.append(C_BUDGET)
            notes.append("precio en CLP sobre presupuesto, 'negociable'")
        elif s == "distance":
            distance = int(hc.distancia_max_transporte_m * rng.uniform(1.15, 1.9))
            distance = _round_to(distance, 50)
            fails.append(C_DISTANCE)
            notes.append("distancia excedida, minimizada en minutos caminando")
        elif s == "parking":
            parking = rng.choice(["visitas", "calle", "ninguno"])
            fails.append(C_PARKING)
            notes.append(f"estacionamiento '{parking}' menciona la palabra pero no cumple")
        elif s == "bedrooms":
            bedrooms = max(0, hc.dormitorios_min - 1)
            fails.append(C_BEDROOMS)
            notes.append("dormitorio 'convertible' que no es real")
        elif s == "pets_weight":
            lim = max(2, int(hc.mascota_kg - rng.choice([1, 2, 3, 5, 8])))
            lim = min(lim, int(hc.mascota_kg) - 1)
            pets = PetsPolicy(explicit=True, allowed=True, species=[], max_kg=lim)
            fails.append(C_PETS)
            notes.append(f"límite de peso {lim}kg < mascota {hc.mascota_kg}kg")
        elif s == "pets_species":
            otra = "gato" if hc.mascota_especie == "perro" else "perro"
            pets = PetsPolicy(explicit=True, allowed=True, species=[otra], max_kg=None)
            fails.append(C_PETS)
            notes.append("acepta la otra especie, no la del comprador")
        elif s == "pets_unspecified":
            pets = PetsPolicy(explicit=False, allowed=False, species=[], max_kg=None)
            fails.append(C_PETS)
            notes.append("política de mascotas ausente (debe ser explícita)")
        elif s == "pets_none":
            pets = PetsPolicy(explicit=True, allowed=False, species=[], max_kg=None)
            fails.append(C_PETS)
            notes.append("no se aceptan mascotas")

    # Precio final: si va en UF, el CLP real es price_uf * uf (entero de UF).
    price_uf: Optional[int] = None
    if in_uf:
        price_uf = _uf_price_for(price_clp, uf)
        price_clp_real = int(round(price_uf * uf))
        # el redondeo a UF entera puede cruzar el umbral: corregir para mantener el escenario
        if C_BUDGET in fails and price_clp_real <= hc.presupuesto_max_clp:
            price_uf += 1
        elif C_BUDGET not in fails and price_clp_real > hc.presupuesto_max_clp:
            price_uf -= 1
        price_clp = int(round(price_uf * uf))

    if C_BUDGET not in fails and price_clp > hc.presupuesto_max_clp:
        price_clp = hc.presupuesto_max_clp  # clamp defensivo tras redondeos

    # Aprobadas: 85 % con arriendo (el resto queda con roi_pct null, al final del ranking).
    has_rent = rng.random() < (0.85 if not fails else 0.6)
    preferred = rng.random() < P_PREFERRED
    location = rng.choice(sc.ubicaciones_preferidas) if preferred else \
        rng.choice([c for c in COMUNAS if c not in sc.ubicaciones_preferidas])
    if preferred and fails:
        notes.append("comuna preferida (soft) pero viola una hard constraint: no rescata")
    truth = Truth(
        bedrooms=bedrooms, distance_transport_m=distance, pets=pets, parking=parking,
        price_uf=price_uf, price_clp=None if in_uf else price_clp,
        rent_monthly_clp=rent if has_rent else None,
        location=location,
    )
    text = render_text(rng, truth, hc, scenario, active, location_trap=preferred and bool(fails))
    prop = Property(id=pid, text=text, truth=truth)
    return prop, sorted(set(fails)), notes


# ------------------------------------------------------------ render texto

def _fmt_clp(n: int) -> str:
    return "$" + f"{n:,}".replace(",", ".")


def _fmt_uf(rng: random.Random, n: int) -> str:
    return rng.choice([f"{n:,} UF".replace(",", "."), f"UF {n:,}".replace(",", "."), f"{n} UF"])


def render_text(rng: random.Random, t: Truth, hc: HardConstraints, scenario: str,
                active: List[str], location_trap: bool = False) -> str:
    kind = "Casa" if t.bedrooms >= 3 and rng.random() < 0.3 else "Depto"
    m2 = 28 + 17 * max(1, t.bedrooms) + rng.randint(0, 18)
    banos = max(1, min(t.bedrooms, rng.randint(1, 2)))
    parts = []

    # Dormitorios / baños
    if "bedrooms" in active:
        extra = rng.choice([
            "escritorio (walk-in office, fácilmente convertible en segundo dormitorio)",
            "sala de estar amplia que puede usarse como dormitorio adicional",
            "loggia cerrada, ideal como pieza extra",
        ])
        if t.bedrooms == 0:
            parts.append(f"{kind} estudio en {t.location}, {m2}m², ambiente único + {extra}, {banos}B.")
        else:
            parts.append(f"{kind} en {t.location}, {m2}m², {t.bedrooms} dormitorio{'s' if t.bedrooms > 1 else ''} + {extra}, {banos}B.")
    else:
        fmt = rng.choice([f"{t.bedrooms}D/{banos}B", f"{t.bedrooms} dormitorios, {banos} baño{'s' if banos > 1 else ''}"])
        parts.append(f"{kind} en {t.location}, {m2}m², {fmt}.")

    # Precio
    if t.price_uf is not None:
        price = f"Precio: {_fmt_uf(rng, t.price_uf)}"
    else:
        price = f"Valor {_fmt_clp(t.price_clp)}"
    if "budget_uf" in active or "budget_clp" in active:
        price += " " + rng.choice(BUDGET_TRAPS)
    elif rng.random() < 0.25:
        price = rng.choice(["Precio rebajado a", "Precio:"]) + " " + price.split(": ", 1)[-1].replace("Valor ", "")
    parts.append(price + ".")

    # Distancia
    d = t.distance_transport_m
    if "distance" in active:
        km = f"{d/1000:.1f}".replace(".", ",")
        parts.append(rng.choice([
            f"Ubicado a {km} km de la estación {rng.choice(METROS)}, {DISTANCE_TRAPS[0].format(min=_minutes(d))}.",
            f"A {d}m del metro {rng.choice(METROS)}, {rng.choice(DISTANCE_TRAPS[1:])}.",
        ]))
    else:
        r = rng.random()
        if r < 0.6:
            parts.append(f"A {d}m de la estación de metro {rng.choice(METROS)}.")
        elif r < 0.8:
            parts.append(f"A {d}m de paradero de buses troncal, y {_fmt_km(d + rng.randint(400, 1200))} del metro más cercano.")
        else:
            far = d + rng.randint(600, 1500)
            parts.append(f"A {_fmt_km(far)} de la estación de metro más cercana, pero cuenta con paradero de buses troncal a {d}m.")

    # Mascotas
    p = t.pets
    if not p.explicit:
        if rng.random() < 0.5:
            parts.append("No se especifica política de mascotas.")
        # else: se omite la frase por completo (más difícil)
    elif not p.allowed:
        parts.append(rng.choice(["No se aceptan mascotas.", "Edificio sin mascotas por reglamento de copropiedad."]))
    elif p.max_kg is not None:
        parts.append(rng.choice([
            f"Se aceptan mascotas pequeñas y medianas hasta {p.max_kg:g}kg, previa autorización de la administración.",
            f"Aceptamos mascotas, gatos y perros hasta {p.max_kg:g}kg.",
            f"Pet friendly con límite de {p.max_kg:g}kg por mascota.",
        ]))
    elif p.species:
        sp = p.species[0]
        otra = "gato" if sp == "perro" else "perro"
        parts.append(rng.choice([
            f"Se aceptan {sp}s, {otra}s no permitidos por reglamento de copropiedad.",
            f"Solo se admiten {sp}s de cualquier tamaño.",
        ]))
    else:
        parts.append(rng.choice([
            "Edificio pet friendly, aceptamos mascotas sin restricciones de raza o tamaño.",
            "100% pet friendly, sin restricciones de tamaño ni especie.",
            "Comunidad pet friendly, aceptamos perros y gatos de cualquier tamaño.",
        ]))

    # Estacionamiento
    parts.append({
        "propio": rng.choice(["Incluye 1 estacionamiento.", "Incluye estacionamiento propio.",
                              "Cuenta con 1 estacionamiento en subterráneo, valor incluido en el precio."]),
        "asignado": rng.choice(["Incluye 1 estacionamiento subterráneo asignado.",
                                "Incluye 1 estacionamiento techado asignado."]),
        "visitas": "Cuenta con estacionamiento de visitas disponible, no asignado de forma permanente.",
        "calle": "Estacionamiento en la calle, sin problemas para aparcar en el sector.",
        "ninguno": rng.choice(["Sin estacionamiento.", "No incluye estacionamiento (posible arriendo en edificio vecino)."]),
    }[t.parking])

    # Arriendo
    if t.rent_monthly_clp is not None:
        parts.append(rng.choice([f"Arriendo estimado: {_fmt_clp(t.rent_monthly_clp)}/mes.",
                                 f"Arriendo referencial de la zona: {_fmt_clp(t.rent_monthly_clp)}/mes."]))

    # Marketing
    if location_trap and rng.random() < 0.7:
        parts.insert(1, rng.choice(LOCATION_TRAPS))
    elif rng.random() < 0.6:
        parts.insert(rng.randint(1, len(parts)), rng.choice(MARKETING))

    return " ".join(parts)


def _fmt_km(m: int) -> str:
    return f"{m/1000:.1f}".replace(".", ",") + "km"


# ------------------------------------------------------------------ casos

def _pick_scenarios(rng: random.Random, n: int) -> List[str]:
    n_pass = max(1, round(n * rng.uniform(0.2, 0.45)))
    if rng.random() < 0.05:
        n_pass = 0  # algunos casos sin ninguna aprobada (prueba el "rechazar todo")
    fails = list(FAIL_WEIGHTS)
    w = [FAIL_WEIGHTS[f] for f in fails]
    scen = ["pass"] * n_pass + rng.choices(fails, weights=w, k=n - n_pass)
    rng.shuffle(scen)
    return scen


def gen_case(rng: random.Random, case_id: str) -> Tuple[Case, Dict]:
    uf = _round_to(rng.uniform(38000, 40600), 50)
    hc, sc = gen_profile(rng)
    n = rng.randint(5, 9)
    props, meta = [], []
    letters = rng.sample("ABCDEFGHJKLMNPQRSTUVWXYZ", n)
    for letter, scenario in zip(letters, _pick_scenarios(rng, n)):
        pid = f"PROP-{letter}{rng.randint(10, 99)}"
        prop, must_fail, notes = gen_property(rng, hc, sc, uf, scenario, pid)
        props.append(prop)
        meta.append({"id": pid, "scenario": scenario, "expected_fail": must_fail, "notes": notes})
    case = Case(id=case_id, uf_value=uf, hard_constraints=hc, properties=props,
                soft_constraints=sc)

    # Auto-verificación: el juez debe coincidir con el escenario intencionado.
    for prop, m in zip(props, meta):
        got = sorted(evaluate_property(prop, case).failed_constraints)
        if got != m["expected_fail"]:
            raise RuntimeError(f"{case_id}/{prop.id}: escenario {m['scenario']} esperaba "
                               f"{m['expected_fail']} pero rules.py dio {got}")
    return case, {"properties": meta}


def case_to_dict(case: Case, meta: Dict) -> Dict:
    d = {
        "id": case.id,
        "uf_value": case.uf_value,
        "hard_constraints": asdict(case.hard_constraints),
        "soft_constraints": asdict(case.soft_constraints),
        "properties": [],
    }
    for p, m in zip(case.properties, meta["properties"]):
        d["properties"].append({
            "id": p.id, "text": p.text, "truth": asdict(p.truth),
            "scenario": m["scenario"], "trap": "; ".join(m["notes"]) or None,
        })
    return d


def generate(n_train: int, n_test: int, seed: int, out_dir: Path = CASES_DIR) -> Dict:
    rng = random.Random(seed)
    stats = {"train": 0, "test": 0, "properties": 0, "approved": 0, "preferred_location": 0,
             "cases_with_nontrivial_ranking": 0, "scenarios": {}}
    for split, n in (("train", n_train), ("test", n_test)):
        d = out_dir / split
        d.mkdir(parents=True, exist_ok=True)
        for i in range(1, n + 1):
            cid = f"{split}_{i:04d}"
            case, meta = gen_case(rng, cid)
            (d / f"{cid}.json").write_text(
                json.dumps(case_to_dict(case, meta), ensure_ascii=False, indent=2), encoding="utf-8")
            stats[split] += 1
            exp = expected_output(case)
            stats["preferred_location"] += sum(e.preferred_location for e in exp.by_id.values())
            stats["cases_with_nontrivial_ranking"] += len(exp.ranked_ids) >= 2
            for m in meta["properties"]:
                stats["properties"] += 1
                stats["approved"] += m["scenario"] == "pass"
                stats["scenarios"][m["scenario"]] = stats["scenarios"].get(m["scenario"], 0) + 1
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", type=int, default=300)
    ap.add_argument("--test", type=int, default=50)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=str(CASES_DIR))
    a = ap.parse_args(argv)
    stats = generate(a.train, a.test, a.seed, Path(a.out))
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
