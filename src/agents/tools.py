"""Herramientas deterministas que usan los agentes (E3). Ningún agente calcula ni compara:
lee, propone o decide a qué herramienta o agente pasar; estas funciones ejecutan.

  anclar      Lector -> spans -> hechos (grounding g3 de la E2 + conversión a números).
  comprobar   Verificador: valida una corrección propuesta contra el aviso. El valor debe
              salir de la evidencia (cifra, cifra en palabras o jerga: "135 palos",
              "680 lucas", "seiscientos metros") y la evidencia debe estar en el aviso.
  evaluar     Decisor: las 5 restricciones duras sobre los hechos, con estado
              cumple / falla / no_verificable por restricción. A diferencia de
              constraints.decide (E2), convierte también el arriendo en UF a CLP.
  ordenar     Decisor: arma el JSON estricto de la E1 (mismo esquema que el baseline).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from matcher import grounding, normalize
from matcher.constraints import C_BEDROOMS, C_BUDGET, C_DISTANCE, C_PARKING, C_PETS
from matcher.schema import Case

# Campos que ve y corrige el Verificador, en el orden en que se le muestran.
# `distancia` es la menor entre metro y paradero troncal (lo único que usa la restricción).
CAMPOS = ("comuna", "dormitorios", "precio", "arriendo", "distancia", "estacionamiento", "mascotas",
          "mascotas_kg")
# Spans del Lector que alimentan cada campo (lo que se le pide releer).
SPAN_DE = {"comuna": ("location_text",), "dormitorios": ("bedrooms_text",), "precio": ("price_text",),
           "arriendo": ("rent_text",), "distancia": ("distance_metro_text", "distance_bus_text"),
           "estacionamiento": ("parking_text",), "mascotas": ("pets_text",), "mascotas_kg": ("pets_text",)}
# Claves de `hechos` que escribe cada campo.
CLAVES = {"distancia": ("distancia_metro", "distancia_bus"),
          "mascotas": ("mascotas", "especies", "mascotas_kg", "_mascotas_por_parser"),
          "mascotas_kg": ("mascotas", "especies", "mascotas_kg", "_mascotas_por_parser")}


def distancia(h: Dict) -> Optional[int]:
    ds = [d for d in (h.get("distancia_metro"), h.get("distancia_bus")) if d is not None]
    return min(ds) if ds else None
MASCOTAS = ("permitidas", "no_permitidas", "no_explicita")
# Las 52 comunas de la Región Metropolitana: una comuna leída fuera de esta lista es dudosa.
COMUNAS_RM = (
    "Alhué", "Buin", "Calera de Tango", "Cerrillos", "Cerro Navia", "Colina", "Conchalí", "Curacaví",
    "El Bosque", "El Monte", "Estación Central", "Huechuraba", "Independencia", "Isla de Maipo",
    "La Cisterna", "La Florida", "La Granja", "La Pintana", "La Reina", "Lampa", "Las Condes",
    "Lo Barnechea", "Lo Espejo", "Lo Prado", "Macul", "Maipú", "María Pinto", "Melipilla", "Ñuñoa",
    "Padre Hurtado", "Paine", "Pedro Aguirre Cerda", "Peñaflor", "Peñalolén", "Pirque", "Providencia",
    "Pudahuel", "Puente Alto", "Quilicura", "Quinta Normal", "Recoleta", "Renca", "San Bernardo",
    "San Joaquín", "San José de Maipo", "San Miguel", "San Pedro", "San Ramón", "Santiago", "Talagante",
    "Tiltil", "Vitacura")
PARKING = ("propio", "asignado", "visitas", "calle", "ninguno", "no_mencionado")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()


# ------------------------------------------------------ números en palabras ----

_SMALL = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21, "veintiuno": 21,
    "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
    "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30,
    "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
    "noventa": 90, "cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300,
    "cuatrocientos": 400, "quinientos": 500, "seiscientos": 600, "setecientos": 700,
    "ochocientos": 800, "novecientos": 900,
}


def numeros_en_palabras(texto: str) -> List[float]:
    """"doscientos cinco millones" -> [205000000] ; "cinco mil cuatrocientas" -> [5400] ;
    "a mil metros" -> [1000] ; "perros de hasta cinco kilos" -> [5]."""
    out: List[float] = []
    total = cur = 0
    active = False
    for tok in re.findall(r"[a-zñ]+", _fold(texto)):
        w = tok.replace("ientas", "ientos")
        if w in _SMALL:
            cur += _SMALL[w]
            active = True
        elif w == "mil":
            cur = max(cur, 1) * 1000
            active = True
        elif w in ("millon", "millones"):
            total += max(cur, 1) * 1_000_000
            cur = 0
            active = True
        elif w == "y" and active:
            continue
        elif active:
            out.append(float(total + cur))
            total = cur = 0
            active = False
    if active:
        out.append(float(total + cur))
    return out


# Multiplicadores de la jerga chilena y de las unidades de distancia.
_MULT = [(re.compile(r"^\s*(?:palos?|millones|mill[oó]n|mm\b|mill\b)", re.I), 1_000_000),
         (re.compile(r"^\s*(?:lucas?|mil\b)", re.I), 1_000),
         (re.compile(r"^\s*(?:km|kms|kil[oó]metros?)\b", re.I), 1_000)]
_DIGITS = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def candidatos(texto: str) -> List[float]:
    """Todos los valores numéricos que la evidencia puede querer decir: cada cifra tal cual
    y multiplicada por la jerga/unidad que la sigue, más las cifras escritas en palabras."""
    vals: List[float] = []
    for m in _DIGITS.finditer(texto or ""):
        v = float(m.group(0).replace(".", "").replace(",", "."))
        vals.append(v)
        after = texto[m.end():m.end() + 12]
        vals += [v * k for rx, k in _MULT if rx.search(after)]
    words = numeros_en_palabras(texto or "")
    vals += words
    # "doscientos cinco millones" ya lo resuelve numeros_en_palabras; "ciento veinte palos" no
    if words and re.search(r"\b(?:palos?|lucas?)\b", texto or "", re.I):
        k = 1_000_000 if re.search(r"\bpalos?\b", texto, re.I) else 1_000
        vals += [v * k for v in words]
    return vals


def _unidad(evidencia: str) -> Optional[str]:
    s = evidencia.upper()
    if re.search(r"\bUF\b|UF\s*\d|\dUF", s):
        return "UF"
    if re.search(r"\$|PESO|CLP|LUCA|PALO|MILL[OÓ]N|MILLONES|\bMIL\b|\bMM\b", s):
        return "CLP"
    return None


def valor_numerico(valor) -> Optional[float]:
    """El número que propone el agente: 135000000, "135.000.000 CLP", "3950 UF", "600 m"."""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    c = candidatos(str(valor or ""))
    if not c:
        return None
    # "135 palos" -> el mayor candidato (con multiplicador); "600 m" -> 600
    return max(c) if re.search(r"palo|luca|mill|\bmil\b", str(valor), re.I) else c[0]


_LIMITE = re.compile(r"(?:mascotas?|perr[oa]s?|gat[oa]s?)\b[^.;]{0,25}\b(?:hasta|de hasta|m[aá]ximo|menores de)\b", re.I)


def especies_de(ev: str) -> Optional[List[str]]:
    """Especies permitidas según una evidencia que acepta mascotas, o None si la evidencia
    no es un permiso explícito. "Perros de hasta cinco kilos" es un permiso (con límite)."""
    if _REMITE.search(ev):
        return None
    si = [sp for sp, rx in grounding._SPECIES_RE.items() if re.search(rx.pattern + r"\s+s[ií]\b", ev, re.I)]
    no = [sp for sp, rx in grounding._SPECIES_RE.items() if re.search(rx.pattern + r"\s+no\b", ev, re.I)]
    if si:                                  # "Gatos sí, perros no"
        return [] if len(si) == 2 else si
    if re.search(r"mascotas?\s*:?\s*(?:ok|s[ií])\b|mascotas? sin restricci", ev, re.I):
        return []
    parsed = grounding.parse_species(ev)
    if parsed is not None:
        return parsed[1] if parsed[0] else None
    if _LIMITE.search(ev):
        named = [sp for sp, rx in grounding._SPECIES_RE.items() if rx.search(ev)]
        return named if len(named) == 1 else []
    return None


def _categoria(valor, opciones) -> str:
    """"permitidas | hasta 15 kg" -> "permitidas"; prueba primero las opciones más largas
    ("no_permitidas" contiene "permitidas")."""
    v = _fold(str(valor or "")).replace(" ", "_")
    return next((o for o in sorted(opciones, key=len, reverse=True) if o in v), str(valor or ""))


def _cerca(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.5, 0.005 * abs(b))


# ------------------------------------------------------------------ anclar ----

def anclar(spans: Dict, texto: str, uf: float, version: str = "g3") -> Tuple[Dict, List[str]]:
    """Spans del Lector -> hechos numéricos. Es la capa de la E2 (grounding g3) más la
    conversión a CLP/metros; los campos que no se pueden leer quedan en None."""
    kw, warnings = grounding.facts_from_spans(spans, texto, version)
    price_v, price_u = normalize.parse_money(kw["price_text"])
    rent_v, rent_u = normalize.parse_money(kw["rent_text"]) if kw["rent_text"] else (None, None)
    pol = {"permitidas": "permitidas", "no_permitidas": "no_permitidas"}.get(kw["pets_policy"], "no_explicita")
    hechos = {
        "comuna": kw["location"],
        "dormitorios": kw["bedrooms"],
        "precio": normalize.to_clp(price_v, price_u, uf) if price_v is not None else None,
        "arriendo": normalize.to_clp(rent_v, rent_u, uf) if rent_v is not None else None,
        "distancia_metro": normalize.parse_distance_m(kw["distance_metro_text"]),
        "distancia_bus": normalize.parse_distance_m(kw["distance_bus_text"]),
        "estacionamiento": kw["parking"],
        "mascotas": pol,
        "especies": list(kw["pets_species"]),
        "mascotas_kg": kw["pets_max_kg"],
        # ¿la política salió de una frase que el parser reconoce, o de las respuestas del Lector?
        "_mascotas_por_parser": any(c and (grounding.parse_species(c) is not None or especies_de(c) is not None)
                                    for c in (spans.get("pets_text"), grounding.topic_sentence(texto, "pets_text"))),
    }
    return hechos, warnings


_RE = lambda p: re.compile(p, re.I)  # noqa: E731
_HABLA = {
    "precio": _RE(r"UF|\$|peso|palo|millon|lucas"),
    "arriendo": _RE(r"arriend|\barr\.|/mes|mensual"),
    "distancia": _RE(r"metro|estaci[óo]n|paradero|troncal"),
    "estacionamiento": _RE(r"estac|parking|cochera|\bautos?\b"),
    "mascotas": _RE(r"mascota|perr[oa]s?|gat[oa]s?|\bpets?\b"),
    "mascotas_kg": _RE(r"\bkg\b|kilo"),
}
_REMITE = _RE(r"reglamento|consultar|administraci[óo]n|a convenir|evaluar")
_DORM = _RE(r"\b(\d+|un|una|uno|dos|tres|cuatro|cinco)\s*(?:d\b|dorm|habitaci|pieza)")


_FRASE_DE = {
    "comuna": _RE(r"\ben\s+[A-ZÁÉÍÓÚÑ]|comuna"),
    "dormitorios": _RE(r"\d\s*d\b|dorm|habitaci|pieza|estudio"),
    "precio": _RE(r"UF|\$|peso|palo|millon|valor|precio"),
    "arriendo": _HABLA["arriendo"], "distancia": _HABLA["distancia"],
    "estacionamiento": _HABLA["estacionamiento"], "mascotas": _HABLA["mascotas"],
    "mascotas_kg": _HABLA["mascotas_kg"],
}


# Frases que hablan de OTRA propiedad ("En el mismo edificio se vende otra unidad 3D...").
_OTRA = _RE(r"otra unidad|otro (?:depto|departamento)|mismo edificio|vecino|piso de (?:arriba|abajo)|"
            r"se vendi[óo]|unidad de al lado|antes (?:costaba|val[ií]a)")
_SPLIT = re.compile(r"(?<=\.)\s+(?=[A-ZÁÉÍÓÚÑ¡¿\d$])|,(?!\d)\s*|;\s*|\s+[—–-]\s+")


def frase(texto: str, campo: str) -> Optional[str]:
    """La primera oración o cláusula del aviso que habla del campo y no de otra propiedad."""
    rx = _FRASE_DE.get(campo)
    for f in _SPLIT.split(texto):
        if rx and f.strip() and rx.search(f) and not _OTRA.search(f):
            return f.strip()
    return None


def dudas(h: Dict, texto: str) -> Dict[str, str]:
    """Señales deterministas de que un campo puede estar mal leído (lo que el Verificador
    revisa), con la frase del aviso donde mirar. No corrige nada."""
    d = _dudas(h, texto)
    for c in d:
        f = frase(texto, c)
        if f:
            d[c] += f' (mira: "{f}")'
    return d


def _dudas(h: Dict, texto: str) -> Dict[str, str]:
    d: Dict[str, str] = {}
    com = h.get("comuna")
    if not com:
        d["comuna"] = "no se pudo leer la comuna"
    elif _fold(com.strip()) not in {_fold(c) for c in COMUNAS_RM}:
        d["comuna"] = "lo leído no es el nombre de una comuna de la Región Metropolitana"
    dorms = {m.group(1).lower() for m in _DORM.finditer(texto)}
    if h.get("dormitorios") is None:
        d["dormitorios"] = "no se pudo leer el número de dormitorios"
    elif len(dorms) > 1:
        d["dormitorios"] = "el aviso menciona más de un número de dormitorios"
    p = h.get("precio")
    if p is None:
        d["precio"] = "no se pudo leer el precio"
    elif not 20_000_000 <= p <= 2_000_000_000:
        d["precio"] = "el precio leído es inverosímil para una vivienda"
    a = h.get("arriendo")
    if a is None and _HABLA["arriendo"].search(texto):
        d["arriendo"] = "el aviso habla de arriendo pero no se pudo leer el monto"
    elif a is not None and not 100_000 <= a <= 5_000_000:
        d["arriendo"] = "el arriendo mensual leído es inverosímil"
    if distancia(h) is None and _HABLA["distancia"].search(texto):
        d["distancia"] = "el aviso habla de metro o paradero pero no se pudo leer la distancia"
    if h.get("estacionamiento") == "no_mencionado" and _HABLA["estacionamiento"].search(texto):
        d["estacionamiento"] = "el aviso habla de estacionamiento pero no se pudo clasificar"
    pets_talk = _HABLA["mascotas"].search(texto)
    if h.get("mascotas") == "no_explicita" and pets_talk:
        d["mascotas"] = "el aviso habla de mascotas pero no se leyó una política"
    elif h.get("mascotas") == "permitidas" and not h.get("_mascotas_por_parser"):
        d["mascotas"] = "el permiso salió de las respuestas del Lector, no de una frase reconocible"
    elif pets_talk and _REMITE.search(texto):
        d["mascotas"] = "el aviso remite a un reglamento, a consultar o a evaluar"
    if h.get("mascotas") == "permitidas" and h.get("mascotas_kg") is None and _HABLA["mascotas_kg"].search(texto):
        d["mascotas_kg"] = "el aviso menciona un peso pero no se leyó un límite"
    return d


def lectura(campo: str, h: Dict) -> str:
    """Cómo quedó leído un campo, en palabras (lo que el Verificador revisa)."""
    v = distancia(h) if campo == "distancia" else h.get(campo)
    if campo == "mascotas":
        if v != "permitidas":
            return {"no_permitidas": "PROHÍBE mascotas", "no_explicita": "no declara política"}[v]
        sp = " y ".join(h["especies"]) if h["especies"] else "cualquier especie"
        return f"PERMITE {sp}"
    if campo == "mascotas_kg":
        return "sin límite de peso" if v is None else f"límite {v:g} kg"
    if v is None:
        return "NO SE PUDO LEER"
    if campo in ("precio", "arriendo"):
        return "$" + f"{int(v):,}".replace(",", ".") + (" CLP" if campo == "precio" else " CLP/mes")
    if campo == "distancia":
        partes = [f"{n} {h[k]} m" for n, k in (("metro", "distancia_metro"), ("paradero", "distancia_bus"))
                  if h.get(k) is not None]
        return f"{v} m ({', '.join(partes)})"
    return str(v)


# --------------------------------------------------------------- comprobar ----

def comprobar(campo: str, valor, evidencia: Optional[str], texto: str, uf: float
              ) -> Tuple[bool, object, str]:
    """¿La corrección propuesta sale de la evidencia, y la evidencia está en el aviso?
    Devuelve (ok, valor normalizado para `hechos`, motivo)."""
    if campo not in CAMPOS:
        return False, None, f"campo desconocido {campo!r}"
    ev = (evidencia or "").strip()
    if not ev or "no copió" in ev or "no se pudo" in _fold(ev):
        return False, None, "falta la evidencia: copia el fragmento desde el texto del aviso, no desde la tabla"
    if not grounding.clause_anchored(ev, texto):
        return False, None, f"la evidencia no está en el aviso: {ev!r}"
    if _OTRA.search(ev) and campo != "comuna":
        return False, None, "la evidencia habla de otra propiedad, no de este aviso"

    if campo == "comuna":
        s = str(valor or "").strip()
        if not s or _fold(s) not in _fold(texto):
            return False, None, f"{s!r} no aparece en el aviso"
        # "Santiago Centro" -> "Santiago"; "Bellavista de La Florida" -> "La Florida"
        canon = [c for c in sorted(COMUNAS_RM, key=len, reverse=True) if re.search(rf"\b{_fold(c)}\b", _fold(s))]
        return True, (canon[0] if canon else s), "ok"

    if campo == "estacionamiento":
        v = _categoria(valor, PARKING)
        if v not in PARKING:
            return False, None, f"valor {v!r} no es uno de {PARKING}"
        if v in ("propio", "asignado"):
            if not re.search(r"estac|parking|cochera|\bautos?\b", ev, re.I):
                return False, None, "la evidencia no habla de estacionamiento"
            if grounding.parse_parking(ev, strict=True, apart=True) in ("calle", "visitas", "ninguno"):
                return False, None, "la evidencia dice que el estacionamiento no viene incluido"
        return True, v, "ok"

    if campo == "mascotas":
        v = _categoria(valor, MASCOTAS)
        if v not in MASCOTAS:
            return False, None, f"valor {v!r} no es uno de {MASCOTAS}"
        if v == "permitidas" and especies_de(ev) is None:
            return False, None, "la evidencia no dice explícitamente que acepta mascotas"
        if v != "permitidas" and especies_de(ev) is not None:
            return False, None, "la evidencia sí acepta mascotas explícitamente"
        if v == "no_permitidas" and grounding.parse_species(ev) != (False, []):
            return False, None, "la evidencia no prohíbe mascotas"
        return True, v, "ok"

    lecturas = interpretar(campo, ev, uf)
    rango = {"precio": (20_000_000, 2_000_000_000), "arriendo": (100_000, 5_000_000)}.get(campo)
    if rango and lecturas and not any(rango[0] <= v <= rango[1] for v in lecturas):
        return False, None, f"{lecturas[0]:,} no es un {campo} verosímil: ¿es el dato de otra cosa?".replace(",", ".")
    if rango:
        lecturas = [v for v in lecturas if rango[0] <= v <= rango[1]]
    if not lecturas:
        return False, None, f"la herramienta no encuentra un dato de {campo} en la evidencia"
    if len(set(lecturas)) == 1:
        v = lecturas[0]
        return True, v, "ok" if _coincide(campo, valor, v, uf) else f"ok: la evidencia dice {v} (el agente escribió {valor!r})"
    elegidas = sorted({v for v in lecturas if _coincide(campo, valor, v, uf)})
    if len(elegidas) == 1:
        return True, elegidas[0], "ok"
    return False, None, f"la evidencia trae varios valores posibles ({sorted(set(lecturas))}); copia solo el que corresponde"


def _coincide(campo: str, valor, v, uf: float) -> bool:
    num = valor_numerico(valor)
    if num is None:
        return False
    if campo in ("precio", "arriendo"):
        return _cerca(num, v) or abs(num * uf - v) <= uf      # en pesos o en UF
    return _cerca(num, v)


_MULT_DE = [(r"palos?|millones|mill[oó]n|mm\b", 1_000_000), (r"lucas?|mil\b", 1_000)]


def _word_spans(folded: str):
    """Tramos de palabras numéricas consecutivas: (inicio, fin, palabras)."""
    spans, cur = [], []
    for m in re.finditer(r"[a-zñ]+", folded):
        w = m.group(0).replace("ientas", "ientos")
        if w in _SMALL or w in ("mil", "millon", "millones") or (w == "y" and cur):
            cur.append((m.start(), m.end(), w))
            continue
        if cur:
            spans.append(cur)
            cur = []
    if cur:
        spans.append(cur)
    out = []
    for c in spans:
        while c and c[-1][2] == "y":
            c.pop()
        if c:
            out.append((c[0][0], c[-1][1], [x[2] for x in c]))
    return out


def interpretar(campo: str, ev: str, uf: float) -> List:
    """Lo que la evidencia dice sobre el campo, leído por código (el agente solo la localiza).
    Devuelve todas las lecturas posibles; si hay más de una, el valor del agente elige."""
    toks = []   # (valor, inicio, fin) para cifras y cifras en palabras
    for m in _DIGITS.finditer(ev):
        toks.append((float(m.group(0).replace(".", "").replace(",", ".")), m.start(), m.end()))
    folded = _fold(ev)
    for i, j, words in _word_spans(folded):
        if set(words) <= {"mil", "millon", "millones", "y"} and re.search(r"\d\s*$", folded[:i]):
            continue                       # "$420 mil": el multiplicador de una cifra, no un número
        for v in numeros_en_palabras(" ".join(words)):
            toks.append((v, i, j))
    out: List = []
    for v, i, j in toks:
        after, before = folded[j:j + 14], folded[max(0, i - 6):i]
        after = re.sub(r"^\s*de\s+", " ", after)      # "doscientos millones de pesos"
        if campo in ("precio", "arriendo"):
            k = next((k for rx, k in _MULT_DE if re.match(r"\s*(?:%s)" % rx, after)), 1)
            if re.match(r"\s*uf\b", after) or re.search(r"uf\s*$", before):
                out.append(normalize.to_clp(v, "UF", uf))
            elif k > 1 or "$" in before or re.match(r"\s*(?:pesos|clp)", after) or v >= 1_000_000:
                out.append(int(round(v * k)))
            elif campo == "arriendo" and v >= 100_000:
                out.append(int(round(v)))
        elif campo == "distancia":
            mm = re.match(r"\s*(km|kms|kilometros?|m\b|mts|metros?)", after)
            if mm:
                out.append(int(round(v * (1000 if mm.group(1).startswith("k") else 1))))
        elif campo == "dormitorios":
            if v == int(v) and (re.match(r"\s*(?:d\b|d[+/ ]|dorm|habitaci|pieza)", after)
                                or re.search(r"(?:dormitorios?|habitaciones|piezas)\s*:\s*$", folded[:i])):
                out.append(int(v))
        elif campo == "mascotas_kg":
            if re.match(r"\s*(?:kg|kilos?)\b", after):
                out.append(v)
    if campo == "dormitorios" and not out and grounding._STUDIO_RE.search(ev):
        out.append(0)
    return out


# ----------------------------------------------------------------- evaluar ----

def evaluar(pid: str, h: Dict, case: Case) -> Dict:
    """Las 5 restricciones sobre los hechos. Un dato faltante nunca aprueba: la restricción
    queda `no_verificable` y cuenta como fallida (misma regla de seguridad que la E2)."""
    hc, sc = case.hard_constraints, case.soft_constraints
    est: Dict[str, str] = {}
    motivo: Dict[str, str] = {}

    p = h.get("precio")
    est[C_BUDGET] = "no_verificable" if p is None else ("cumple" if p <= hc.presupuesto_max_clp else "falla")
    motivo[C_BUDGET] = f"precio {lectura('precio', h)} vs tope ${hc.presupuesto_max_clp:,}".replace(",", ".")

    if hc.mascota_especie is None:
        est[C_PETS], motivo[C_PETS] = "cumple", "el comprador no tiene mascota"
    elif h["mascotas"] == "no_explicita":
        est[C_PETS], motivo[C_PETS] = "no_verificable", "el aviso no declara política de mascotas"
    else:
        ok = (h["mascotas"] == "permitidas"
              and (not h["especies"] or hc.mascota_especie in h["especies"])
              and (h["mascotas_kg"] is None or hc.mascota_kg <= h["mascotas_kg"]))
        est[C_PETS] = "cumple" if ok else "falla"
        motivo[C_PETS] = (f"{lectura('mascotas', h)}, {lectura('mascotas_kg', h)} vs "
                          f"{hc.mascota_especie} de {hc.mascota_kg:g} kg")

    d = distancia(h)
    est[C_DISTANCE] = "no_verificable" if d is None else ("cumple" if d <= hc.distancia_max_transporte_m else "falla")
    motivo[C_DISTANCE] = f"{d if d is not None else '?'} m vs máximo {hc.distancia_max_transporte_m} m"

    b = h.get("dormitorios")
    est[C_BEDROOMS] = "no_verificable" if b is None else ("cumple" if b >= hc.dormitorios_min else "falla")
    motivo[C_BEDROOMS] = f"{b if b is not None else '?'} vs mínimo {hc.dormitorios_min}"

    pk = h.get("estacionamiento")
    if not hc.estacionamiento_requerido:
        est[C_PARKING] = "cumple"
    elif pk == "no_mencionado":
        est[C_PARKING] = "no_verificable"
    else:
        est[C_PARKING] = "cumple" if pk in ("propio", "asignado") else "falla"
    motivo[C_PARKING] = f"{pk} (requerido={'sí' if hc.estacionamiento_requerido else 'no'})"

    failed = [c for c in (C_BUDGET, C_PETS, C_DISTANCE, C_BEDROOMS, C_PARKING) if est[c] != "cumple"]
    roi = normalize.roi_pct(h["arriendo"], p) if p and h.get("arriendo") else None
    prefs = {_fold(x.strip()) for x in sc.ubicaciones_preferidas}
    return {"id": pid, "estado": est, "motivo": motivo, "failed_constraints": failed,
            "price_clp": p, "roi_pct": roi,
            "preferida": bool(h.get("comuna")) and _fold(h["comuna"].strip()) in prefs}


def ordenar(evals: List[Dict]) -> Dict:
    """JSON estricto de la E1: aprobadas por comuna preferida y luego ROI desc."""
    ok = [e for e in evals if not e["failed_constraints"]]
    ok.sort(key=lambda e: (e["preferida"], e["roi_pct"] is not None, e["roi_pct"] or 0.0), reverse=True)
    return {
        "approved_matches": [{"id": e["id"], "price_clp": e["price_clp"], "roi_pct": e["roi_pct"]} for e in ok],
        "rejected": [{"id": e["id"], "failed_constraints": e["failed_constraints"]}
                     for e in evals if e["failed_constraints"]],
    }
