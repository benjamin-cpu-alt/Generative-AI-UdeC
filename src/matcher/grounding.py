"""Anclaje (grounding) y parseo determinista de los SPANS que devuelve el extractor v5.

Principio: el LLM LOCALIZA, el código INTERPRETA. Lo que se le pide al modelo es
copiar el fragmento del aviso que habla de cada tema; aquí se comprueba que ese
fragmento exista de verdad en el aviso y se convierte a los campos de `Facts`.

Por qué existe este módulo (extract_report sobre tools_phi4_v1, test/, 352 propiedades):
  - los campos que el modelo debía INTERPRETAR concentran los errores: bedrooms 42
    ("3D/1B" -> 1; "1 dormitorio + sala convertible" -> 2), parking 10 (10/10 "en la
    calle" -> asignado), pets_species 12, pets_max_kg 4 ("hasta 6kg" -> null);
  - los campos que solo debía COPIAR fallan por alucinar la unidad o el número del
    ejemplo del prompt ("$126.100.000" -> "126.100.000 UF"; arriendo "$980.000").

Reglas de anclaje:
  - numéricos (precio, arriendo, distancia, kg): ESTRICTO. El número debe aparecer en
    el aviso; la unidad se lee del contexto del AVISO, nunca del modelo. Si no está,
    el campo queda vacío y la restricción se rechaza como "no verificable" (nunca se
    aprueba con un número inventado);
  - categóricos (dormitorios, estacionamiento, mascotas): se parsea la cláusula copiada;
    si no es literal del aviso se parsea igual pero se registra un warning en Facts.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

PARKING = ["propio", "asignado", "visitas", "calle", "ninguno", "no_mencionado"]
SPECIES = ("perro", "gato")
ANSWERS = ("si", "no", "no_dice")

_NUM = r"\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?"
_NUM_RE = re.compile(_NUM)
_DIST_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km|kms|kilómetros?|kilometros?|m|mts|metros?)\b", re.IGNORECASE)
_KG_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:kg|kilos?)\b", re.IGNORECASE)
_WORD_NUM = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}
_BED_RE = re.compile(r"\b(\d+|un|una|uno|dos|tres|cuatro|cinco|seis)\s*(?:d\b|dorm)", re.IGNORECASE)
# Fallback sobre el aviso completo cuando el modelo no localiza la cláusula: solo formas
# inequívocas ("3D/", "3 dormitorios"), nunca "N d" suelto.
_BED_STRICT_RE = re.compile(r"\b(\d+)\s*(?:D\s*/|dormitorios?\b)", re.IGNORECASE)
_STUDIO_RE = re.compile(r"\b(?:estudio|monoambiente|ambiente único|ambiente unico)\b", re.IGNORECASE)
_LOC_PREFIX_RE = re.compile(r"^\W*(?:depto\.?|departamento|casa|propiedad|ubicad[oa])?\s*(?:en)\s+", re.IGNORECASE)


# ------------------------------------------------------------- utilidades ----

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().casefold()


def clause_in_text(clause: Optional[str], text: str) -> bool:
    """La cláusula copiada aparece literalmente en el aviso (ignorando mayúsculas y espacios)."""
    return bool(clause) and _norm(clause) in _norm(text)


def clause_anchored(clause: Optional[str], text: str, min_ratio: float = 0.8) -> bool:
    """Anclaje tolerante para cláusulas categóricas: literal, o al menos `min_ratio` de sus
    palabras (≥4 letras) aparecen en el aviso. Acepta un typo de copia ("acceptamos mascotas")
    y rechaza una cláusula inventada ("acepta_mascotas: si, acepta_perros: si": 0 %)."""
    if clause_in_text(clause, text):
        return True
    words = [w for w in re.findall(r"[a-záéíóúñü]{4,}", _norm(clause or ""))]
    if len(words) < 3:
        return False
    present = set(re.findall(r"[a-záéíóúñü]{4,}", _norm(text)))
    return sum(w in present for w in words) / len(words) >= min_ratio


def _number_positions(num: str, text: str) -> List[Tuple[int, int]]:
    """Posiciones del número `num` en el texto como token completo ("143.500" no matchea
    dentro de "143.500.000", ni "1" dentro de "1.200")."""
    pat = re.compile(rf"(?<![\d.,]){re.escape(num)}(?![\d]|[.,]\d)")
    return [(m.start(), m.end()) for m in pat.finditer(text)]


# ---------------------------------------------------------------- dinero ----

def ground_money(span: Optional[str], text: str) -> Optional[str]:
    """Devuelve el monto anclado al aviso con la unidad que dice el AVISO, o None.

    "126.100.000 UF" con aviso "Valor $126.100.000"  -> "$126.100.000"  (unidad corregida)
    "$980.000/mes"   sin ese número en el aviso       -> None            (número inventado)
    """
    if not span:
        return None
    m = _NUM_RE.search(span)
    if not m:
        return None
    num = m.group(0)
    pos = _number_positions(num, text)
    if not pos:
        return None
    start, end = pos[0]
    before, after = text[max(0, start - 8):start], text[end:end + 6]
    if "UF" in before.upper() or "UF" in after.upper():
        return f"{num} UF"
    if "$" in before or "CLP" in after.upper() or "PESO" in after.upper():
        return f"${num}"
    return num  # sin unidad en el aviso: normalize.parse_money decide por magnitud


# -------------------------------------------------------------- distancia ----

def ground_distance(span: Optional[str], text: str) -> Optional[str]:
    """Primera distancia (m/km) del span cuyo número exista en el aviso, como "1,4 km".
    Los minutos caminando no son distancia y se ignoran solos (no matchean m/km)."""
    if not span:
        return None
    for m in _DIST_RE.finditer(span):
        num, unit = m.group(1), m.group(2)
        # el número debe estar en el aviso Y seguido de una unidad de distancia
        # ("100m" inventado no se ancla a "100% pet friendly")
        if re.search(rf"(?<![\d.,]){re.escape(num)}\s*(?:km|kms|kilómetros?|kilometros?|m|mts|metros?)\b",
                     text, re.IGNORECASE):
            return f"{num} {unit}"
    return None


# ------------------------------------------------------------- dormitorios ----

def parse_bedrooms(clause: Optional[str]) -> Optional[int]:
    """Dormitorios REALES a partir de la cláusula copiada.

    "3D/1B" -> 3 ; "2 dormitorios, 1 baño" -> 2 ; "1 dormitorio + sala que puede usarse
    como dormitorio adicional" -> 1 (solo cuenta el primer "N dormitorio(s)" / "ND") ;
    "estudio, ambiente único + loggia" -> 0 ; sin número -> None (no verificable).
    """
    if not clause:
        return None
    m = _BED_RE.search(clause)
    if m:
        tok = m.group(1).lower()
        return int(tok) if tok.isdigit() else _WORD_NUM[tok]
    if _STUDIO_RE.search(clause):
        return 0
    return None


# ---------------------------------------------------------- estacionamiento ----

def parse_parking(clause: Optional[str]) -> str:
    """Clasifica la cláusula de estacionamiento. El orden importa: "en la calle, sin
    problemas para aparcar" es `calle`, no `ninguno`."""
    if not clause:
        return "no_mencionado"
    s = clause.casefold()
    if not re.search(r"estacionamiento|parking|aparc|cochera", s):
        return "no_mencionado"
    if "calle" in s:
        return "calle"
    if "visita" in s:
        return "visitas"
    if re.search(r"\bsin\b|no incluye|no cuenta|no tiene|no dispone", s):
        return "ninguno"
    if "asignad" in s:
        return "asignado"
    return "propio"


# ---------------------------------------------------------------- mascotas ----

def parse_kg(clause: Optional[str], text: str) -> Optional[float]:
    """Límite de peso en kg declarado en la cláusula de mascotas, anclado al aviso."""
    if not clause:
        return None
    for m in _KG_RE.finditer(clause):
        num = m.group(1)
        if re.search(rf"(?<!\d){re.escape(num)}\s*(?:kg|kilos?)\b", text, re.IGNORECASE):
            return float(num.replace(",", "."))
    return None


def pets_from_answers(acepta_mascotas: str, acepta_perros: str, acepta_gatos: str
                      ) -> Tuple[str, List[str]]:
    """Tres preguntas cerradas -> (pets_policy, pets_species) en el formato de v1.

    Reformula la única decisión semántica que el modelo no puede evitar: con una lista
    bajo negación ("se aceptan gatos, perros no permitidos") phi4-mini devolvía ambas
    especies; con preguntas por especie la negación es local a cada respuesta.
    """
    ans = {"perro": acepta_perros, "gato": acepta_gatos}
    allowed = [s for s in SPECIES if ans[s] == "si"]
    denied = [s for s in SPECIES if ans[s] == "no"]
    if acepta_mascotas == "si" or allowed:
        policy = "permitidas"
    elif acepta_mascotas == "no" or len(denied) == len(SPECIES):
        policy = "no_permitidas"
    else:
        policy = "no_mencionada"
    if len(allowed) == len(SPECIES):
        species: List[str] = []                       # ambas: sin restricción de especie
    elif allowed:
        species = allowed
    elif denied:
        species = [s for s in SPECIES if s not in denied]
    else:
        species = []
    return policy, species


# --------------------------------------------------------------- ubicación ----

def parse_location(span: Optional[str], text: str) -> Optional[str]:
    """"Depto en Estación Central, 57m²" -> "Estación Central" (debe existir en el aviso)."""
    if not span:
        return None
    s = _LOC_PREFIX_RE.sub("", span.strip())
    s = re.split(r"[,.;(]|\s+\d", s, maxsplit=1)[0].strip()
    if not s or _norm(s) not in _norm(text):
        return None
    return s


# ------------------------------------------------------ spans -> Facts (v5) ----

SPAN_FIELDS = ("location_text", "bedrooms_text", "price_text", "rent_text", "distance_metro_text",
               "distance_bus_text", "parking_text", "pets_text")
ANSWER_FIELDS = ("acepta_mascotas", "acepta_perros", "acepta_gatos")


def facts_from_spans(obj: Dict, text: str) -> Tuple[Dict, List[str]]:
    """Convierte la salida v5 (spans + 3 respuestas) a los kwargs de `Facts` (formato v1),
    aplicando anclaje. Devuelve (kwargs, warnings)."""
    warnings: List[str] = []
    for k in SPAN_FIELDS:
        v = obj.get(k)
        if v and not clause_in_text(v, text):
            warnings.append(f"{k}: no es literal del aviso: {v!r}")

    price = ground_money(obj.get("price_text"), text)
    if obj.get("price_text") and price is None:
        warnings.append(f"price_text: número no está en el aviso: {obj.get('price_text')!r}")
    rent = ground_money(obj.get("rent_text"), text)
    if obj.get("rent_text") and rent is None:
        warnings.append(f"rent_text: número no está en el aviso: {obj.get('rent_text')!r}")

    # Mascotas: las tres respuestas cerradas solo valen si la cláusula que las respalda está
    # en el aviso. Sin cláusula anclada (o inventada, p.ej. copiando los nombres del esquema),
    # la política es "no mencionada": la decodificación restringida obliga a responder, y
    # una respuesta sin respaldo no puede aprobar nada.
    pets_text = obj.get("pets_text")
    pets_kg: Optional[float] = None
    if clause_anchored(pets_text, text):
        policy, species = pets_from_answers(*(obj.get(k) or "no_dice" for k in ANSWER_FIELDS))
        pets_kg = parse_kg(pets_text, text)
    else:
        policy, species = "no_mencionada", []
        if pets_text or any(obj.get(k) not in (None, "no_dice") for k in ANSWER_FIELDS):
            warnings.append("pets: respuestas sin cláusula anclada -> no_mencionada")

    # Dormitorios: si el modelo no localizó la cláusula (típico con "3D/1B"), se busca la
    # forma inequívoca en el aviso completo y se deja constancia.
    bedrooms = parse_bedrooms(obj.get("bedrooms_text"))
    if bedrooms is None:
        m = _BED_STRICT_RE.search(text)
        if m:
            bedrooms = int(m.group(1))
            warnings.append(f"bedrooms: recuperado del aviso completo ({m.group(0).strip()!r})")
        elif _STUDIO_RE.search(text):
            bedrooms = 0
            warnings.append("bedrooms: recuperado del aviso completo (estudio)")

    kwargs = {
        "location": parse_location(obj.get("location_text"), text),
        "bedrooms": bedrooms,
        "price_text": price or "",
        "rent_text": rent,
        "distance_metro_text": ground_distance(obj.get("distance_metro_text"), text),
        "distance_bus_text": ground_distance(obj.get("distance_bus_text"), text),
        "pets_policy": policy,
        "pets_species": species,
        "pets_max_kg": pets_kg,
        "parking": parse_parking(obj.get("parking_text")),
    }
    return kwargs, warnings
