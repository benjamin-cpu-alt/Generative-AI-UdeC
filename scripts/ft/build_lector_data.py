"""Datos de entrenamiento del Lector (E4): pares (mensaje que ve el agente -> JSON de fragmentos).

Fuente A, sintética con etiqueta por construcción (la mayoría):
  Un compositor arma cada aviso uniendo frases de bancos por tema (comuna, dormitorios,
  precio, arriendo, metro, paradero, estacionamiento, mascotas) con relleno y distractores.
  Cada frase lleva MARCADO el fragmento que el Lector debe copiar, así que la salida correcta
  no la escribe ningún modelo: es, por construcción, una subcadena literal del aviso. Las tres
  respuestas cerradas de mascotas salen de la política con la que se generó la frase.

Fuente B, autoetiquetada por el modelo base y filtrada con el `truth` (opcional, --base-run):
  Avisos del generador de la E2 (split `train`, que siempre fue dev) con la salida del propio
  phi4-mini base, tomada de una traza de la E3. Solo se acepta si `anclar` reproduce el `truth`
  en los 7 campos sin marcar ninguna duda. Enseña a no desaprender lo que el Lector ya hacía.

Cada ejemplo de A se comprueba con las herramientas del sistema antes de entrar al set:
  1. cada fragmento es subcadena literal del aviso;
  2. `anclar(fragmentos)` da el `truth` del campo, o `dudas` lo marca para el Verificador.
     Un ejemplo cuyo fragmento correcto `anclar` lee MAL y en silencio se descarta (el límite
     es de la herramienta; entrenar al Lector con él no lo arregla) y se cuenta en el reporte.

Separación de la evaluación: se descarta todo ejemplo que comparta 8 palabras seguidas con un
aviso de hard_test, hard_dev, real_e3, real, test u ood (el mismo criterio que `build_hard.py`
usa entre dev y test). Los avisos de evaluación solo se leen para esa comprobación.

Uso:
  PYTHONPATH=src python3 scripts/ft/build_lector_data.py                 # escribe data/ft_lector/
  PYTHONPATH=src python3 scripts/ft/build_lector_data.py --check         # verifica, no escribe
  PYTHONPATH=src python3 scripts/ft/build_lector_data.py --muestra 8     # imprime ejemplos
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from agents import llm, tools  # noqa: E402
from agents.orchestrator import mensaje_lector  # noqa: E402
from agents.verdad import CAMPOS, igual, leido, marcado, verdad  # noqa: E402
from matcher.grounding import ANSWER_FIELDS, SPAN_FIELDS  # noqa: E402
from matcher.schema import Case  # noqa: E402

OUT = ROOT / "data" / "ft_lector"
SEED = 20261112
N_SINTETICOS = 1100          # avisos sintéticos que se intentan generar (antes de filtros)
P_RELECTURA = 0.12           # fracción de ejemplos con formato de relectura
VALID_FRAC = 0.10
P_FICHA = 0.07              # avisos con formato de ficha «Campo: valor»
P_SIN_TILDES = 0.12         # avisos escritos sin tildes
_TILDES = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
EVAL_SETS = ("hard_test", "hard_dev", "real_e3", "real", "real_fallo", "test", "ood")
LOC, BED, PRICE, RENT, METRO, BUS, PARK, PETS = range(8)   # índice en SPAN_FIELDS

# ------------------------------------------------------------------ vocabulario --

COMUNAS = [c for c in tools.COMUNAS_RM if c not in ("San Pedro", "Alhué", "María Pinto", "Tiltil")]
# Más peso a las comunas urbanas (donde hay metro), sin dejar fuera al resto.
URBANAS = ["Providencia", "Ñuñoa", "Las Condes", "Santiago", "San Miguel", "La Florida", "Macul",
           "La Reina", "Vitacura", "Independencia", "Recoleta", "Maipú", "Peñalolén",
           "Estación Central", "La Cisterna", "Quinta Normal", "San Joaquín", "Conchalí",
           "Puente Alto", "Cerrillos", "Lo Prado", "Pudahuel", "Huechuraba", "Quilicura",
           "La Granja", "El Bosque", "San Bernardo", "Renca", "Lo Barnechea", "Pedro Aguirre Cerda"]
SECTORES = ["sector oriente", "barrio residencial", "sector plaza", "cerca del parque", "barrio tranquilo",
            "sector sur", "sector norte", "a pasos del centro cívico", "barrio universitario",
            "sector alto", "villa consolidada", "barrio comercial", "sector poniente"]
CALLES = ["Av. Los Aromos", "Calle Las Dalias", "Av. Las Industrias", "Pasaje El Roble", "Av. Central",
          "Calle Los Copihues", "Av. La Marina", "Calle El Molino", "Av. Las Torres", "Pasaje Los Olmos",
          "Calle Santa Elena", "Av. Departamental", "Calle Nueva Uno", "Av. El Parrón"]
METROS = ["Tobalaba", "Los Leones", "Ñuble", "Santa Isabel", "Parque Bustamante", "Bío Bío", "El Llano",
          "Departamental", "Ciudad del Niño", "Lo Ovalle", "El Parrón", "Quinta Normal", "Santa Ana",
          "Plaza de Armas", "Salvador", "Manuel Montt", "Pedro de Valdivia", "El Golf", "Alcántara",
          "Hernando de Magallanes", "Simón Bolívar", "Villa Frei", "Chile España", "Monseñor Eyzaguirre",
          "Estadio Nacional", "San Alberto Hurtado", "Pajaritos", "Monte Tabor", "Del Sol",
          "Santiago Bueno", "Vicuña Mackenna", "Mirador", "Los Quillayes", "Elisa Correa", "Las Mercedes",
          "Cementerios", "Einstein", "Dorsal", "Zapadores", "Vespucio Norte", "Plaza Chacabuco",
          "Vivaceta", "Cardenal Caro", "Los Libertadores", "Lo Valledor", "Inés de Suárez",
          "Los Orientales", "Grecia", "Los Presidentes", "Quilín", "Las Torres", "Rojas Magallanes",
          "Trinidad", "San José de la Estrella", "San Pablo", "Neptuno", "Blanqueado", "La Granja",
          "Santa Rosa", "San Ramón", "Ñuñoa", "Macul", "Conchalí", "Cerrillos", "Lo Prado",
          "Plaza de Puente Alto", "Estación Central", "La Cisterna", "San Joaquín", "San Miguel"]
MARKETING = ["Oportunidad", "Excelente conectividad", "Luminoso", "Muy buen estado", "Ideal inversión",
             "Vista despejada", "Recién pintado", "Entrega inmediata", "Muy luminoso en la tarde",
             "Conversable", "Dueño vende directo", "Cocina equipada", "Edificio con conserjería 24 h",
             "Barrio seguro", "Cerca de colegios y supermercados", "Piso alto", "Bajo gasto común",
             "Impecable", "Listo para habitar", "Con bodega", "Terraza amplia", "Quincho en la azotea",
             "Se aceptan ofertas razonables", "Ideal para familia joven", "Remodelado el año pasado"]
DESCRIPCION = ["Living comedor amplio con salida a terraza", "Cocina americana equipada con encimera y horno",
               "El edificio cuenta con piscina, gimnasio y lavandería", "Locomoción a la puerta",
               "Colegios, supermercados y áreas verdes cercanas", "Dormitorio principal con baño en suite y clóset",
               "Pisos flotantes y ventanas de termopanel", "Logia independiente con conexión para lavadora",
               "Excelente distribución y muy buena luz natural", "Condominio cerrado con juegos infantiles",
               "Calefacción central y agua caliente por caldera", "Patio trasero con parrón y bodega exterior",
               "Baños remodelados con mampara de vidrio", "Sala multiuso, bicicletero y quinchos en la azotea",
               "Propiedad sin deudas, lista para escriturar", "Se muestra los fines de semana previa coordinación",
               "Sector residencial de calles tranquilas", "Acceso controlado y cámaras de seguridad",
               "Hermosa vista a la cordillera desde el living", "Clósets en todos los dormitorios"]
SALUDOS = ["hola, ", "hola! ", "buenas, ", "buenas tardes, ", "", ""]

_UNI = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once",
        "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte",
        "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete",
        "veintiocho", "veintinueve"]
_DEC = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"}
_CEN = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
        6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def _hasta_999(n: int) -> str:
    if n < 30:
        return _UNI[n]
    if n < 100:
        d, u = n // 10 * 10, n % 10
        return _DEC[d] + (f" y {_UNI[u]}" if u else "")
    if n == 100:
        return "cien"
    c, r = n // 100, n % 100
    return _CEN[c] + (f" {_hasta_999(r)}" if r else "")


def palabras(n: int, fem: bool = False) -> str:
    """Número en palabras ("doscientos cinco millones", "cinco mil cuatrocientas")."""
    partes = []
    mill, resto = n // 1_000_000, n % 1_000_000
    if mill:
        partes.append("un millón" if mill == 1 else f"{_apocope(_hasta_999(mill))} millones")
    miles, uni = resto // 1000, resto % 1000
    if miles:
        partes.append("mil" if miles == 1 else f"{_apocope(_hasta_999(miles))} mil")
    if uni:
        partes.append(_hasta_999(uni))
    s = " ".join(partes) or "cero"
    return s.replace("ientos", "ientas") if fem else s


def _apocope(s: str) -> str:
    return re.sub(r"veintiuno$", "veintiún", re.sub(r"\buno$", "un", s))


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def M(k: int, s: str) -> str:
    """Marca el fragmento que debe copiarse en el campo k."""
    return f"⟦{k}|{s}⟧"


_MARCA = re.compile(r"⟦(\d)\|([^⟦⟧]*)⟧")


class Frase:
    def __init__(self, texto: str, propio: bool = False):
        self.texto, self.propio = texto, propio      # propio: empieza con nombre propio/sigla


def W(rng: random.Random, opciones):
    """Elige entre opciones ponderadas [(peso, valor), ...] o una lista simple."""
    if opciones and isinstance(opciones[0], tuple) and isinstance(opciones[0][0], (int, float)):
        return rng.choices([v for _, v in opciones], weights=[w for w, _ in opciones])[0]
    return rng.choice(opciones)


# ----------------------------------------------------------------- temas --------

def gen_dormitorios(rng) -> Tuple[str, int, List[str]]:
    """(frase con marca, dormitorios reales, tags)."""
    n, b = W(rng, [(2, 1), (5, 2), (5, 3), (2, 4), (0.4, 5)]), rng.choice([1, 1, 2, 2, 3])
    pal = {1: "un", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco"}[n]
    s = "s" if n > 1 else ""
    forma = W(rng, [
        (10, "nd/nb"), (7, "nd nb"), (3, "nd+nb"), (5, "nd"), (5, "nd+e"), (7, "n dormitorios"),
        (5, "n dormitorios, b baños"), (3, "n dorm."), (4, "n habitaciones"), (3, "n piezas"),
        (5, "palabras"), (3, "suite"), (4, "mas escritorio"), (3, "mas servicio"), (4, "habilitable"),
        (3, "nd + estudio"), (2, "nd + estar"), (4, "estudio")])
    if forma == "nd/nb":
        return M(BED, f"{n}D/{b}B"), n, []
    if forma == "nd nb":
        return M(BED, f"{n}D {b}B"), n, ["dorm_notacion"]
    if forma == "nd+nb":
        return M(BED, f"{n}D+{b}B"), n, ["dorm_notacion"]
    if forma == "nd":
        return M(BED, f"{n}D"), n, ["dorm_notacion"]
    if forma == "nd+e":
        return M(BED, f"{n}D+E"), n, ["dorm_notacion"]
    if forma == "n dormitorios":
        return M(BED, f"{n} dormitorio{s}"), n, []
    if forma == "n dormitorios, b baños":
        return M(BED, f"{n} dormitorio{s}, {b} baño{'s' if b > 1 else ''}"), n, []
    if forma == "n dorm.":
        return M(BED, rng.choice([f"{n} dorm.", f"{n} dorm", f"{n} dorms"])), n, ["dorm_notacion"]
    if forma == "n habitaciones":
        return M(BED, f"{n} habitaci{'ones' if n > 1 else 'ón'}"), n, ["dorm_notacion"]
    if forma == "n piezas":
        return M(BED, f"{n} pieza{s}"), n, ["dorm_notacion"]
    if forma == "palabras":
        return M(BED, f"{pal} {rng.choice(['dormitorio', 'dormitorio', 'habitación'])}{s}".replace("habitacións", "habitaciones")), n, ["cifra_palabras"]
    if forma == "suite":
        n = max(n, 2)
        return M(BED, f"{n} dormitorios ({rng.choice(['uno en suite', 'principal en suite', 'el principal con walk-in closet'])})"), n, []
    if forma == "mas escritorio":
        return M(BED, f"{n} dormitorio{s} {rng.choice(['más escritorio', '+ escritorio', 'y un escritorio', 'más sala de estar', '+ loggia cerrada'])}"), n, ["dorm_no_cuenta"]
    if forma == "mas servicio":
        return M(BED, f"{n} dormitorio{s} {rng.choice(['más pieza de servicio', '+ dependencias de servicio', 'más dormitorio de servicio'])}"), n, ["dorm_no_cuenta"]
    if forma == "habilitable":
        extra = rng.choice(["un escritorio habilitable como dormitorio", "una sala convertible en dormitorio",
                            "un estar que puede usarse como dormitorio", "un altillo habilitable como pieza"])
        return M(BED, f"{n} dormitorio{s} y {extra}"), n, ["dorm_no_cuenta"]
    if forma == "nd + estudio":
        return M(BED, f"{n}D + {rng.choice(['estudio', 'escritorio', 'oficina'])}"), n, ["dorm_no_cuenta", "dorm_notacion"]
    if forma == "nd + estar":
        return M(BED, f"{n}D + {rng.choice(['sala de estar', 'loggia', 'home office'])}"), n, ["dorm_no_cuenta", "dorm_notacion"]
    return M(BED, rng.choice(["estudio", "monoambiente", "loft", "estudio de ambiente único",
                              "monoambiente tipo estudio"])), 0, ["dorm_no_cuenta"]


def gen_precio(rng, uf: float) -> Dict:
    """Precio de venta: frase(s) con marca, valor en UF o CLP, tags. Puede traer montos distractores."""
    en_uf = rng.random() < 0.5
    clp = int(round(rng.uniform(78e6, 265e6) / 500_000) * 500_000)
    tags: List[str] = []
    if en_uf:
        x = int(round(clp / uf / 10) * 10)
        num = miles(x) if rng.random() < 0.8 else str(x)
        forma = W(rng, [(6, "UF x"), (5, "x UF"), (2, "xUF"), (2, "palabras"), (2, "decimal")])
        if forma == "UF x":
            marca = M(PRICE, f"UF {num}")
        elif forma == "x UF":
            marca = M(PRICE, f"{num} UF")
        elif forma == "xUF":
            marca = M(PRICE, f"{num}UF")
        elif forma == "decimal":
            dec = rng.choice([5, 25, 75])
            x = x + dec / (10 if dec == 5 else 100)
            marca = M(PRICE, f"UF {miles(int(x))},{dec}")
        else:
            x = int(round(x / 100) * 100)
            marca = M(PRICE, f"{palabras(x, fem=True)} UF")
            tags.append("cifra_palabras")
        truth = {"price_uf": x, "price_clp": None}
        actual_clp = int(round(x * uf))
    else:
        mm = int(round(clp / 1e6))
        forma = W(rng, [(7, "$"), (4, "$ millones"), (3, "millones"), (4, "palos"), (3, "palabras"), (1, "mm")])
        if forma == "$":
            marca = M(PRICE, f"${miles(clp)}")
            mm = None
        elif forma == "$ millones":
            marca = M(PRICE, f"${mm} millones")
            tags.append("jerga_monto")
        elif forma == "millones":
            marca = M(PRICE, f"{mm} millones" + rng.choice(["", " de pesos"]))
            tags.append("jerga_monto")
        elif forma == "palos":
            marca = M(PRICE, f"{mm} palos")
            tags.append("jerga_monto")
        elif forma == "mm":
            marca = M(PRICE, f"{mm} MM")
            tags.append("jerga_monto")
        else:
            marca = M(PRICE, palabras(mm * 1_000_000) + rng.choice(["", " de pesos"]))
            tags.append("cifra_palabras")
        actual_clp = clp if mm is None else mm * 1_000_000
        truth = {"price_uf": None, "price_clp": actual_clp}

    pre = W(rng, [(5, ""), (3, "Valor "), (3, "Precio: "), (2, "Precio "), (1, "Se vende en "), (1, "Piden "),
                  (1, "Valor de venta: ")])
    frase = f"{pre}{marca}"
    propio = pre == "" and marca.startswith(f"⟦{PRICE}|UF")
    # corrección dentro del aviso: vale el último monto
    if rng.random() < 0.10 and "palabras" not in forma:
        otro = _otro_monto(rng, truth, uf, factor=rng.uniform(1.04, 1.12))
        frase = rng.choice([f"Antes {otro}, ahora {marca}", f"Rebajado de {otro} a {marca}",
                            f"Precio anterior {otro}; hoy {marca}", f"{otro} → rebajado a {marca}"])
        tags.append("correccion")
        propio = False
    return {"frase": Frase(frase, propio), "truth": truth, "clp": actual_clp, "tags": tags}


def _otro_monto(rng, truth: Dict, uf: float, factor: float) -> str:
    if truth["price_uf"] is not None:
        return f"UF {miles(int(round(truth['price_uf'] * factor / 10) * 10))}"
    return f"${miles(int(round(truth['price_clp'] * factor / 500_000) * 500_000))}"


def gen_arriendo(rng, clp_precio: int, uf: float) -> Optional[Dict]:
    r = rng.random()
    if r < 0.42:
        return None
    if r < 0.47:      # arrendado, sin monto: no hay arriendo publicado
        return {"frase": Frase(rng.choice(["Actualmente arrendado", "Hoy está arrendado a buen arrendatario",
                                           "Se vende con arrendatario"])), "truth": None, "tags": []}
    renta = int(round(clp_precio * rng.uniform(0.0038, 0.0075) / 10_000) * 10_000)
    tags: List[str] = []
    forma = W(rng, [(7, "$"), (3, "/mes"), (4, "UF"), (2, "UF,5"), (3, "lucas"), (2, "$ mil"), (2, "sin signo")])
    if renta >= 1_000_000 and forma in ("lucas", "$ mil"):
        forma = "$"
    pre = rng.choice(["Arriendo ", "Arriendo estimado: ", "Arriendo actual: ", "Arriendo referencial ",
                      "Se arrienda en ", "Arr. ", "Renta mensual ", "Arriendo: "])
    if forma in ("/mes", "UF") and pre == "Renta mensual ":
        pre = "Arriendo "
    if forma == "$":
        cuerpo, truth = f"${miles(renta)}", renta
    elif forma == "/mes":
        cuerpo, truth = f"${miles(renta)}{rng.choice(['/mes', ' mensuales', ' al mes'])}", renta
    elif forma == "UF":
        n = max(8, int(round(renta / uf)))
        cuerpo, truth = f"{n} UF{rng.choice(['', ' mensuales', ' al mes'])}", int(round(n * uf))
        tags.append("arriendo_uf")
    elif forma == "UF,5":
        n = max(8, int(round(renta / uf))) + 0.5
        cuerpo, truth = f"{str(n).replace('.', ',')} UF", int(round(n * uf))
        tags.append("arriendo_uf")
    elif forma == "lucas":
        k = int(round(renta / 10_000) * 10)
        cuerpo, truth = f"{k} lucas", k * 1000
        tags.append("jerga_monto")
    elif forma == "$ mil":
        k = int(round(renta / 10_000) * 10)
        cuerpo, truth = f"${k} mil", k * 1000
        tags.append("jerga_monto")
    else:
        cuerpo, truth = miles(renta), renta
    return {"frase": Frase(M(RENT, pre + cuerpo)), "truth": truth, "tags": tags}


def _dist_txt(rng, d: int) -> str:
    """Distancia en cifras, en un formato que el sistema lee: m, mts, metros o km."""
    if d >= 1000 and rng.random() < 0.6:
        km = d / 1000
        s = (f"{km:.1f}" if d % 1000 else f"{int(km)}").replace(".", ",")
        return f"{s} km"
    if d < 1000 and d % 100 == 0 and rng.random() < 0.12:
        return f"0,{d // 100} km"
    num = miles(d) if d >= 1000 else str(d)
    return f"{num} {rng.choice(['m', 'm', 'metros', 'mts'])}" if rng.random() < 0.85 else f"{num}m"


def gen_transporte(rng) -> Dict:
    """Metro y/o paradero. truth = la menor distancia verificable en metros (o None)."""
    st = rng.choice(METROS)
    tags: List[str] = []
    frases: List[Frase] = []
    ds: List[int] = []
    caso = W(rng, [(10, "metro"), (4, "bus"), (5, "ambos"), (2, "palabras"), (4, "no_verificable"),
                   (2, "nv+bus"), (1.5, "nada")])
    d1 = rng.choice([150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950,
                     1000, 1100, 1200, 1300, 1400, 1500, 1800, 2100])
    d2 = rng.choice([100, 150, 200, 250, 300, 350, 400, 500, 600, 700, 800, 900, 1000, 1200])

    def metro(d: int) -> Frase:
        t = _dist_txt(rng, d)
        if "km" in t or "," in t:
            tags.append("dist_formato")
        op = W(rng, [(5, f"A {t} del Metro {st}"), (3, f"Metro {st} a {t}"), (3, f"A {t} del metro"),
                     (2, f"A {t} de la estación {st}"), (2, f"El Metro {st} queda a {t}"),
                     (1, f"Estación {st} a {t}"), (2, f"Metro a {t}")])
        return Frase(M(METRO, op), op.startswith(("Metro", "Estación")))

    def bus(d: int) -> Frase:
        t = _dist_txt(rng, d)
        op = W(rng, [(4, f"Paradero troncal a {t}"), (3, f"A {t} de paradero de buses troncal"),
                     (2, f"A {t} del paradero"), (2, f"Paradero de micros a {t}"),
                     (1, f"Paradero de buses a {t}")])
        return Frase(M(BUS, op))

    def no_verificable() -> Frase:
        op = rng.choice([f"A {rng.choice([5, 8, 10, 12, 15])} minutos caminando del Metro {st}",
                         f"A {rng.choice([2, 3, 4, 5, 6])} cuadras del metro",
                         f"A pasos del Metro {st}", f"Metro {st} a {rng.choice([5, 10, 15])} min a pie",
                         "Muy cerca del metro", f"A {rng.choice([3, 4, 5])} cuadras del Metro {st}"])
        tags.append("dist_formato")
        return Frase(M(METRO, op), op.startswith("Metro"))

    if caso == "metro":
        frases.append(metro(d1)); ds.append(d1)
    elif caso == "bus":
        frases.append(bus(d2)); ds.append(d2)
    elif caso == "ambos":
        fm, fb = metro(d1), bus(d2)
        ds += [d1, d2]
        tags.append("dist_multiple")
        if rng.random() < 0.5:
            union = rng.choice(["; ", ", pero ", " y "])
            a, b = (fm, fb) if rng.random() < 0.5 else (fb, fm)
            b_txt = b.texto if b.propio else _minus(b.texto)
            frases.append(Frase(a.texto + union + b_txt, a.propio))
        else:
            frases += [fm, fb]
    elif caso == "palabras":
        d = rng.choice([200, 300, 400, 500, 600, 700, 800, 900, 1000, 1200, 1500])
        tags.append("cifra_palabras")
        if rng.random() < 0.65:
            op = rng.choice([f"A {palabras(d)} metros del Metro {st}", f"Está a {palabras(d)} metros del metro",
                             f"Metro {st} a {palabras(d)} metros"])
            frases.append(Frase(M(METRO, op), op.startswith("Metro")))
        else:
            op = rng.choice([f"Paradero troncal a {palabras(d)} metros", f"A {palabras(d)} metros del paradero troncal"])
            frases.append(Frase(M(BUS, op)))
        ds.append(d)
    elif caso == "no_verificable":
        frases.append(no_verificable())
    elif caso == "nv+bus":
        frases += [no_verificable(), bus(d2)]
        ds.append(d2)
    return {"frases": frases, "truth": min(ds) if ds else None, "tags": tags}


def gen_estacionamiento(rng) -> Dict:
    clase = W(rng, [(9, "propio"), (5, "asignado"), (5, "ninguno"), (2, "visitas"), (2, "calle"), (3, None)])
    tags: List[str] = []
    if clase is None:
        return {"frase": None, "truth": "ninguno", "tags": []}
    if clase == "propio":
        op = W(rng, [(5, "Estacionamiento propio"), (3, "Incluye estacionamiento"),
                     (2, "Incluye 1 estacionamiento y bodega"), (2, "Con estacionamiento techado"),
                     (2, rng.choice(["Estacionamiento para 1 auto", "Estacionamiento para 2 autos", "Estacionamiento para 3 autos"])), (2, "Dos estacionamientos"),
                     (1, "1 estacionamiento subterráneo"), (3, "Estac. propio"), (2, f"{rng.choice([1, 2])} estac."),
                     (1, "Tiene estacionamiento"), (1, "Estacionamiento y bodega incluidos"),
                     (1, "Estacionamento propio"), (1, "Cochera techada")])
    elif clase == "asignado":
        op = W(rng, [(5, "Estacionamiento asignado"), (2, "Derecho a uso de estacionamiento asignado"),
                     (2, "Estac. asignado"), (2, "Estacionamiento subterráneo asignado"),
                     (1, "Un estacionamiento asignado en el -1")])
    elif clase == "ninguno":
        aparte = f"UF {rng.choice([250, 300, 350, 400, 450])}"
        op = W(rng, [(4, "Sin estacionamiento"), (2, "No tiene estacionamiento"), (2, "Estacionamiento: no tiene"),
                     (2, "No incluye estacionamiento"), (2, "Estacionamiento opcional, se arrienda aparte"),
                     (3, f"Estacionamiento se vende aparte en {aparte}"), (1, "Estacionamiento por separado"),
                     (1, f"Estacionamiento opcional por {aparte} adicionales")])
        if "aparte" in op or "opcional" in op or "separado" in op:
            tags.append("estac_ambiguo")
        if "UF" in op:
            tags.append("multi_monto")
    elif clase == "visitas":
        op = rng.choice(["Solo estacionamiento de visitas", "Estacionamiento de visitas",
                         "Cuenta con estacionamientos de visitas"])
        tags.append("estac_ambiguo")
    else:
        op = rng.choice(["Se estaciona en la calle", "Estacionamiento en la calle", "Solo estacionamiento en la calle"])
        tags.append("estac_ambiguo")
    return {"frase": Frase(M(PARK, op)), "truth": clase, "tags": tags}


def gen_mascotas(rng) -> Dict:
    """Frase, truth (explicit, allowed, species, max_kg) y las 3 respuestas cerradas."""
    caso = W(rng, [(9, "todas"), (6, "kg"), (2, "kg_palabras"), (5, "una"), (3, "una_kg"), (4, "solo"),
                   (3, "si_no"), (5, "no"), (4, "remite"), (5, None)])
    tags: List[str] = []
    otra = {"perro": "gato", "gato": "perro"}
    pl = {"perro": "perros", "gato": "gatos"}
    if caso is None:
        return {"frase": None, "truth": dict(explicit=False, allowed=False, species=[], max_kg=None),
                "resp": ("no_dice", "no_dice", "no_dice"), "tags": ["mascota_silencio"]}
    if caso == "todas":
        op = rng.choice(["Acepta mascotas", "Se aceptan mascotas", "Pet friendly", "Mascotas bienvenidas",
                         "Edificio pet friendly", "Mascotas permitidas", "Admite mascotas", "Mascotas OK",
                         "Mascotas: sí", "Se permiten mascotas sin restricción", "Comunidad pet friendly",
                         "Acepta perros y gatos", "Se admiten mascotas de cualquier tamaño",
                         "La comunidad ahora sí acepta mascotas"])
        t, resp = dict(explicit=True, allowed=True, species=[], max_kg=None), ("si", "si", "si")
    elif caso == "kg":
        k = rng.choice([4, 5, 6, 7, 8, 10, 12, 15, 18, 20, 25, 30])
        op = rng.choice([f"Acepta mascotas de hasta {k} kg", f"Mascotas permitidas hasta {k} kilos",
                         f"Pet friendly (máx. {k} kg)", f"Se aceptan mascotas pequeñas, máximo {k} kg",
                         f"Acepta mascotas (máx. {k} kg)", f"Mascotas hasta {k}kg",
                         f"Se admiten mascotas con límite de {k} kg por mascota"])
        t, resp = dict(explicit=True, allowed=True, species=[], max_kg=float(k)), ("si", "si", "si")
        tags.append("mascota_condicion")
    elif caso == "kg_palabras":
        k = rng.choice([4, 5, 6, 8, 10, 12, 15, 20])
        op = rng.choice([f"Acepta mascotas de hasta {palabras(k)} kilos", f"Mascotas permitidas hasta {palabras(k)} kilos",
                         f"Se aceptan mascotas, máximo {palabras(k)} kilos"])
        t, resp = dict(explicit=True, allowed=True, species=[], max_kg=float(k)), ("si", "si", "si")
        tags += ["mascota_condicion", "cifra_palabras"]
    elif caso == "una":
        sp = rng.choice(["perro", "gato"])
        op = rng.choice([f"Se aceptan {pl[sp]}", f"Acepta {pl[sp]}", f"Se permiten {pl[sp]}", f"Admite {pl[sp]}"])
        t = dict(explicit=True, allowed=True, species=[sp], max_kg=None)
        resp = ("si", "si" if sp == "perro" else "no_dice", "si" if sp == "gato" else "no_dice")
        tags.append("mascota_condicion")
    elif caso == "una_kg":
        sp, k = rng.choice(["perro", "gato"]), rng.choice([4, 5, 6, 8, 10, 12, 15, 20])
        op = rng.choice([f"Se aceptan {pl[sp]} de hasta {k} kg", f"Acepta {pl[sp]} hasta {k} kilos",
                         f"{pl[sp].capitalize()} hasta {k} kg"])
        t = dict(explicit=True, allowed=True, species=[sp], max_kg=float(k))
        resp = ("si", "si" if sp == "perro" else "no_dice", "si" if sp == "gato" else "no_dice")
        tags.append("mascota_condicion")
    elif caso == "solo":
        sp = rng.choice(["perro", "gato"])
        op = rng.choice([f"Solo {pl[sp]}", f"Solo se admiten {pl[sp]}", f"Se aceptan solo {pl[sp]}",
                         f"Únicamente se permiten {pl[sp]}"])
        t = dict(explicit=True, allowed=True, species=[sp], max_kg=None)
        resp = ("si", "si" if sp == "perro" else "no", "si" if sp == "gato" else "no")
        tags.append("mascota_condicion")
    elif caso == "si_no":
        sp = rng.choice(["perro", "gato"])
        op = rng.choice([f"{pl[sp].capitalize()} sí, {pl[otra[sp]]} no", f"Se aceptan {pl[sp]}, {pl[otra[sp]]} no",
                         f"Se aceptan {pl[sp]}; no se permiten {pl[otra[sp]]}",
                         f"No se aceptan {pl[otra[sp]]}, {pl[sp]} sí"])
        t = dict(explicit=True, allowed=True, species=[sp], max_kg=None)
        resp = ("si", "si" if sp == "perro" else "no", "si" if sp == "gato" else "no")
        tags.append("mascota_condicion")
    elif caso == "no":
        op = rng.choice(["No se aceptan mascotas", "Sin mascotas", "Mascotas no permitidas", "No admite mascotas",
                         "Edificio no acepta mascotas", "No se permiten mascotas", "Prohibidas las mascotas"])
        t, resp = dict(explicit=True, allowed=False, species=[], max_kg=None), ("no", "no", "no")
    else:   # remite: no es permiso ni prohibición
        op = rng.choice(["Mascotas: consultar con la administración", "Mascotas según reglamento de copropiedad",
                         "Consultar por mascotas", "Mascotas a convenir con el dueño", "Mascotas: consultar",
                         "Por mascotas, consultar reglamento", "Tenencia de mascotas a evaluar"])
        t, resp = dict(explicit=False, allowed=False, species=[], max_kg=None), ("no_dice", "no_dice", "no_dice")
        tags.append("mascota_silencio")
    return {"frase": Frase(M(PETS, op)), "truth": t, "resp": resp, "tags": tags}


def gen_distractores(rng, precio_truth: Dict, uf: float) -> Tuple[List[Frase], List[str]]:
    """Frases que NO son el dato de este aviso: otros montos, otra unidad, relleno."""
    fr: List[Frase] = []
    tags: List[str] = []
    if rng.random() < 0.22:
        fr.append(Frase(rng.choice([f"Gastos comunes ${miles(rng.choice([65, 80, 95, 110, 140, 180]) * 1000)}",
                                    f"Contribuciones ${miles(rng.choice([90, 120, 180, 240]) * 1000)} trimestrales",
                                    f"GC aprox. ${miles(rng.choice([70, 85, 120]) * 1000)}",
                                    f"Pie desde ${miles(rng.choice([15, 20, 25, 30]) * 1_000_000)}",
                                    f"Bodega opcional en UF {rng.choice([60, 80, 90, 120])}"])))
        tags.append("multi_monto")
    if rng.random() < 0.10:
        otro = _otro_monto(rng, precio_truth, uf, factor=rng.uniform(1.15, 1.45))
        nd = rng.choice([2, 3, 4])
        fr.append(Frase(rng.choice([f"Otra unidad del edificio, de {nd}D, se ofrece en {otro}",
                                    f"El depto del piso de abajo ({nd} dormitorios) se vendió en {otro}",
                                    f"La unidad de al lado ({nd}D) está publicada en {otro}",
                                    f"El vecino vendió el suyo en {otro} hace un mes"])))
        tags.append("distractor")
    for m in rng.sample(MARKETING, W(rng, [(3, 0), (4, 1), (3, 2), (1, 3)])):
        fr.append(Frase(m))
    if rng.random() < 0.30:          # aviso largo, como las descripciones de los portales
        for d in rng.sample(DESCRIPCION, rng.choice([2, 3, 4, 5])):
            fr.append(Frase(d))
    if rng.random() < 0.35:
        fr.append(Frase(rng.choice([f"Piso {rng.randint(2, 18)}", f"Año {rng.randint(1995, 2023)}",
                                    rng.choice(["1 baño", "2 baños"]), "Con bodega", f"Terraza de {rng.randint(4, 12)} m²",
                                    f"Orientación {rng.choice(['norte', 'oriente', 'poniente', 'sur'])}"])))
    return fr, tags


# --------------------------------------------------------------- composición ----

def _minus(s: str, f=str.lower) -> str:
    """Minúscula inicial, saltándose una marca de apertura."""
    m = re.match(r"(⟦\d\|)?(.)", s)
    return s[:m.start(2)] + f(m.group(2)) + s[m.end(2):]


def _mayus(s: str) -> str:
    return _minus(s, str.upper)


def _area(rng, n: int = 2) -> str:
    base = 30 if n == 0 else 28 + 22 * n
    return f"{rng.randint(base - 6, base + 28)} {rng.choice(['m²', 'm²', 'm2'])}"


def gen_cabecera(rng, comuna: str, dorm: str, n: int) -> Tuple[List[Frase], Optional[Frase], List[str]]:
    """Tipo de propiedad + comuna + dormitorios. Devuelve (frases iniciales, cola, tags).
    Convención del fragmento de comuna: «Depto en X» / «Casa en X» si el aviso lo escribe así;
    si no, el fragmento mínimo que nombra la comuna («en X», o «X» con su sector)."""
    tipo = "Casa" if (n >= 3 and rng.random() < 0.45) else rng.choice(["Depto", "Depto", "Departamento", "Depto."])
    if "estudio" in dorm or "monoambiente" in dorm or "loft" in dorm:
        tipo = rng.choice(["Depto", "Departamento"])
    area = _area(rng, n)
    f = W(rng, [(9, "tipo en C"), (5, "C, sector"), (6, "tipo dorm en C"), (5, "C."), (5, "cola"),
                (3, "parentesis"), (3, "direccion"), (3, "C:"), (2, "vendo")])
    es_estudio = dorm.startswith(f"⟦{BED}|") and re.match(rf"⟦{BED}\|(estudio|monoambiente|loft)", dorm)
    de = "" if es_estudio else rng.choice(["", "de "]) if re.search(r"dormitorio|habitaci|pieza", dorm) else ""
    if f == "tipo en C":
        t = tipo.rstrip(".")
        return [Frase(f"{M(LOC, f'{t} en {comuna}')}, {area}, {dorm}")], None, []
    if f == "C, sector":
        return [Frase(f"{M(LOC, f'{comuna}, {rng.choice(SECTORES)}')}", True),
                Frase(f"{tipo} {de}{dorm} de {area}")], None, ["comuna_posicion"]
    if f == "tipo dorm en C":
        return [Frase(f"{tipo} {de}{dorm} {M(LOC, f'en {comuna}')}, {area}")], None, ["comuna_posicion"]
    if f == "C.":
        return [Frase(M(LOC, comuna), True), Frase(f"{tipo} {de}{dorm}, {area}")], None, ["comuna_posicion"]
    if f == "cola":
        return [Frase(f"{tipo} {de}{dorm}, {area}")], Frase(M(LOC, comuna), True), ["comuna_posicion"]
    if f == "parentesis":
        return [Frase(f"{tipo} {de}{dorm} {area} ({M(LOC, comuna)})")], None, ["comuna_posicion"]
    if f == "direccion":
        return [Frase(f"{rng.choice(CALLES)} {rng.randint(100, 9800)}, {M(LOC, comuna)}", True),
                Frase(f"{tipo} {de}{dorm}")], None, ["comuna_posicion"]
    if f == "C:":
        return [Frase(f"{M(LOC, comuna)}: {_minus(tipo)} {de}{dorm}, {area}", True)], None, ["comuna_posicion"]
    return [Frase(f"Vendo {_minus(tipo)} {M(LOC, f'en {comuna}')}, {dorm}, {area}")], None, ["comuna_posicion"]


def componer(rng, i: int) -> Dict:
    uf = float(rng.choice(range(38_500, 41_501, 100)))
    comuna = rng.choice(URBANAS) if rng.random() < 0.8 else rng.choice(COMUNAS)
    dorm, n, t_dorm = gen_dormitorios(rng)
    cab, cola, t_cab = gen_cabecera(rng, comuna, dorm, n)
    precio = gen_precio(rng, uf)
    arr = gen_arriendo(rng, precio["clp"], uf)
    trans = gen_transporte(rng)
    est = gen_estacionamiento(rng)
    masc = gen_mascotas(rng)
    extra, t_extra = gen_distractores(rng, precio["truth"], uf)

    cuerpo: List[Frase] = [precio["frase"]] + trans["frases"]
    for g in (est, masc):
        if g["frase"] is not None:
            cuerpo.append(g["frase"])
    if arr is not None:
        cuerpo.append(arr["frase"])
    cuerpo += extra
    rng.shuffle(cuerpo)
    frases = cab + cuerpo + ([cola] if cola else [])

    estilo = W(rng, [(10, "portal"), (6, "comas"), (3, "mayusculas"), (3, "whatsapp"), (2, "lineas")])
    if estilo in ("portal", "lineas"):      # cada frase es una oración: empieza con mayúscula
        frases = [Frase(_mayus(fr.texto), fr.propio) for fr in frases]
    if estilo == "portal":
        marcado_txt = ". ".join(fr.texto for fr in frases) + "."
        if cola:      # la comuna al final va tras una raya o como oración aparte
            marcado_txt = ". ".join(fr.texto for fr in frases[:-1]) + rng.choice([". ", " — ", ". Comuna: "]) + cola.texto + "."
    elif estilo == "comas":
        sep = rng.choice([", ", ", ", " · ", " / ", "; "])
        marcado_txt = sep.join(fr.texto if (j == 0 or fr.propio) else _minus(fr.texto) for j, fr in enumerate(frases))
        marcado_txt += rng.choice([".", "", "."])
    elif estilo == "mayusculas":
        marcado_txt = (rng.choice([". ", ", ", " - "]).join(fr.texto for fr in frases)).upper()
    elif estilo == "whatsapp":
        cuerpo_txt = ", ".join(fr.texto for fr in frases)
        saludo = rng.choice(SALUDOS)
        if re.match(r"(?:⟦\d\|)?(?:Depto|Departamento|Casa)", cuerpo_txt) and rng.random() < 0.5:
            saludo += rng.choice(["vendo ", "se vende ", "dueño vende ", "ofrezco "])
        marcado_txt = (saludo + cuerpo_txt).lower()
        marcado_txt = marcado_txt.replace(" uf", " UF") if rng.random() < 0.5 else marcado_txt
    else:
        marcado_txt = "\n".join(fr.texto for fr in frases)

    marcado_txt = marcado_txt.replace(".⟧.", ".⟧")      # «4 dorm.» al final de una oración: un solo punto
    sin_tildes = estilo != "mayusculas" and rng.random() < P_SIN_TILDES
    if sin_tildes:                 # muchos avisos reales se escriben sin tildes («estacion», «habitacion»)
        marcado_txt = marcado_txt.translate(_TILDES)
    spans: Dict[str, Optional[str]] = {k: None for k in SPAN_FIELDS}
    for m in _MARCA.finditer(marcado_txt):
        k = SPAN_FIELDS[int(m.group(1))]
        assert spans[k] is None, f"dos marcas para {k}"
        spans[k] = m.group(2)
    texto = _MARCA.sub(lambda m: m.group(2), marcado_txt)
    spans.update(dict(zip(ANSWER_FIELDS, masc["resp"])))
    truth = {"bedrooms": n, "distance_transport_m": trans["truth"], "pets": masc["truth"],
             "parking": est["truth"], **precio["truth"],
             "rent_monthly_clp": arr["truth"] if arr else None, "location": comuna}
    tags = sorted(set(t_dorm + t_cab + precio["tags"] + (arr["tags"] if arr else []) + trans["tags"]
                      + est["tags"] + masc["tags"] + t_extra
                      + (["estilo"] if estilo != "portal" or sin_tildes else [])))
    return {"id": f"FT-{i:04d}", "fuente": "sintetico", "estilo": estilo, "uf": uf, "texto": texto,
            "spans": spans, "truth": truth, "tags": tags}


def componer_ficha(rng, i: int) -> Dict:
    """Aviso como ficha «Campo: valor», el formato de las tablas de los portales."""
    uf = float(rng.choice(range(38_500, 41_501, 100)))
    comuna = rng.choice(URBANAS) if rng.random() < 0.8 else rng.choice(COMUNAS)
    n = W(rng, [(2, 1), (5, 2), (5, 3), (2, 4)])
    tags = ["estilo", "comuna_posicion", "dorm_notacion"]
    campos = [f"Comuna: {M(LOC, comuna)}", f"Tipo: {rng.choice(['Depto', 'Casa', 'Departamento'])}",
              M(BED, f"{rng.choice(['Dormitorios', 'Dorms', 'Habitaciones'])}: {n}"), f"Baños: {rng.choice([1, 2, 3])}",
              f"Superficie: {_area(rng, n)}"]
    clp = int(round(rng.uniform(78e6, 265e6) / 500_000) * 500_000)
    if rng.random() < 0.5:
        x = int(round(clp / uf / 10) * 10)
        campos.append(f"{rng.choice(['Precio', 'Valor'])}: {M(PRICE, rng.choice([f'UF {miles(x)}', f'{miles(x)} UF']))}")
        precio, clp = {"price_uf": x, "price_clp": None}, int(round(x * uf))
    else:
        campos.append(f"{rng.choice(['Precio', 'Valor'])}: {M(PRICE, f'${miles(clp)}')}")
        precio = {"price_uf": None, "price_clp": clp}
    ds = []
    r = rng.random()
    if r < 0.7:
        d = rng.choice([200, 300, 400, 500, 600, 700, 800, 900, 1000, 1200])
        campos.append(M(METRO, f"Metro: {_dist_txt(rng, d)}")); ds.append(d)
    elif r < 0.85:
        campos.append(M(METRO, f"Metro: {rng.choice(['10 min caminando', '5 cuadras', 'cerca'])}"))
        tags.append("dist_formato")
    if rng.random() < 0.35:
        d = rng.choice([100, 200, 300, 400, 500, 700, 900])
        campos.append(M(BUS, f"Paradero: {_dist_txt(rng, d)}")); ds.append(d)
    pk = W(rng, [(4, ("propio", "sí")), (3, ("asignado", "asignado")), (3, ("propio", "1")), (3, ("ninguno", "no tiene")),
                 (2, ("visitas", "solo visitas")), (2, ("propio", "propio")), (2, None)])
    if pk:
        campos.append(M(PARK, f"Estacionamiento: {pk[1]}"))
    k = rng.choice([5, 8, 10, 15, 20])
    mk = W(rng, [(4, ("sí", dict(explicit=True, allowed=True, species=[], max_kg=None), ("si", "si", "si"))),
                 (3, ("no", dict(explicit=True, allowed=False, species=[], max_kg=None), ("no", "no", "no"))),
                 (2, (f"hasta {k} kg", dict(explicit=True, allowed=True, species=[], max_kg=float(k)), ("si", "si", "si"))),
                 (2, ("solo gatos", dict(explicit=True, allowed=True, species=["gato"], max_kg=None), ("si", "no", "si"))),
                 (2, ("consultar", dict(explicit=False, allowed=False, species=[], max_kg=None), ("no_dice",) * 3)),
                 (3, None)])
    if mk:
        campos.append(M(PETS, f"Mascotas: {mk[0]}"))
    renta = None
    if rng.random() < 0.5:
        renta = int(round(clp * rng.uniform(0.004, 0.007) / 10_000) * 10_000)
        if rng.random() < 0.3:
            nuf = max(8, int(round(renta / uf)))
            campos.append(M(RENT, f"Arriendo: {nuf} UF")); renta = int(round(nuf * uf)); tags.append("arriendo_uf")
        else:
            campos.append(M(RENT, f"Arriendo: ${miles(renta)}"))
    cab, resto = campos[:1], campos[1:]
    rng.shuffle(resto)
    marcado_txt = rng.choice([" | ", " | ", "\n", " · ", "; "]).join(cab + resto)
    spans: Dict[str, Optional[str]] = {k_: None for k_ in SPAN_FIELDS}
    for m in _MARCA.finditer(marcado_txt):
        spans[SPAN_FIELDS[int(m.group(1))]] = m.group(2)
    spans.update(dict(zip(ANSWER_FIELDS, mk[2] if mk else ("no_dice",) * 3)))
    truth = {"bedrooms": n, "distance_transport_m": min(ds) if ds else None,
             "pets": mk[1] if mk else dict(explicit=False, allowed=False, species=[], max_kg=None),
             "parking": pk[0] if pk else "ninguno", **precio, "rent_monthly_clp": renta, "location": comuna}
    return {"id": f"FT-{i:04d}", "fuente": "sintetico", "estilo": "ficha", "uf": uf,
            "texto": _MARCA.sub(lambda m: m.group(2), marcado_txt), "spans": spans, "truth": truth,
            "tags": sorted(set(tags))}


# ---------------------------------------------------------------- verificación --

def _caso(ej: Dict) -> Case:
    return Case.from_dict({"id": "ft", "uf_value": ej["uf"],
                           "hard_constraints": dict(presupuesto_max_clp=1, mascota_especie=None, mascota_kg=None,
                                                    distancia_max_transporte_m=1, dormitorios_min=1,
                                                    estacionamiento_requerido=True),
                           "properties": [{"id": ej["id"], "text": ej["texto"], "truth": ej["truth"]}]})


def comprobar_ejemplo(ej: Dict) -> Tuple[bool, Dict[str, str]]:
    """(¿sirve?, estado por campo: directo | con_duda | silencioso | no_literal)."""
    estado: Dict[str, str] = {}
    for k in SPAN_FIELDS:
        v = ej["spans"][k]
        if v is not None and v not in ej["texto"]:
            estado[k] = "no_literal"
    case = _caso(ej)
    prop = case.properties[0]
    h, _ = tools.anclar(ej["spans"], prop.text, case.uf_value, "g3")
    d = tools.dudas(h, prop.text)
    T, L = verdad(prop, case), leido(h)
    for c in CAMPOS:
        if igual(c, L[c], T[c], case.uf_value):
            estado[c] = "directo"
        elif marcado(c, d):
            estado[c] = "con_duda"
        else:
            estado[c] = "silencioso"
    return not any(v in ("silencioso", "no_literal") for v in estado.values()), estado


def ngramas(texto: str, n: int = 8) -> set:
    w = re.findall(r"\w+", texto.casefold())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def avisos_de_evaluacion() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for s in EVAL_SETS:
        out[s] = [p["text"] for f in sorted((ROOT / "data" / "cases" / s).glob("*.json"))
                  for p in json.loads(f.read_text(encoding="utf-8"))["properties"]]
    return out


# ------------------------------------------------------------ fuente B (base) ---

def autoetiquetados(run: str, split: str = "train") -> List[Dict]:
    """Salidas del Lector base sobre avisos del generador (traza de la E3). Se acepta una
    salida solo si CADA fragmento, por sí solo, lleva al `truth`:
      - todos los fragmentos son subcadenas literales del aviso y `anclar` no tuvo que
        recuperar nada desde el aviso (sin avisos de anclaje) ni `dudas` marcó un campo;
      - los dormitorios salen del fragmento copiado (no del respaldo sobre el aviso completo);
      - las tres respuestas cerradas, solas, dan la política y las especies del `truth`;
      - los 7 campos leídos son iguales al `truth`.
    Sin este filtro entrarían salidas que el sistema acierta por sus respaldos (dormitorios en
    null con «3D/2B» en el aviso), y el ajuste aprendería justo el fallo que se quiere quitar."""
    from matcher import grounding
    out = []
    for tp in sorted((ROOT / "results" / run).glob("*.trace.jsonl")):
        case = Case.load(ROOT / "data" / "cases" / split / tp.name.replace(".trace.jsonl", ".json"))
        props = {p.id: p for p in case.properties}
        for line in tp.read_text(encoding="utf-8").splitlines():
            m = json.loads(line)
            if not (m["de"] == "Lector" and m["tipo"] == "spans"):
                continue
            prop, spans = props[m["aviso"]], dict(m["contenido"])
            # El prompt define que aceptar mascotas sin restringir la especie es «si» a perros y
            # a gatos; el modelo base suele dejar «no_dice». Se normaliza a la definición (misma
            # convención que la fuente A). El punto final de la oración no es parte del fragmento.
            if spans.get("acepta_mascotas") == "si" and spans.get("acepta_perros") == spans.get("acepta_gatos") == "no_dice":
                spans["acepta_perros"] = spans["acepta_gatos"] = "si"
            for k in SPAN_FIELDS:
                if spans.get(k) and spans[k].endswith(".") and not re.search(r"(?:dorm|estac|av)\.$", spans[k], re.I):
                    spans[k] = spans[k][:-1]
            h, avisos_anclaje = tools.anclar(spans, prop.text, case.uf_value, "g3")
            T, L = verdad(prop, case), leido(h)
            t = prop.truth
            pol, esp = grounding.pets_from_answers(*(spans.get(k) or "no_dice" for k in ANSWER_FIELDS))
            pol_t = "no_mencionada" if not t.pets.explicit else ("permitidas" if t.pets.allowed else "no_permitidas")
            ok = (all(spans.get(k) is None or spans[k] in prop.text for k in SPAN_FIELDS)
                  and not avisos_anclaje and not tools.dudas(h, prop.text)
                  and grounding.parse_bedrooms(spans.get("bedrooms_text")) == t.bedrooms
                  and pol == pol_t and (pol != "permitidas" or sorted(esp) == sorted(t.pets.species))
                  and spans.get("acepta_mascotas") == {"permitidas": "si", "no_permitidas": "no"}.get(pol_t, "no_dice")
                  and all(igual(c, L[c], T[c], case.uf_value) for c in CAMPOS))
            if ok:
                out.append({"id": prop.id, "fuente": f"base:{run}", "estilo": "generador", "uf": case.uf_value,
                            "texto": prop.text, "spans": {k: spans.get(k) for k in SPAN_FIELDS + ANSWER_FIELDS},
                            "truth": None, "tags": []})
    return out


# ------------------------------------------------------------------- mensajes ---

RELEER = "el fragmento copiado no corresponde al tema"      # el motivo que escribe el orquestador


def a_mensajes(ej: Dict, prompt: Dict[str, str], rng: random.Random, relectura: bool) -> Dict:
    pid = _id_variado(rng, ej["id"])
    if relectura:
        campos = rng.sample(list(tools.SPAN_DE), rng.choice([1, 1, 2, 2, 3]))
        campos = [c for c in tools.CAMPOS if c in campos]
        user, schema = mensaje_lector(prompt, pid, ej["texto"], {c: RELEER for c in campos})
    else:
        user, schema = mensaje_lector(prompt, pid, ej["texto"])
    salida = {k: ej["spans"][k] for k in schema["properties"]}
    return {"messages": [{"role": "system", "content": prompt["system"]},
                         {"role": "user", "content": user},
                         {"role": "assistant", "content": json.dumps(salida, ensure_ascii=False, indent=2)}]}


def _id_variado(rng: random.Random, base: str) -> str:
    """Ids con la forma de los que usa el sistema (letras-dígitos), nunca los de evaluación."""
    pref = rng.choice(["AV", "P", "PROP", "ID", "COD", "REF", "LST", "N"])
    return f"{pref}-{rng.randint(1, 9999):04d}" if rng.random() < 0.8 else f"{pref}{rng.randint(1, 999)}"


N_REVISION = (45, 15)      # (sintéticos, autoetiquetados) que el equipo revisa a mano


def hoja_revision(ejemplos: List[Dict], seed: int) -> str:
    """Muestra aleatoria para la revisión humana: aviso + fragmentos, y dos columnas vacías.
    El archivo con las respuestas del equipo es `revision_manual_respondida.csv` (no se pisa)."""
    import csv
    import io
    rng = random.Random(seed + 2)
    sint = [e for e in ejemplos if e["fuente"] == "sintetico"]
    base = [e for e in ejemplos if e["fuente"] != "sintetico"]
    muestra = rng.sample(sint, N_REVISION[0]) + rng.sample(base, min(N_REVISION[1], len(base)))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "fuente", "aviso", *SPAN_FIELDS, *ANSWER_FIELDS, "correcto (si/no)", "comentario"])
    for e in muestra:
        w.writerow([e["id"], e["fuente"], e["texto"], *[e["spans"][k] if e["spans"][k] is not None else "null"
                                                        for k in SPAN_FIELDS + ANSWER_FIELDS], "", ""])
    return buf.getvalue()


# ----------------------------------------------------------------------- main ---

def construir(n: int, seed: int, base_run: Optional[str]) -> Tuple[List[Dict], Dict]:
    rng = random.Random(seed)
    evals = avisos_de_evaluacion()
    eval_ngr = set().union(*(ngramas(t) for ts in evals.values() for t in ts))
    eval_txt = {t.strip().casefold() for ts in evals.values() for t in ts}
    rep = {"intentados": n, "descartes": Counter(), "estado": Counter(), "por_estilo": Counter(),
           "tags": Counter(), "solapados": 0, "duplicados": 0}
    vistos, ejemplos = set(), []
    for i in range(1, n + 1):
        ej = componer_ficha(rng, i) if rng.random() < P_FICHA else componer(rng, i)
        ok, estado = comprobar_ejemplo(ej)
        if not ok:
            for c, v in estado.items():
                if v in ("silencioso", "no_literal"):
                    rep["descartes"][f"{c}:{v}"] += 1
            continue
        if ej["texto"].casefold() in vistos:
            rep["duplicados"] += 1
            continue
        if ej["texto"].strip().casefold() in eval_txt or ngramas(ej["texto"]) & eval_ngr:
            rep["solapados"] += 1
            continue
        vistos.add(ej["texto"].casefold())
        ej["estado"] = estado
        for c in CAMPOS:
            rep["estado"][f"{c}:{estado[c]}"] += 1
        rep["por_estilo"][ej["estilo"]] += 1
        rep["tags"].update(ej["tags"])
        ejemplos.append(ej)
    rep["sinteticos"] = len(ejemplos)
    if base_run:
        base = [e for e in autoetiquetados(base_run) if e["texto"].casefold() not in vistos]
        rep["autoetiquetados"] = len(base)
        ejemplos += base
    return ejemplos, rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=N_SINTETICOS)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--base-run", default="agents_v1_train20",
                    help="corrida de la E3 sobre `train` de donde salen los ejemplos autoetiquetados ('' = ninguno)")
    ap.add_argument("--check", action="store_true", help="verifica que data/ft_lector/ coincide con lo que se genera")
    ap.add_argument("--muestra", type=int, default=0)
    a = ap.parse_args(argv)

    ejemplos, rep = construir(a.n, a.seed, a.base_run or None)
    if a.muestra:
        for ej in random.Random(1).sample(ejemplos, a.muestra):
            print(f"\n[{ej['id']} · {ej['estilo']} · {','.join(ej['tags'])}]\n{ej['texto']}")
            print("  " + json.dumps({k: v for k, v in ej["spans"].items() if v not in (None, 'no_dice')}, ensure_ascii=False))
            print("  estado:", {c: v for c, v in ej.get("estado", {}).items() if v != "directo"})
        return 0

    prompt = llm.load_prompt("lector", "v1")
    rng = random.Random(a.seed + 1)
    orden = list(ejemplos)
    rng.shuffle(orden)
    sint = [e for e in orden if e["fuente"] == "sintetico"]
    n_valid = int(round(len(sint) * VALID_FRAC))
    valid_ids = {e["id"] for e in sint[:n_valid]}
    train, valid = [], []
    for ej in orden:
        ej["split"] = "valid" if ej["id"] in valid_ids and ej["fuente"] == "sintetico" else "train"
        ej["relectura"] = ej["fuente"] == "sintetico" and rng.random() < P_RELECTURA
        (valid if ej["split"] == "valid" else train).append(a_mensajes(ej, prompt, rng, ej["relectura"]))

    archivos = {
        "train.jsonl": "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in train),
        "valid.jsonl": "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in valid),
        "ejemplos.jsonl": "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in orden),
    }
    rep_out = {"seed": a.seed, "intentados": rep["intentados"], "sinteticos": rep["sinteticos"],
               "autoetiquetados": rep.get("autoetiquetados", 0), "train": len(train), "valid": len(valid),
               "relectura": sum(e["relectura"] for e in orden),
               "descartes_por_herramienta": dict(sorted(rep["descartes"].items())),
               "descartes_por_solapamiento_con_evaluacion": rep["solapados"], "duplicados": rep["duplicados"],
               "estado_por_campo": dict(sorted(rep["estado"].items())),
               "por_estilo": dict(rep["por_estilo"]), "tags": dict(sorted(rep["tags"].items())),
               "sets_de_evaluacion_comprobados": list(EVAL_SETS),
               "sha256": {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in archivos.items()}}
    archivos["reporte.json"] = json.dumps(rep_out, ensure_ascii=False, indent=2) + "\n"
    archivos["revision_manual.csv"] = hoja_revision(orden, a.seed)

    if a.check:
        malos = [k for k, v in archivos.items()
                 if not (OUT / k).exists() or (OUT / k).read_text(encoding="utf-8") != v]
        print("OK: data/ft_lector/ coincide con el generador" if not malos else f"DIFIEREN: {malos}")
        return 1 if malos else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for k, v in archivos.items():
        (OUT / k).write_text(v, encoding="utf-8")
    print(json.dumps(rep_out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
