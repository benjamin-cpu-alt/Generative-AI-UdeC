"""Set OOD (out-of-distribution): 12 casos con avisos ESCRITOS A MANO.

Por qué existe: `generate.py` produce el texto con plantillas fijas, así que un parser
puede acertar por memorizar la plantilla en vez de leer el aviso. Este set no usa ninguna
plantilla del generador: son avisos redactados imitando cómo escriben de verdad los
corredores chilenos (fichas de portal, WhatsApp sin tildes, MAYÚSCULAS, cifras en palabras,
"millones", "600k", "620 lucas", UF con decimales y rangos, gastos comunes compitiendo con
el precio, "2D+servicio", "3D+E", distancias solo en minutos, estacionamiento "opcional").

Es el control de la afirmación "el LLM aporta percepción, no el regex": si la solución
rinde aquí parecido a como rinde en `test/`, la percepción es real; si se derrumba, lo que
había era ajuste a las plantillas. Cualquiera de los dos resultados se reporta.

Cada propiedad lleva:
  - `text`   el aviso, escrito a mano (lo único que ve el modelo);
  - `truth`  los campos estructurados que solo ve el juez;
  - `note`   qué dificultad concreta introduce (para revisión humana; el código la ignora);
  - `expect` las restricciones que DEBEN fallar. El script aborta si `rules.py` no coincide:
             es la misma auto-verificación que usa el generador, aplicada a anotación manual.

Uso:
  python3 scripts/build_ood.py            # escribe data/cases/ood/*.json
  python3 scripts/build_ood.py --check    # solo verifica, no escribe
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from matcher.rules import evaluate_property                      # noqa: E402
from matcher.schema import (Case, HardConstraints, PetsPolicy,   # noqa: E402
                            Property, SoftConstraints, Truth)

OOD_DIR = ROOT / "data" / "cases" / "ood"

# --------------------------------------------------------------- atajos ----

ANY = PetsPolicy(explicit=True, allowed=True, species=[], max_kg=None)
NONE_ = PetsPolicy(explicit=False, allowed=False, species=[], max_kg=None)   # no se menciona
NO = PetsPolicy(explicit=True, allowed=False, species=[], max_kg=None)       # no se aceptan


def kg(n: float) -> PetsPolicy:
    return PetsPolicy(explicit=True, allowed=True, species=[], max_kg=n)


def only(species: str, max_kg: Optional[float] = None) -> PetsPolicy:
    return PetsPolicy(explicit=True, allowed=True, species=[species], max_kg=max_kg)


def hc(presupuesto: int, especie: str, mascota_kg: float, distancia: int,
       dormitorios: int) -> HardConstraints:
    return HardConstraints(presupuesto_max_clp=presupuesto, mascota_especie=especie,
                           mascota_kg=mascota_kg, distancia_max_transporte_m=distancia,
                           dormitorios_min=dormitorios, estacionamiento_requerido=True)


def P(pid: str, text: str, *, note: str, expect: List[str], loc: str, beds: int,
      dist: Optional[int], pets: PetsPolicy, parking: str, uf: Optional[float] = None,
      clp: Optional[int] = None, rent: Optional[int] = None) -> Dict:
    return {
        "id": pid, "text": " ".join(text.split()), "note": note, "expect": sorted(expect),
        "truth": Truth(bedrooms=beds, distance_transport_m=dist, pets=pets, parking=parking,
                       price_uf=uf, price_clp=clp, rent_monthly_clp=rent, location=loc),
    }


def case(cid: str, uf_value: float, hard: HardConstraints, prefs: List[str],
         style: str, props: List[Dict]) -> Dict:
    return {"id": cid, "uf_value": uf_value, "hard_constraints": hard,
            "soft_constraints": SoftConstraints(ubicaciones_preferidas=prefs),
            "style": style, "properties": props}


# ------------------------------------------------------------- los casos ----

CASES: List[Dict] = [

    # ---------------------------------------------------------------- 001 --
    case("ood_001", 39_100, hc(200_000_000, "perro", 12, 800, 2), ["Providencia", "Ñuñoa"],
         "Ficha de portal inmobiliario: prosa formal, unidades escritas completas.", [
        P("OOD-101", """Departamento en Providencia, 3 dormitorios y 2 baños, 92 m². Valor de venta:
           UF 4.900. Ubicado a 450 metros de Metro Salvador. El reglamento de copropiedad
           permite mascotas de hasta 15 kilos. Incluye un estacionamiento en subterráneo y
           bodega. Renta estimada de mercado: $1.100.000 mensuales.""",
          note="cumple todo; 'metros'/'kilos' en palabras completas",
          expect=[], loc="Providencia", beds=3, dist=450, pets=kg(15), parking="propio",
          uf=4900, rent=1_100_000),
        P("OOD-102", """Departamento en Ñuñoa, 1 dormitorio más pieza de servicio con baño, 68 m².
           Precio: UF 3.700. A 300 metros de Metro Chile España. Se aceptan mascotas sin
           restricción. Estacionamiento asignado.""",
          note="'1 dormitorio más pieza de servicio': la pieza de servicio no es dormitorio",
          expect=["dormitorios"], loc="Ñuñoa", beds=1, dist=300, pets=ANY, parking="asignado",
          uf=3700),
        P("OOD-103", """Depto 3D/2B de 105 m² en Las Condes, excelente ubicación. Valor: $210.000.000.
           A 600 metros de Metro Manquehue. Acepta mascotas. Dos estacionamientos.""",
          note="sobre presupuesto en CLP",
          expect=["presupuesto"], loc="Las Condes", beds=3, dist=600, pets=ANY,
          parking="propio", clp=210_000_000),
        P("OOD-104", """Amplio departamento en Providencia, 2 dormitorios, 78 m². UF 4.100. A 12 minutos
           caminando del metro. Pet friendly. Incluye estacionamiento.""",
          note="distancia SOLO en minutos: no verificable -> debe rechazarse",
          expect=["distancia_transporte"], loc="Providencia", beds=2, dist=None, pets=ANY,
          parking="propio", uf=4100),
        P("OOD-105", """Casa de 3 dormitorios, 110 m². Precio: $185.000.000. A 700 metros de
           Metro Ñuñoa. El condominio no acepta mascotas. Estacionamiento propio para dos
           autos.""",
          note="negativa de mascotas en prosa ('no acepta')",
          expect=["mascotas"], loc="Ñuñoa", beds=3, dist=700, pets=NO, parking="propio",
          clp=185_000_000),
        P("OOD-106", """Departamento 2D/1B de 70 m² en Providencia. Valor: UF 4.500. A 250 metros del Metro
           Los Leones. Mascotas permitidas hasta 20 kilos. Cuenta con estacionamiento de
           visitas para el edificio.""",
          note="estacionamiento de visitas redactado como si fuera una ventaja",
          expect=["estacionamiento"], loc="Providencia", beds=2, dist=250, pets=kg(20),
          parking="visitas", uf=4500),
        P("OOD-107", """Depto en Macul, 2 dormitorios, 65 m². Precio: UF 3.900. A 550 metros de Metro
           Los Presidentes. Acepta perros y gatos, sin límite de peso. Estacionamiento
           propio. Se arrienda actualmente en $1.000.000.""",
          note="cumple pero NO está en comuna preferida y tiene mayor ROI: la preferencia "
               "debe ganarle al ROI en el ranking",
          expect=[], loc="Macul", beds=2, dist=550, pets=ANY, parking="propio",
          uf=3900, rent=1_000_000),
    ]),

    # ---------------------------------------------------------------- 002 --
    case("ood_002", 38_750, hc(130_000_000, "gato", 5, 1000, 2), ["La Florida"],
         "WhatsApp de corredor: minúsculas, sin tildes, abreviaturas, 'lucas'.", [
        P("OOD-201", """hola! te mando el depto de la florida: 2d 1b, 58 mts. piden 3.200 uf.
           esta a 400 mts del metro vicuña mackenna. aceptan gatos hasta 8 kilos. tiene 1
           estacionamiento asignado. arriendo referencial 620 lucas""",
          note="'620 lucas' = $620.000 (jerga chilena); minúsculas y sin tildes",
          expect=[], loc="La Florida", beds=2, dist=400, pets=kg(8), parking="asignado",
          uf=3200, rent=620_000),
        P("OOD-202", """el otro tambien en la florida: 1d+1b, 45 mts, 2.900 uf. a 300 mts del metro. aceptan
           mascotas chicas. sin estacionamiento, pero hay harto espacio en la calle""",
          note="dos fallos; 'sin estacionamiento' seguido de 'espacio en la calle'",
          expect=["dormitorios", "estacionamiento"], loc="La Florida", beds=1, dist=300,
          pets=ANY, parking="ninguno", uf=2900),
        P("OOD-203", """casa 3d 2b en puente alto, 95 mts, 118 millones. a 1,4 km del metro
           plaza puente alto. no aceptan mascotas por reglamento. 2 estacionamientos
           propios""",
          note="'118 millones' sin signo $; dos fallos",
          expect=["distancia_transporte", "mascotas"], loc="Puente Alto", beds=3, dist=1400,
          pets=NO, parking="propio", clp=118_000_000),
        P("OOD-204", """depto 2d 1b 62 mts en la florida, piden 135 millones. a 600 mts del metro. pet
           friendly total. estacionamiento subterraneo incluido""",
          note="'135 millones' sobre presupuesto",
          expect=["presupuesto"], loc="La Florida", beds=2, dist=600, pets=ANY,
          parking="propio", clp=135_000_000),
        P("OOD-205", """2d/2b 70 mts en macul, 3.300 uf. a 850 mts del metro. aceptan solo
           perros. estacionamiento asignado. renta 700 lucas""",
          note="'solo perros' y el comprador tiene gato",
          expect=["mascotas"], loc="Macul", beds=2, dist=850, pets=only("perro"),
          parking="asignado", uf=3300, rent=700_000),
        P("OOD-206", """depto 2d 1b en la florida, 3.100 uf, a 700 mts del metro, aceptan gatos y perros
           hasta 10 kg, tiene estacionamiento propio. arriendo 650.000""",
          note="cumple; mismo grupo de preferencia que OOD-201, mayor ROI -> va primero",
          expect=[], loc="La Florida", beds=2, dist=700, pets=kg(10), parking="propio",
          uf=3100, rent=650_000),
    ]),

    # ---------------------------------------------------------------- 003 --
    case("ood_003", 39_300, hc(160_000_000, "perro", 25, 600, 3), ["San Miguel", "Macul"],
         "Cifras escritas en palabras y en 'millones'.", [
        P("OOD-301", """Casa en San Miguel, tres dormitorios y dos baños, 120 m². Precio: ciento cuarenta
           y cinco millones de pesos. A quinientos metros del Metro El Llano. Se aceptan
           perros de cualquier tamaño. Dos estacionamientos propios. Arriendo estimado:
           novecientos mil pesos.""",
          note="TODAS las cifras en palabras: ningún número que copiar. Probablemente "
               "imposible de anclar -> rechazo por no verificable (falso negativo seguro)",
          expect=[], loc="San Miguel", beds=3, dist=500, pets=only("perro"),
          parking="propio", clp=145_000_000, rent=900_000),
        P("OOD-302", """Depto 3D/2B, 88 m², Macul. Valor: $158 millones. A 400 m del metro. Acepta
           mascotas hasta 30 kilos. Estacionamiento propio.""",
          note="'$158 millones': cifra abreviada, sin arriendo (roi null)",
          expect=[], loc="Macul", beds=3, dist=400, pets=kg(30), parking="propio",
          clp=158_000_000),
        P("OOD-303", """Casa 4D/2B de 130 m² en San Miguel. $172 millones. A 550 metros del metro. Pet
           friendly sin restricciones. Estacionamiento para 3 autos.""",
          note="'$172 millones' sobre presupuesto",
          expect=["presupuesto"], loc="San Miguel", beds=4, dist=550, pets=ANY,
          parking="propio", clp=172_000_000),
        P("OOD-304", """Depto en La Cisterna, 3 dormitorios, 80 m². UF 3.800. A 1,2 km de la estación.
           Acepta mascotas hasta 20 kilos. Estacionamiento asignado.""",
          note="dos fallos: distancia y peso de mascota",
          expect=["distancia_transporte", "mascotas"], loc="La Cisterna", beds=3, dist=1200,
          pets=kg(20), parking="asignado", uf=3800),
        P("OOD-305", """Departamento en Macul, dos dormitorios, 64 m². Precio: UF 3.500. A 300
           metros del metro. Perros bienvenidos. Estacionamiento propio.""",
          note="'dos dormitorios' en palabras, bajo el mínimo de 3",
          expect=["dormitorios"], loc="Macul", beds=2, dist=300, pets=only("perro"),
          parking="propio", uf=3500),
        P("OOD-306", """Casa 3D/1B, 105 m². Precio: UF 3.600. A 480 metros del Metro San
           Miguel. No se especifica política de mascotas. Estacionamiento propio.""",
          note="política de mascotas ausente y declarada como ausente",
          expect=["mascotas"], loc="San Miguel", beds=3, dist=480, pets=NONE_,
          parking="propio", uf=3600),
    ]),

    # ---------------------------------------------------------------- 004 --
    case("ood_004", 38_900, hc(190_000_000, "gato", 6, 900, 2), ["Recoleta"],
         "Distancias en minutos, en micro, o en metros junto a minutos.", [
        P("OOD-401", """Depto 2D/1B, 60 m², Recoleta. UF 4.300. A pasos del Metro Cerro Blanco, unos 5
           minutos caminando. Se aceptan gatos. Estacionamiento propio. Arriendo:
           $720.000.""",
          note="'a pasos' + minutos, sin metros -> no verificable",
          expect=["distancia_transporte"], loc="Recoleta", beds=2, dist=None,
          pets=only("gato"), parking="propio", uf=4300, rent=720_000),
        P("OOD-402", """Depto 2D/2B, 72 m², Recoleta. UF 4.600. A 350 metros del Metro Patronato,
           aproximadamente 4 minutos a pie. Mascotas permitidas hasta 10 kilos.
           Estacionamiento asignado. Arriendo: $850.000.""",
          note="metros Y minutos en la misma frase: debe usar los metros",
          expect=[], loc="Recoleta", beds=2, dist=350, pets=kg(10), parking="asignado",
          uf=4600, rent=850_000),
        P("OOD-403", """Depto 3D/1B, 85 m², Independencia. $165.000.000. Muy bien conectado, a 15 minutos
           del metro en micro. Acepta mascotas. Estacionamiento propio.""",
          note="'15 minutos en micro': ni siquiera es caminando",
          expect=["distancia_transporte"], loc="Independencia", beds=3, dist=None, pets=ANY,
          parking="propio", clp=165_000_000),
        P("OOD-404", """Depto 2D/1B, 58 m², Recoleta. UF 4.900 (negociable). A 800 m del metro. Pet
           friendly, sin límite de peso ni especie. Estacionamiento propio. Arriendo:
           $800.000.""",
          note="near miss: UF 4.900 = $190.610.000, sobre el tope por $610.000",
          expect=["presupuesto"], loc="Recoleta", beds=2, dist=800, pets=ANY,
          parking="propio", uf=4900, rent=800_000),
        P("OOD-405", """Depto 2D/1B, 55 m², Recoleta. UF 4.200. A 500 metros del metro y a 200 metros
           de paradero de Transantiago troncal. Solo se aceptan perros. Estacionamiento
           propio.""",
          note="dos distancias válidas; falla por especie (comprador tiene gato)",
          expect=["mascotas"], loc="Recoleta", beds=2, dist=200, pets=only("perro"),
          parking="propio", uf=4200),
        P("OOD-406", """Casa 3D/2B, 98 m², Conchalí. $150.000.000. A 1.100 metros del metro, pero a 400
           metros de paradero troncal. Acepta gatos y perros. Estacionamiento propio.
           Arriendo: $900.000.""",
          note="cumple por el paradero; NO preferida y con mayor ROI que OOD-402",
          expect=[], loc="Conchalí", beds=3, dist=400, pets=ANY, parking="propio",
          clp=150_000_000, rent=900_000),
    ]),

    # ---------------------------------------------------------------- 005 --
    case("ood_005", 39_000, hc(175_000_000, "perro", 8, 1000, 3), ["Las Condes", "Vitacura"],
         "Tipologías chilenas: '2D+servicio', '3D+E'.", [
        P("OOD-501", """Depto 2D+servicio, 2B, 95 m², Las Condes. UF 4.400. A 600 m de Metro Escuela
           Militar. Acepta mascotas pequeñas hasta 10 kg. 1 estacionamiento. Arriendo:
           $950.000.""",
          note="'2D+servicio' = 2 dormitorios, bajo el mínimo de 3",
          expect=["dormitorios"], loc="Las Condes", beds=2, dist=600, pets=kg(10),
          parking="propio", uf=4400, rent=950_000),
        P("OOD-502", """Departamento en Vitacura, 3D+E (escritorio), 2B, 110 m². UF 4.450. A 750 metros
           del metro. Pet friendly hasta 15 kilos. Estacionamiento y bodega. Arriendo:
           $1.050.000.""",
          note="'3D+E' = 3 dormitorios + escritorio: el escritorio no suma",
          expect=[], loc="Vitacura", beds=3, dist=750, pets=kg(15), parking="propio",
          uf=4450, rent=1_050_000),
        P("OOD-503", """Casa 4D/3B + quincho, 180 m², Las Condes. $240.000.000. A 400 m del metro. Acepta
           perros grandes. Tres estacionamientos.""",
          note="muy sobre presupuesto",
          expect=["presupuesto"], loc="Las Condes", beds=4, dist=400, pets=only("perro"),
          parking="propio", clp=240_000_000),
        P("OOD-504", """Depto 3D/2B, 90 m², Ñuñoa. UF 4.300. A 500 metros del metro. Se aceptan
           mascotas hasta 5 kilos. Estacionamiento propio.""",
          note="límite de peso bajo el del comprador (8 kg)",
          expect=["mascotas"], loc="Ñuñoa", beds=3, dist=500, pets=kg(5), parking="propio",
          uf=4300),
        P("OOD-505", """Depto 3D/2B, 100 m², Vitacura. UF 4.480. A 850 m del metro. Acepta mascotas sin
           restricción. Estacionamiento de cortesía para visitas.""",
          note="'estacionamiento de cortesía para visitas'; precio justo bajo el tope",
          expect=["estacionamiento"], loc="Vitacura", beds=3, dist=850, pets=ANY,
          parking="visitas", uf=4480),
        P("OOD-506", """Depto 3D/2B, 98 m², Las Condes. UF 4.490. A 900 metros del metro. Acepta perros y
           gatos. 1 estacionamiento asignado. Arriendo: $1.000.000.""",
          note="near miss extremo: UF 4.490 = $175.110.000, sobre el tope por $110.000",
          expect=["presupuesto"], loc="Las Condes", beds=3, dist=900, pets=ANY,
          parking="asignado", uf=4490, rent=1_000_000),
    ]),

    # ---------------------------------------------------------------- 006 --
    case("ood_006", 38_600, hc(145_000_000, "gato", 4, 700, 2), ["Santiago Centro"],
         "Gastos comunes compitiendo con el precio de venta.", [
        P("OOD-601", """Depto 2D/1B, 55 m², Santiago Centro. Precio: UF 3.600. Gastos comunes: $95.000. A 200
           metros del Metro Universidad de Chile. Acepta gatos y perros chicos.
           Estacionamiento asignado. Arriendo: $620.000.""",
          note="tres cifras en pesos y UF en el mismo aviso: precio, GC y arriendo",
          expect=[], loc="Santiago Centro", beds=2, dist=200, pets=ANY, parking="asignado",
          uf=3600, rent=620_000),
        P("OOD-602", """Depto 1D/1B, 40 m², Santiago Centro. Valor UF 3.100, gastos comunes aproximados
           $70.000 mensuales. A 150 m del metro. Pet friendly. Estacionamiento propio.""",
          note="GC 'mensuales' puede confundirse con arriendo",
          expect=["dormitorios"], loc="Santiago Centro", beds=1, dist=150, pets=ANY,
          parking="propio", uf=3100),
        P("OOD-603", """Depto 2D/2B, 62 m², Estación Central. $142.000.000. GC $130.000. A 300 metros del
           metro. No acepta mascotas. Estacionamiento propio.""",
          note="'GC' abreviado; precio en CLP bajo el tope",
          expect=["mascotas"], loc="Estación Central", beds=2, dist=300, pets=NO,
          parking="propio", clp=142_000_000),
        P("OOD-604", """Depto 2D/1B, 50 m², Santiago Centro. UF 3.900. A 1,1 km del metro. Acepta mascotas
           hasta 8 kilos. Estacionamiento propio. Arriendo: $600.000.""",
          note="dos fallos: presupuesto y distancia",
          expect=["distancia_transporte", "presupuesto"], loc="Santiago Centro", beds=2,
          dist=1100, pets=kg(8), parking="propio", uf=3900, rent=600_000),
        P("OOD-605", """Depto 2D/1B, 53 m², Santiago Centro. UF 3.700. Gastos comunes $88.000. A 400 m del
           metro. Se aceptan mascotas hasta 3 kilos. Estacionamiento propio.""",
          note="límite 3 kg contra gato de 4 kg",
          expect=["mascotas"], loc="Santiago Centro", beds=2, dist=400, pets=kg(3),
          parking="propio", uf=3700),
    ]),

    # ---------------------------------------------------------------- 007 --
    case("ood_007", 39_200, hc(170_000_000, "perro", 20, 800, 2), ["Peñalolén", "La Reina"],
         "Política de mascotas con fraseos poco habituales.", [
        P("OOD-701", """Depto 2D/2B, 75 m², La Reina. UF 4.200. A 600 m de paradero troncal. Se admite
           una mascota por departamento, sin restricción de tamaño. Estacionamiento propio.
           Arriendo: $820.000.""",
          note="'una mascota por departamento' = permitidas, sin límite de peso ni especie",
          expect=[], loc="La Reina", beds=2, dist=600, pets=ANY, parking="propio",
          uf=4200, rent=820_000),
        P("OOD-702", """Casa 3D/2B, 100 m², Peñalolén. $160.000.000. A 700 metros del metro. Se aceptan
           perros hasta veinte kilos. Estacionamiento propio. Arriendo: $900.000.""",
          note="límite en palabras ('veinte kilos') EXACTAMENTE igual al peso del perro: "
               "20 <= 20 cumple",
          expect=[], loc="Peñalolén", beds=3, dist=700, pets=only("perro", 20),
          parking="propio", clp=160_000_000, rent=900_000),
        P("OOD-703", """Depto 2D/1B, 68 m², La Reina. UF 4.100. A 500 m del metro. Prohibido mantener
           perros; gatos sí están permitidos. Estacionamiento propio.""",
          note="negación invertida: prohíbe primero, permite después",
          expect=["mascotas"], loc="La Reina", beds=2, dist=500, pets=only("gato"),
          parking="propio", uf=4100),
        P("OOD-704", """Depto 2D/1B, 66 m², Peñalolén. UF 4.000. A 450 metros del metro. Solo mascotas
           de raza pequeña, máximo 8 kg. Estacionamiento propio.""",
          note="adjetivo cualitativo + límite numérico en la misma frase",
          expect=["mascotas"], loc="Peñalolén", beds=2, dist=450, pets=kg(8),
          parking="propio", uf=4000),
        P("OOD-705", """Depto 2D/1B, 60 m², Macul. UF 3.900. A 400 m del metro. Estacionamiento
           propio. Excelente conectividad.""",
          note="el aviso simplemente no habla de mascotas",
          expect=["mascotas"], loc="Macul", beds=2, dist=400, pets=NONE_, parking="propio",
          uf=3900),
        P("OOD-706", """Depto 2D/2B, 80 m², La Reina. UF 4.350. A 300 metros del metro. Aceptamos
           mascotas, incluidos perros grandes. Estacionamiento de visitas disponible las 24
           horas.""",
          note="mascotas OK pero el estacionamiento es de visitas",
          expect=["estacionamiento"], loc="La Reina", beds=2, dist=300, pets=ANY,
          parking="visitas", uf=4300),
    ]),

    # ---------------------------------------------------------------- 008 --
    case("ood_008", 38_400, hc(120_000_000, "gato", 7, 1200, 2), ["Quinta Normal"],
         "MAYÚSCULAS, erratas y abreviaturas de portal barato.", [
        P("OOD-801", """DEPTO 2D/1B 55M2 EN QUINTA NORMAL. PRECIO UF 3.000. A 600 MTS METRO
           CUMBRE. ACEPTAN MASCOTAS HASTA 10 KILOS. INCLUYE ESTACIONAMIENTO. ARRIENDO
           $560.000""",
          note="todo en mayúsculas",
          expect=[], loc="Quinta Normal", beds=2, dist=600, pets=kg(10), parking="propio",
          uf=3000, rent=560_000),
        P("OOD-802", """depto 2d/1b 50m2 en quinta normal, precio 3.050 uf. a 900 mts del metro. NO SE ACEPTAN
           MASCOTAS. estacionamiento propio""",
          note="negativa en mayúsculas dentro de texto en minúsculas",
          expect=["mascotas"], loc="Quinta Normal", beds=2, dist=900, pets=NO,
          parking="propio", uf=3050),
        P("OOD-803", """Casa 3D/1B 85m2 en Renca. Valor $118.000.000. A 1.500 mts del metro mas
           cercano. Acepta mascotas. Estacionamento propio.""",
          note="errata 'Estacionamento' (sin la i); distancia excedida",
          expect=["distancia_transporte"], loc="Renca", beds=3, dist=1500, pets=ANY,
          parking="propio", clp=118_000_000),
        P("OOD-804", """Dpto 2D/1B, 52m2, Quinta Normal, UF 3.250. A 1.000 mts del metro. Se acepta 1
           mascota chica hasta 5 kilos. Estacionamiento asignado.""",
          note="dos fallos; 'Dpto' abreviado",
          expect=["mascotas", "presupuesto"], loc="Quinta Normal", beds=2, dist=1000,
          pets=kg(5), parking="asignado", uf=3250),
        P("OOD-805", """DEPTO 2D 1B 58M2 EN QUINTA NORMAL, UF 3.100. A 400 MTS DEL METRO. PET FRIENDLY SIN
           RESTRICCIONES. ESTACIONAMIENTO EN LA CALLE, SIN PROBLEMAS PARA APARCAR.""",
          note="estacionamiento en la calle, en mayúsculas",
          expect=["estacionamiento"], loc="Quinta Normal", beds=2, dist=400, pets=ANY,
          parking="calle", uf=3100),
    ]),

    # ---------------------------------------------------------------- 009 --
    case("ood_009", 39_050, hc(155_000_000, "perro", 10, 900, 2), ["San Joaquín"],
         "Estacionamiento redactado de forma ambigua.", [
        P("OOD-901", """Depto 2D/1B, 58 m², San Joaquín. UF 3.500. A 500 m del Metro Pedrero. Acepta
           mascotas hasta 12 kilos. Se vende con estacionamiento y bodega incluidos en el
           precio. Arriendo: $640.000.""",
          note="'se vende con estacionamiento incluido' = propio",
          expect=[], loc="San Joaquín", beds=2, dist=500, pets=kg(12), parking="propio",
          uf=3500, rent=640_000),
        P("OOD-902", """Depto 2D/1B, 60 m², San Joaquín. UF 3.600. A 450 metros del metro. Pet friendly.
           Estacionamiento opcional, se arrienda aparte a $50.000 mensuales.""",
          note="'estacionamiento opcional, se arrienda aparte': la unidad NO lo incluye",
          expect=["estacionamiento"], loc="San Joaquín", beds=2, dist=450, pets=ANY,
          parking="ninguno", uf=3600),
        P("OOD-903", """Depto 2D/2B, 70 m², Macul. UF 3.800. A 600 m del metro. Acepta perros.
           Cuenta con estacionamientos de visita y acceso controlado.""",
          note="'estacionamientos de visita' en plural",
          expect=["estacionamiento"], loc="Macul", beds=2, dist=600, pets=only("perro"),
          parking="visitas", uf=3800),
        P("OOD-904", """Depto 2D/1B, 55 m², San Joaquín. UF 3.450. A 700 metros del metro. Mascotas
           permitidas. Derecho a uso de un estacionamiento asignado a la unidad. Arriendo:
           $610.000.""",
          note="'derecho a uso de un estacionamiento asignado a la unidad' = asignado",
          expect=[], loc="San Joaquín", beds=2, dist=700, pets=ANY, parking="asignado",
          uf=3450, rent=610_000),
        P("OOD-905", """Depto 3D/1B, 72 m², San Joaquín. UF 3.950. A 850 m del metro. Acepta mascotas
           hasta 6 kilos. Estacionamiento propio.""",
          note="límite 6 kg contra perro de 10 kg",
          expect=["mascotas"], loc="San Joaquín", beds=3, dist=850, pets=kg(6),
          parking="propio", uf=3950),
        P("OOD-906", """Casa 3D/2B, 95 m², La Granja. $160.000.000. A 800 metros de paradero troncal.
           Acepta perros grandes. Dos estacionamientos propios.""",
          note="sobre presupuesto",
          expect=["presupuesto"], loc="La Granja", beds=3, dist=800, pets=only("perro"),
          parking="propio", clp=160_000_000),
    ]),

    # ---------------------------------------------------------------- 010 --
    case("ood_010", 38_800, hc(180_000_000, "gato", 5, 1000, 3), ["Maipú"],
         "UF con 'aproximado', con decimales y en rango.", [
        P("OOD-1001", """Casa 3D/2B, 105 m², Maipú. Valor aproximado: UF 4.500. A 800 m de Metro Del
           Sol. Acepta gatos y perros. Dos estacionamientos propios. Arriendo: $880.000.""",
          note="'valor aproximado' antes de la cifra",
          expect=[], loc="Maipú", beds=3, dist=800, pets=ANY, parking="propio",
          uf=4500, rent=880_000),
        P("OOD-1002", """Depto 3D/1B, 78 m², Maipú. UF 4.250,5. A 600 metros del metro. Pet
           friendly. Estacionamiento asignado.""",
          note="UF con decimal en formato chileno (coma); sin arriendo -> roi null",
          expect=[], loc="Maipú", beds=3, dist=600, pets=ANY, parking="asignado",
          uf=4250.5),
        P("OOD-1003", """Casa 4D/2B, 120 m², Maipú. Entre UF 4.900 y UF 5.100 según forma de pago.
           A 900 m del metro. Acepta mascotas. Estacionamiento propio.""",
          note="precio en RANGO; ambos extremos superan el tope, así que el veredicto no "
               "depende de cuál se tome",
          expect=["presupuesto"], loc="Maipú", beds=4, dist=900, pets=ANY, parking="propio",
          uf=4900),
        P("OOD-1004", """Depto 3D/2B, 82 m², Cerrillos. $170.000.000. A 1,3 km del metro. Acepta gatos
           hasta 4 kilos. Estacionamiento propio.""",
          note="dos fallos: distancia y peso",
          expect=["distancia_transporte", "mascotas"], loc="Cerrillos", beds=3, dist=1300,
          pets=only("gato", 4), parking="propio", clp=170_000_000),
        P("OOD-1005", """Depto 2D/1B, 62 m², Maipú. UF 3.900. A 400 metros del metro. Acepta
           mascotas. Estacionamiento propio.""",
          note="bajo el mínimo de dormitorios",
          expect=["dormitorios"], loc="Maipú", beds=2, dist=400, pets=ANY, parking="propio",
          uf=3900),
        P("OOD-1006", """Casa 3D/2B, 98 m², Maipú. UF 4.640. A 700 m del metro. Acepta mascotas sin
           restricciones. Estacionamiento propio. Arriendo: $920.000.""",
          note="near miss máximo: UF 4.640 = $180.032.000, sobre el tope por $32.000",
          expect=["presupuesto"], loc="Maipú", beds=3, dist=700, pets=ANY, parking="propio",
          uf=4640, rent=920_000),
    ]),

    # ---------------------------------------------------------------- 011 --
    case("ood_011", 39_400, hc(135_000_000, "perro", 15, 800, 2), ["Independencia"],
         "Avisos telegráficos: frases de dos palabras, '600k'.", [
        P("OOD-1101", """2D 1B. 55m2. Independencia. UF 3.300. Metro a 350m. Mascotas OK hasta 20kg. Est.
           propio. Arriendo 600k.""",
          note="'Est. propio' abreviado; '600k' = $600.000",
          expect=[], loc="Independencia", beds=2, dist=350, pets=kg(20), parking="propio",
          uf=3300, rent=600_000),
        P("OOD-1102", """1D 1B. 42m2. Independencia. UF 2.900. Metro 200m. Mascotas OK. Est. asignado.""",
          note="telegráfico, un dormitorio",
          expect=["dormitorios"], loc="Independencia", beds=1, dist=200, pets=ANY,
          parking="asignado", uf=2900),
        P("OOD-1103", """3D 2B. 78m2. Recoleta. UF 3.400. Metro 1km. Sin mascotas. Est. propio.""",
          note="'Metro 1km' sin preposición; dos fallos",
          expect=["distancia_transporte", "mascotas"], loc="Recoleta", beds=3, dist=1000,
          pets=NO, parking="propio", uf=3400),
        P("OOD-1104", """2D 1B. 58m2. Independencia. UF 3.380. Metro 400m. Solo gatos. Est. propio.""",
          note="'Solo gatos' en dos palabras; comprador tiene perro",
          expect=["mascotas"], loc="Independencia", beds=2, dist=400, pets=only("gato"),
          parking="propio", uf=3380),
        P("OOD-1105", """2D 2B. 60m2. Independencia. UF 3.420. Metro 600m. Perros y gatos OK. Est.
           visitas.""",
          note="'Est. visitas' abreviado; precio justo bajo el tope",
          expect=["estacionamiento"], loc="Independencia", beds=2, dist=600, pets=ANY,
          parking="visitas", uf=3420),
    ]),

    # ---------------------------------------------------------------- 012 --
    case("ood_012", 38_950, hc(165_000_000, "gato", 8, 700, 2), ["Providencia"],
         "Avisos largos, saturados de marketing (trampa de atención selectiva).", [
        P("OOD-1201", """¡OPORTUNIDAD ÚNICA EN EL CORAZÓN DE PROVIDENCIA! Espectacular
           departamento de 2 dormitorios y 2 baños, 78 m² totalmente remodelados, cocina
           americana, piso flotante y ventanas termopanel. El barrio más cotizado de
           Santiago, rodeado de cafés, parques y colegios de primer nivel. Valor: UF 4.180,
           ¡muy por debajo de la tasación comercial! A solo 350 metros del Metro Manuel
           Montt. Edificio pet friendly, se aceptan mascotas de hasta 12 kilos. Incluye
           estacionamiento subterráneo y bodega. Renta actual: $880.000 mensuales. ¡No la
           dejes pasar!""",
          note="cumple, pero el dato útil está enterrado en 90 palabras de marketing",
          expect=[], loc="Providencia", beds=2, dist=350, pets=kg(12), parking="propio",
          uf=4180, rent=880_000),
        P("OOD-1202", """¡IMPERDIBLE! Hermoso departamento en el mejor sector de Providencia,
           a pasos de todo. 2 dormitorios amplios, 1 baño completo, 65 m². Precio: UF 4.350,
           ¡bajo el presupuesto de cualquier comprador según nuestro tasador! A 300 metros
           del metro. Aceptamos mascotas sin restricción. Estacionamiento propio incluido en
           el precio.""",
          note="la trampa de la E1: '¡bajo el presupuesto!' sobre un precio que lo excede",
          expect=["presupuesto"], loc="Providencia", beds=2, dist=300, pets=ANY,
          parking="propio", uf=4350),
        P("OOD-1203", """EXCELENTE INVERSIÓN. Departamento de 2D/2B en Ñuñoa, 70 m²,
           orientación nororiente, excelente luminosidad natural durante todo el día. Ideal
           para inversionistas: alta demanda de arriendo en el sector. Valor: UF 4.100.
           Ubicado a 1,5 km del Metro Irarrázaval, pero con excelente conectividad y
           locomoción a pasos. Se aceptan mascotas pequeñas. Estacionamiento propio.""",
          note="'conectividad excelente' minimizando 1,5 km reales",
          expect=["distancia_transporte"], loc="Ñuñoa", beds=2, dist=1500, pets=ANY,
          parking="propio", uf=4100),
        P("OOD-1204", """¡ÚLTIMA UNIDAD DISPONIBLE! Moderno departamento de 2 dormitorios y 2
           baños en Providencia, 72 m². Terminaciones premium, conserjería 24/7, gimnasio y
           sala multiuso. Valor: UF 4.000. A 250 metros del Metro Salvador. El reglamento de
           copropiedad NO permite mascotas de ninguna especie. Incluye un estacionamiento
           asignado.""",
          note="negativa de mascotas enterrada entre amenidades",
          expect=["mascotas"], loc="Providencia", beds=2, dist=250, pets=NO,
          parking="asignado", uf=4000),
        P("OOD-1205", """OPORTUNIDAD DE INVERSIÓN EN PROVIDENCIA. Acogedor departamento de 1
           dormitorio más amplio living-comedor que puede habilitarse fácilmente como segundo
           dormitorio, 1 baño, 52 m². Valor: UF 3.900. A 400 metros del metro. Pet friendly,
           sin restricciones de tamaño. Estacionamiento propio. Renta estimada:
           $700.000.""",
          note="el dormitorio 'convertible' de la E1, redactado de otra forma",
          expect=["dormitorios"], loc="Providencia", beds=1, dist=400, pets=ANY,
          parking="propio", uf=3900, rent=700_000),
        P("OOD-1206", """¡GRAN OPORTUNIDAD! Departamento 2D/1B de 68 m² en Providencia,
           inmejorable ubicación. Valor: UF 4.150. A 500 metros del Metro Los Leones, en pleno corazón
           del barrio El Golf. Se aceptan gatos y perros de hasta 15 kilos. Cuenta con amplio
           estacionamiento para visitas y acceso vehicular controlado. Renta: $820.000.""",
          note="'amplio estacionamiento para visitas' suena a ventaja pero no cumple",
          expect=["estacionamiento"], loc="Providencia", beds=2, dist=500, pets=kg(15),
          parking="visitas", uf=4150),
    ]),
]


# ----------------------------------------------------------- verificación ----

def build(check_only: bool = False) -> int:
    errors: List[str] = []
    n_props = n_ok = 0
    for spec in CASES:
        props = [Property(id=p["id"], text=p["text"], truth=p["truth"]) for p in spec["properties"]]
        c = Case(id=spec["id"], uf_value=spec["uf_value"], hard_constraints=spec["hard_constraints"],
                 properties=props, soft_constraints=spec["soft_constraints"])
        for prop, p in zip(props, spec["properties"]):
            n_props += 1
            got = evaluate_property(prop, c)
            if sorted(got.failed_constraints) != p["expect"]:
                errors.append(f"{c.id} {prop.id}: anotado {p['expect']} pero rules.py dice "
                              f"{got.failed_constraints} (precio {got.price_clp:,} CLP)")
            else:
                n_ok += got.approved
        if check_only:
            continue
        OOD_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": c.id,
            "uf_value": c.uf_value,
            "style": spec["style"],
            "hard_constraints": asdict(c.hard_constraints),
            "soft_constraints": asdict(c.soft_constraints),
            "properties": [{"id": p["id"], "text": p["text"], "note": p["note"],
                            "truth": asdict(p["truth"])} for p in spec["properties"]],
        }
        (OOD_DIR / f"{c.id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if errors:
        print("ANOTACIONES INCONSISTENTES:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 1
    print(f"OK: {len(CASES)} casos, {n_props} propiedades, {n_ok} aprobadas "
          f"({100 * n_ok / n_props:.0f} %). Anotación manual == rules.py.")
    if not check_only:
        print(f"escritos en {OOD_DIR.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verifica la anotación sin escribir")
    sys.exit(build(ap.parse_args().check))
