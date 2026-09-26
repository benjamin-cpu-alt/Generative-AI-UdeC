"""Paso 2 del set REAL: anotación de los 16 avisos sorteados por scripts/sample_real.py.

El texto de cada propiedad es la FICHA exacta de data/cases/real/fuente/muestra.json (lo que
ven baseline y solución); aquí solo se agrega la verdad (`truth`) leída de ese texto,
qué restricciones deben fallar (`expect`) y una nota con cada decisión discutible. Igual
que en el set OOD, el script aborta si rules.py no llega al veredicto anotado.

Decisiones que se fijaron ANTES de correr ningún modelo:
  - Comprador: el de la E1 (data/perfil_comprador_ejemplo.json y case_001_e1): tope
    $150.000.000, perro de 18 kg, transporte a <= 1.000 m, 2 dormitorios, estacionamiento
    requerido; comunas preferidas Providencia y Ñuñoa. No se ajusta a los avisos.
  - UF del día de la descarga (26-sep-2026, mindicador.cl): $41.024,46.
  - Casos: 4 de 4 avisos, uno de cada portal (R01, R05, R09, R13 / R02, R06, ...).
  - Convenciones de anotación (las mismas del set OOD):
      * dormitorios REALES: la pieza de servicio y el "estudio" no cuentan; si el portal
        y la descripción discrepan, manda la descripción más específica (se anota);
      * distancia: la única cifra en metros de la ficha (la estimada con OSM); si no hay
        ninguna, no verificable (None) -> falla;
      * mascotas: solo "admite/permite mascotas" explícito cuenta como permiso;
      * estacionamiento: "Incluye N estacionamientos" / listado como característica =
        propio; "sin estacionamiento" = ninguno; no mencionado = ninguno (no verificable);
        "estacionamientos de visitas" del edificio no dice nada de la unidad.

Resultado de la anotación: con este comprador NINGÚN aviso se aprueba. Solo 3 de 16
declaran aceptar mascotas y los tres fallan en otra restricción. El set mide, entonces,
aprobaciones indebidas y exactitud de lectura sobre texto real, no aciertos positivos.
R08 es el caso límite: cumple todo salvo mascotas, que el aviso no menciona.

Anotado por el asistente de código (Claude) sobre las fichas; pendiente de revisión por
el equipo antes de la entrega.

  python3 scripts/build_real.py            # escribe data/cases/real/real_00N.json
  python3 scripts/build_real.py --check
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from matcher.rules import evaluate_property                      # noqa: E402
from matcher.schema import Case, HardConstraints, PetsPolicy, Truth  # noqa: E402

REAL_DIR = ROOT / "data" / "cases" / "real"
UF = 41_024.46
BUYER = dict(presupuesto_max_clp=150_000_000, mascota_especie="perro", mascota_kg=18,
             distancia_max_transporte_m=1000, dormitorios_min=2, estacionamiento_requerido=True)
PREFS = ["Providencia", "Ñuñoa"]

ANY = PetsPolicy(explicit=True, allowed=True, species=[], max_kg=None)
NONE_ = PetsPolicy(explicit=False, allowed=False, species=[], max_kg=None)

B, M, D, R, E = "presupuesto", "mascotas", "distancia_transporte", "dormitorios", "estacionamiento"

# R-nn = posición en muestra.json (1-based). truth: dormitorios, distancia, mascotas,
# estacionamiento, precio (uf o clp), comuna.
ANNOTATION = {
    "R01": dict(beds=3, dist=None, pets=ANY, parking="propio", uf=4420, loc="Santiago", expect=[B, D],
                note="Yapo sin coordenadas: la ficha no trae distancia"),
    "R02": dict(beds=4, dist=568, pets=NONE_, parking="propio", uf=9790, loc="Ñuñoa", expect=[B, M]),
    "R03": dict(beds=1, dist=898, pets=ANY, parking="ninguno", uf=2300, loc="Ñuñoa", expect=[R, E],
                note="'Sin Estacionamiento' + 'ni estacionamiento'; el de visitas es del edificio"),
    "R04": dict(beds=0, dist=None, pets=ANY, parking="ninguno", uf=1400, loc="Providencia", expect=[D, R, E],
                note="'tipo Studio', '1 espacio/dormitorio' = estudio (0); '3 cuadras' no es distancia"),
    "R05": dict(beds=6, dist=1330, pets=NONE_, parking="ninguno", clp=260_000_000, loc="Santiago",
                expect=[B, M, D, E], note="6D es el dato del portal; la descripción dice 'varias piezas'"),
    "R06": dict(beds=1, dist=226, pets=NONE_, parking="ninguno", uf=1650, loc="Providencia", expect=[M, R, E],
                note="'2 Ambientes (Dormitorio Living Comedor)', '1 Espacioso Dormitorio'"),
    "R07": dict(beds=2, dist=648, pets=NONE_, parking="propio", uf=6000, loc="Providencia", expect=[B, M],
                note="'Estacionamientos: 1'; el 'Estacionamiento de Visitas' es amenidad del edificio"),
    "R08": dict(beds=3, dist=825, pets=NONE_, parking="propio", clp=140_000_000, loc="Ñuñoa", expect=[M],
                note="CASO LÍMITE: cumple todo salvo mascotas, que no se mencionan"),
    "R09": dict(beds=2, dist=1137, pets=NONE_, parking="ninguno", uf=10409, loc="Providencia", expect=[B, M, D, E],
                note="sin '2D/' en la ficha: el número sale de '2 dormitorios en suite'"),
    "R10": dict(beds=1, dist=927, pets=NONE_, parking="ninguno", uf=3300, loc="Providencia", expect=[M, R, E],
                note="'1 Dormitorio / Ambiente', 22 m²: 1 (o estudio, 0); falla igual con mínimo 2"),
    "R11": dict(beds=2, dist=1667, pets=NONE_, parking="propio", uf=2800, loc="La Florida", expect=[M, D],
                note="'Estacionamiento,' en la lista de lo que incluye; 'a pasos del metro' no es distancia"),
    "R12": dict(beds=5, dist=2005, pets=NONE_, parking="propio", uf=20000, loc="La Florida", expect=[B, M, D],
                note="CONFLICTO: el portal dice 4D, la descripción '5 dormitorios' (manda la descripción)"),
    "R13": dict(beds=3, dist=410, pets=NONE_, parking="propio", uf=7300, loc="Providencia", expect=[B, M],
                note="'Cuenta con estacionamiento y bodega'; 'actualmente arrendado' no publica monto"),
    "R14": dict(beds=5, dist=923, pets=NONE_, parking="ninguno", uf=15500, loc="Ñuñoa", expect=[B, M, E],
                note="CONFLICTO: portal 4D; texto: 1 dormitorio en el primer piso + 4 en el segundo = 5"),
    "R15": dict(beds=3, dist=4646, pets=NONE_, parking="propio", uf=6100, loc="La Florida", expect=[B, M, D],
                note="la mansarda de 'uso flexible' no es dormitorio"),
    "R16": dict(beds=2, dist=443, pets=NONE_, parking="calle", uf=4890, loc="Santiago", expect=[B, M, E],
                note="portal dice 3D y 'casa'; el texto: departamento, 'dos dormitorios... mas pieza y baño "
                     "de servicios' (servicio no cuenta); 'opción de estacionamiento en calle' = calle"),
}


def build(check_only: bool = False) -> int:
    muestra = json.loads((REAL_DIR / "fuente" / "muestra.json").read_text(encoding="utf-8"))["avisos"]
    if len(muestra) != len(ANNOTATION):
        sys.exit(f"muestra con {len(muestra)} avisos y anotación con {len(ANNOTATION)}")
    props = []
    for i, aviso in enumerate(muestra, 1):
        rid = f"R{i:02d}"
        a = ANNOTATION[rid]
        truth = Truth(bedrooms=a["beds"], distance_transport_m=a["dist"], pets=a["pets"], parking=a["parking"],
                      price_uf=a.get("uf"), price_clp=a.get("clp"), rent_monthly_clp=None, location=a["loc"])
        props.append({"id": f"REAL-{i:02d}", "text": aviso["ficha"], "truth": asdict(truth),
                      "fuente": aviso["url"], "portal": aviso["source"], "note": a.get("note", ""),
                      "expect": sorted(a["expect"])})
    cases = []
    for k in range(4):   # un aviso de cada portal por caso
        members = [props[k + 4 * j] for j in range(4)]
        cases.append({"id": f"real_{k + 1:03d}", "uf_value": UF, "hard_constraints": BUYER,
                      "soft_constraints": {"ubicaciones_preferidas": PREFS},
                      "properties": members})
    bad = []
    for c in cases:
        case = Case.from_dict(c)
        for p, raw in zip(case.properties, c["properties"]):
            got = sorted(evaluate_property(p, case).failed_constraints)
            if got != raw["expect"]:
                bad.append(f"{p.id}: rules.py={got} anotado={raw['expect']}")
    if bad:
        print("La anotación no coincide con rules.py:\n  " + "\n  ".join(bad))
        return 1
    n_ok = sum(1 for c in cases for p in c["properties"] if not p["expect"])
    print(f"OK: {len(cases)} casos, {len(props)} propiedades, {n_ok} aprobadas. Anotación == rules.py.")
    fallo = build_fallo()
    if fallo is None:
        return 1
    if not check_only:
        for c in cases:
            (REAL_DIR / f"{c['id']}.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
        FALLO_DIR.mkdir(parents=True, exist_ok=True)
        (FALLO_DIR / "fallo_001.json").write_text(json.dumps(fallo, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


# ------------------------------------------------------- caso de fallo (g3) ----
# NO es parte del sorteo: es el aviso real con el que se descubrió la aprobación falsa de
# g3 (ver docs/scout.md). Va en su propio split, data/cases/real_fallo/, para no mezclar
# un caso elegido con las cifras del set aleatorio. Mismo comprador de la E1: el aviso
# cuesta exactamente el tope ($150.000.000), así que el veredicto depende de leer bien
# mascotas y estacionamiento.
FALLO_DIR = ROOT / "data" / "cases" / "real_fallo"


def build_fallo():
    src = json.loads((REAL_DIR / "fuente" / "fallo_g3.json").read_text(encoding="utf-8"))
    truth = Truth(bedrooms=3, distance_transport_m=112, pets=NONE_, parking="ninguno",
                  price_clp=150_000_000, location="Providencia")
    c = {"id": "fallo_001", "uf_value": UF, "hard_constraints": BUYER,
         "soft_constraints": {"ubicaciones_preferidas": PREFS},
         "properties": [{"id": "REAL-F1", "text": src["ficha"], "truth": asdict(truth), "fuente": src["url"],
                         "note": "'Se aceptan ofertas' no es política de mascotas; 'opción de arriendo de "
                                 "estacionamientos' = no incluido. g3 aprobaba este aviso.",
                         "expect": [E, M]}]}
    case = Case.from_dict(c)
    got = sorted(evaluate_property(case.properties[0], case).failed_constraints)
    if got != sorted([E, M]):
        print(f"fallo_001: rules.py={got}")
        return None
    return c


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    sys.exit(build(ap.parse_args().check))
