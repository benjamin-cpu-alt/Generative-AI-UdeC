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

Versiones de la capa (`version=`), para que cada corrida siga siendo reproducible:
  g1  la capa con la que se corrió results/tools_phi4_v5*: anclaje + parsers, con
      recuperación desde el aviso SOLO para dormitorios.
  g2  (por defecto) añade dos mecanismos derivados del análisis de los 11 fallos de
      tools_phi4_v5, todos rechazos falsos o de ranking:
        A. recuperación de cláusula: si el span no ancla (el modelo parafraseó, copió
           el nombre del campo o se llevó la mitad equivocada de la frase), el código
           localiza la frase del tema en el aviso y la usa. Extiende a mascotas,
           estacionamiento, distancias y ubicación el fallback que g1 ya hacía con
           dormitorios.
        B. especies por parseo: la lista de especies se lee de la cláusula anclada
           ("Solo se admiten gatos" -> ['gato']) en vez de las respuestas del modelo,
           que confunden exclusividad con prohibición. Las respuestas del modelo se
           usan solo si el parser no reconoce el patrón.
      Ambos mecanismos dejan constancia en `warnings`: son medibles, no invisibles.
  g3  (por defecto) tres correcciones de SEGURIDAD encontradas al correr g2 sobre el set
      OOD escrito a mano. Las tres solo pueden QUITAR aprobaciones, nunca añadirlas, y
      ninguna cambia un solo veredicto en test/ ni en dev (la ruta que corrigen no se
      activa con los avisos del generador; se verificó comparando las salidas):
        1. "135 millones" se entiende como 135.000.000 CLP (formato estándar en Chile);
        2. si el aviso no declara la unidad junto al número, el precio queda NO VERIFICABLE
           en vez de adivinarse por magnitud. Adivinarla convirtió "piden 135 millones" en
           135 UF = $5,2 M y aprobó dos propiedades fuera de presupuesto;
        3. "Estacionamiento opcional, se arrienda aparte" deja de caer en la rama por
           defecto `propio`: la unidad no lo incluye;
        4. en una distancia, "1.500 mts" son 1500 m y no 1,5 m. El punto de miles se leía
           como decimal y aprobaba una propiedad a 1,5 km del metro (OOD-803);
        5. "UF 4.250,5" se ancla completo (miles y decimales a la vez). Este último SÍ
           puede añadir una aprobación, pero corrige una inconsistencia con
           normalize.parse_number, que siempre aceptó ese formato.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

PARKING = ["propio", "asignado", "visitas", "calle", "ninguno", "no_mencionado"]
SPECIES = ("perro", "gato")
ANSWERS = ("si", "no", "no_dice")

_NUM = r"\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?"
_NUM_RE = re.compile(_NUM)
# Igual que el anterior pero admitiendo decimales DESPUÉS del separador de miles:
# "UF 4.250,5". El de arriba corta en "4.250" y luego el anclaje rechaza el número
# porque en el aviso viene seguido de ",5" (g3 corrige esta inconsistencia con
# normalize.parse_number, que sí acepta el formato completo).
_NUM_RE_DEC = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
# En una distancia, un punto seguido de EXACTAMENTE tres dígitos es separador de miles,
# no decimal: "1.500 mts" son 1500 m, no 1,5 m (que es lo que leía g1/g2).
_THOUSANDS_RE = re.compile(r"(?<=\d)\.(?=\d{3}\b)")
_DIST_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km|kms|kilómetros?|kilometros?|m|mts|metros?)\b", re.IGNORECASE)
_KG_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:kg|kilos?)\b", re.IGNORECASE)
_WORD_NUM = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}
_BED_RE = re.compile(r"\b(\d+|un|una|uno|dos|tres|cuatro|cinco|seis)\s*(?:d\b|dorm)", re.IGNORECASE)
# Fallback sobre el aviso completo cuando el modelo no localiza la cláusula: solo formas
# inequívocas ("3D/", "3 dormitorios"), nunca "N d" suelto.
_BED_STRICT_RE = re.compile(r"\b(\d+)\s*(?:D\s*/|dormitorios?\b)", re.IGNORECASE)
_STUDIO_RE = re.compile(r"\b(?:estudio|monoambiente|ambiente único|ambiente unico)\b", re.IGNORECASE)
_LOC_PREFIX_RE = re.compile(r"^\W*(?:depto\.?|departamento|casa|propiedad|ubicad[oa])?\s*(?:en)\s+", re.IGNORECASE)
_LOC_IN_AD_RE = re.compile(r"\b(?:depto\.?|dpto\.?|departamento|casa|propiedad)\b[^.]{0,40}?\ben\s+"
                           r"([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ]*){0,2})",
                           re.IGNORECASE)

# --- A: recuperación de cláusula desde el aviso ---------------------------
# Palabras que identifican la frase de cada tema. El código NO adivina el valor: busca
# la oración donde el aviso habla del tema y la parsea con el mismo parser de siempre.
TOPIC_WORDS = {
    "pets_text": r"mascota|pet\s*friendly|gatos?|perros?|\d+\s*(?:kg|kilos?)",
    "parking_text": r"estacionamiento|estacionamento|parking|aparc|cochera|\best\.",
    "distance_metro_text": r"metro|estaci[óo]n",
    "distance_bus_text": r"paradero|buses|troncal|transantiago",
}


# La coma chilena separa oraciones PERO también decimales ("2,1km"): solo se corta en una
# coma que no vaya seguida de un dígito.
_SENT_SPLIT = re.compile(r"(?<=\.)\s+|\n+")
_CLAUSE_SPLIT = re.compile(r"(?<=\.)\s+|\n+|;|,(?!\d)| y (?=[a-záéíóú])| pero ")


def topic_fragments(text: str, topic: str, clauses: bool = False) -> List[str]:
    """Fragmentos del aviso que hablan de `topic`, en orden de aparición.

    `clauses=False` devuelve oraciones completas (lo que necesitan los parsers de mascotas
    y estacionamiento, que leen la frase entera). `clauses=True` corta además por comas y
    "y"/"pero": lo necesitan las distancias, porque "A 1.100 metros del metro, pero a 400
    metros de paradero troncal" son dos datos distintos en una sola oración.

    Devuelve TODOS los fragmentos, no el primero: "Depto en Estación Central, 73m², 2
    dormitorios" contiene la palabra "estación" sin ser la frase de la distancia, así que
    quien llama debe quedarse con el primer fragmento del que sí obtiene un valor.
    """
    words = TOPIC_WORDS.get(topic)
    if not words:
        return []
    splitter = _CLAUSE_SPLIT if clauses else _SENT_SPLIT
    return [f.strip() for f in splitter.split(text)
            if f and f.strip() and re.search(words, f, re.IGNORECASE)]


def topic_sentence(text: str, topic: str) -> Optional[str]:
    """La primera oración del aviso que habla de `topic`, o None."""
    frags = topic_fragments(text, topic)
    return frags[0] if frags else None


def recover_distance(text: str, topic: str, thousands: bool = False) -> Optional[str]:
    """Primera cláusula del tema de la que se obtiene una distancia anclada al aviso."""
    for frag in topic_fragments(text, topic, clauses=True):
        d = ground_distance(frag, text, thousands)
        if d is not None:
            return d
    return None


# --- B: especies a partir de la cláusula ----------------------------------
_NEG_RE = re.compile(r"\bno\s+(?:se\s+)?(?:se\s+)?(?:aceptan?|admiten?|permite[ns]?|permitid[oa]s?|"
                     r"est[áa][ns]?)|prohibid|\bsin\s+mascotas?|no\s+permitid", re.IGNORECASE)
_POS_RE = re.compile(r"acepta|admite|permit|pet\s*friendly|bienvenid", re.IGNORECASE)
_SPECIES_RE = {"perro": re.compile(r"\bperr[oa]s?\b", re.IGNORECASE),
               "gato": re.compile(r"\bgat[oa]s?\b", re.IGNORECASE)}


def parse_species(clause: Optional[str]) -> Optional[Tuple[bool, List[str]]]:
    """(¿acepta mascotas?, especies permitidas) leídos de la cláusula, o None si el
    patrón no se reconoce (entonces se usan las respuestas del modelo).

    Regla: se parte la cláusula en segmentos y cada uno se marca positivo o negativo.
    Las especies nombradas en segmentos positivos son las permitidas; las nombradas en
    negativos quedan excluidas. Nombrar UNA especie en positivo ya restringe a esa
    especie ("Acepta gatos hasta 4 kilos" -> ['gato']); nombrar ambas, o ninguna, no
    restringe ([]). Un segmento negativo sin especie ("No se aceptan mascotas") niega
    todo, salvo que otro segmento permita una especie explícitamente.
    """
    if not clause:
        return None
    allowed: List[str] = []
    denied: List[str] = []
    global_pos = global_neg = False
    for seg in re.split(r"[;,.]| pero | aunque ", clause):
        if not seg.strip():
            continue
        neg = bool(_NEG_RE.search(seg))
        pos = bool(_POS_RE.search(seg))
        if not (neg or pos):
            continue
        here = [sp for sp, rx in _SPECIES_RE.items() if rx.search(seg)]
        if neg:
            global_neg = True
            denied += here
        else:
            global_pos = True
            allowed += here
    if not (global_pos or global_neg):
        return None
    allowed = [sp for sp in allowed if sp not in denied]
    if global_neg and not global_pos and not allowed:
        return False, []                       # negativa global: no se aceptan mascotas
    if global_neg and not allowed and not denied:
        return False, []
    if not global_pos and not allowed:
        return False, []
    species = [] if len(set(allowed)) == len(SPECIES) or not allowed else sorted(set(allowed))
    return True, species


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

def ground_money(span: Optional[str], text: str, millions: bool = False,
                 require_unit: bool = False, decimals: bool = False) -> Optional[str]:
    """Devuelve el monto anclado al aviso con la unidad que dice el AVISO, o None.

    "126.100.000 UF" con aviso "Valor $126.100.000"  -> "$126.100.000"  (unidad corregida)
    "$980.000/mes"   sin ese número en el aviso       -> None            (número inventado)

    `millions` (g3): reconoce "135 millones" como 135.000.000 CLP.
    `require_unit` (g3): si el aviso no declara la unidad junto al número, devuelve None
    en vez de dejar que `parse_money` la adivine por magnitud. Adivinarla es lo que hizo
    que "piden 135 millones" se leyera como 135 UF = $5,2 M y se aprobara una propiedad
    fuera de presupuesto (OOD-204, OOD-303).
    `decimals` (g3): acepta "UF 4.250,5" (miles y decimales a la vez).
    """
    if not span:
        return None
    m = (_NUM_RE_DEC if decimals else _NUM_RE).search(span)
    if not m:
        return None
    num = m.group(0)
    pos = _number_positions(num, text)
    if not pos:
        return None
    start, end = pos[0]
    before, after = text[max(0, start - 8):start], text[end:end + 12]
    if "UF" in before.upper() or "UF" in after.upper():
        return f"{num} UF"
    if millions and re.search(r"^\s*(?:mill[oó]n|millones)", after, re.IGNORECASE):
        return f"${num} millones" if "$" in before else f"{num} millones"
    if "$" in before or "CLP" in after.upper() or "PESO" in after.upper():
        return f"${num}"
    return None if require_unit else num


# -------------------------------------------------------------- distancia ----

def ground_distance(span: Optional[str], text: str, thousands: bool = False) -> Optional[str]:
    """Primera distancia (m/km) del span cuyo número exista en el aviso, como "1,4 km".
    Los minutos caminando no son distancia y se ignoran solos (no matchean m/km).

    `thousands` (g3): quita el separador de miles antes de devolver el valor, para que
    "1.500 mts" llegue a `normalize.parse_distance_m` como "1500 mts" y se lea 1500 m.
    Sin esto se leía 1,5 m y aprobaba una propiedad a 1,5 km del metro (OOD-803).
    """
    if not span:
        return None
    for m in _DIST_RE.finditer(span):
        num, unit = m.group(1), m.group(2)
        # el número debe estar en el aviso Y seguido de una unidad de distancia
        # ("100m" inventado no se ancla a "100% pet friendly")
        if re.search(rf"(?<![\d.,]){re.escape(num)}\s*(?:km|kms|kilómetros?|kilometros?|m|mts|metros?)\b",
                     text, re.IGNORECASE):
            return f"{_THOUSANDS_RE.sub('', num) if thousands else num} {unit}"
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

# Señales de que el estacionamiento NO viene con la unidad aunque la frase lo mencione
# ("Estacionamiento opcional, se arrienda aparte a $50.000 mensuales" -> no lo incluye).
_PARKING_NOT_INCLUDED = re.compile(r"opcional|se arrienda|arriendo aparte|\baparte\b|"
                                   r"por separado|valor adicional|costo adicional|no incluid",
                                   re.IGNORECASE)


def parse_parking(clause: Optional[str], strict: bool = False) -> str:
    """Clasifica la cláusula de estacionamiento. El orden importa: "en la calle, sin
    problemas para aparcar" es `calle`, no `ninguno`.

    `strict` (g3): (a) una cláusula que menciona estacionamiento pero declara que se
    arrienda aparte o es opcional es `ninguno` — sin esto el caso cae en la rama por
    defecto `propio` y aprueba (OOD-902): el defecto era que la rama permisiva fuera la
    de descarte; (b) reconoce la errata "estacionamento", frecuente en avisos reales.
    """
    if not clause:
        return "no_mencionado"
    s = clause.casefold()
    known = r"estacionamiento|estacionamento|parking|aparc|cochera" if strict else \
            r"estacionamiento|parking|aparc|cochera"
    if not re.search(known, s):
        return "no_mencionado"
    if "calle" in s:
        return "calle"
    if "visita" in s:
        return "visitas"
    if re.search(r"\bsin\b|no incluye|no cuenta|no tiene|no dispone", s):
        return "ninguno"
    if strict and _PARKING_NOT_INCLUDED.search(s):
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
VERSIONS = ("g1", "g2", "g3")
DEFAULT_VERSION = "g3"


def facts_from_spans(obj: Dict, text: str, version: str = DEFAULT_VERSION) -> Tuple[Dict, List[str]]:
    """Convierte la salida v5 (spans + 3 respuestas) a los kwargs de `Facts` (formato v1),
    aplicando anclaje. Devuelve (kwargs, warnings). `version`: ver el docstring del módulo."""
    if version not in VERSIONS:
        raise ValueError(f"versión de grounding desconocida: {version} (usa {'|'.join(VERSIONS)})")
    g2 = version in ("g2", "g3")
    g3 = version == "g3"
    warnings: List[str] = []

    def anchored(field: str, topic: Optional[str] = None) -> Optional[str]:
        """El span copiado si ancla; si no y estamos en g2, la frase del aviso que habla
        del tema. Deja constancia de cuál de las dos se usó."""
        span = obj.get(field)
        if span and clause_in_text(span, text):
            return span
        if span:
            warnings.append(f"{field}: no es literal del aviso: {span!r}")
        if not g2 or topic is None:
            return span
        recovered = topic_sentence(text, topic)
        if recovered is not None:
            warnings.append(f"{field}: recuperado del aviso ({recovered[:48]!r})")
        return recovered

    # --- dinero: el número debe estar en el aviso y la unidad se lee del aviso -------
    price_span = obj.get("price_text")
    if price_span and not clause_in_text(price_span, text):
        warnings.append(f"price_text: no es literal del aviso: {price_span!r}")
    price = ground_money(price_span, text, millions=g3, require_unit=g3, decimals=g3)
    if price_span and price is None:
        warnings.append(f"price_text: número no está en el aviso: {price_span!r}")
    rent_span = obj.get("rent_text")
    if rent_span and not clause_in_text(rent_span, text):
        warnings.append(f"rent_text: no es literal del aviso: {rent_span!r}")
    rent = ground_money(rent_span, text, millions=g3, decimals=g3)
    if rent_span and rent is None:
        warnings.append(f"rent_text: número no está en el aviso: {rent_span!r}")

    # --- distancias: si el span no da un número anclado, se recupera la frase --------
    metro = ground_distance(obj.get("distance_metro_text"), text, thousands=g3)
    if metro is None and g2:
        metro = recover_distance(text, "distance_metro_text", thousands=g3)
        if metro is not None:
            warnings.append(f"distance_metro_text: recuperada del aviso ({metro})")
    bus = ground_distance(obj.get("distance_bus_text"), text, thousands=g3)
    if bus is None and g2:
        bus = recover_distance(text, "distance_bus_text", thousands=g3)
        if bus is not None:
            warnings.append(f"distance_bus_text: recuperada del aviso ({bus})")

    # --- mascotas: cláusula anclada (o recuperada) + especies por parseo -------------
    pets_clause = obj.get("pets_text")
    pets_ok_clause = clause_anchored(pets_clause, text)
    if not pets_ok_clause and g2:
        recovered = topic_sentence(text, "pets_text")
        if recovered:
            warnings.append(f"pets_text: recuperado del aviso ({recovered[:48]!r})")
            pets_clause, pets_ok_clause = recovered, True
    pets_kg: Optional[float] = None
    if pets_ok_clause:
        answers = tuple(obj.get(k) or "no_dice" for k in ANSWER_FIELDS)
        policy, species = pets_from_answers(*answers)
        parsed = parse_species(pets_clause) if g2 else None
        if parsed is not None:
            allowed, parsed_species = parsed
            new_policy = "permitidas" if allowed else "no_permitidas"
            if (new_policy, parsed_species) != (policy, species):
                warnings.append(f"pets: parser={new_policy}/{parsed_species or 'cualquiera'} "
                                f"reemplaza al modelo={policy}/{species or 'cualquiera'}")
            policy, species = new_policy, parsed_species
        pets_kg = parse_kg(pets_clause, text)
    else:
        policy, species = "no_mencionada", []
        if pets_clause or any(obj.get(k) not in (None, "no_dice") for k in ANSWER_FIELDS):
            warnings.append("pets: respuestas sin cláusula anclada -> no_mencionada")

    # --- dormitorios: cláusula copiada, y si no da número, el aviso completo ---------
    bedrooms = parse_bedrooms(obj.get("bedrooms_text"))
    if bedrooms is None:
        m = _BED_STRICT_RE.search(text)
        if m:
            bedrooms = int(m.group(1))
            warnings.append(f"bedrooms: recuperado del aviso completo ({m.group(0).strip()!r})")
        elif _STUDIO_RE.search(text):
            bedrooms = 0
            warnings.append("bedrooms: recuperado del aviso completo (estudio)")

    # --- estacionamiento y ubicación --------------------------------------------------
    parking_clause = anchored("parking_text", "parking_text" if g2 else None)
    location = parse_location(obj.get("location_text"), text)
    if location is None and g2:
        m = _LOC_IN_AD_RE.search(text)
        if m:
            location = m.group(1).strip()
            warnings.append(f"location_text: recuperada del aviso ({location!r})")

    kwargs = {
        "location": location,
        "bedrooms": bedrooms,
        "price_text": price or "",
        "rent_text": rent,
        "distance_metro_text": metro,
        "distance_bus_text": bus,
        "pets_policy": policy,
        "pets_species": species,
        "pets_max_kg": pets_kg,
        "parking": parse_parking(parking_clause, strict=g3),
    }
    return kwargs, warnings
