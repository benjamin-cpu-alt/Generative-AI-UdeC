"""Tests de grounding.py (sin Ollama). Cada caso reproduce un error real observado en
results/tools_phi4_v1 (extract_report --show) y comprueba que la capa de anclaje/parseo
lo neutraliza sin necesitar que el modelo "razone" mejor.
"""
import pytest

from matcher import grounding
from matcher.constraints import decide
from matcher.extract import Facts
from matcher.schema import HardConstraints, SoftConstraints

AVISO_CLP = ("Depto en Macul, 55m², 1 dormitorio + sala de estar amplia que puede usarse como "
             "dormitorio adicional, 1B. Valor $126.100.000. A 2,3km de la estación de metro más "
             "cercana, pero cuenta con paradero de buses troncal a 901m. Comunidad pet friendly, "
             "aceptamos perros y gatos de cualquier tamaño. Incluye estacionamiento propio. "
             "Arriendo estimado: $980.000/mes.")
AVISO_UF = ("Casa en Estación Central, 91m², 3D/1B. Precio: 1.927 UF. Ubicado a 1,3 km de la "
            "estación Franklin, unos 16 minutos caminando. Se aceptan mascotas pequeñas y medianas "
            "hasta 6kg, previa autorización de la administración. Estacionamiento en la calle, sin "
            "problemas para aparcar en el sector. Arriendo estimado: $870.000/mes.")


# ------------------------------------------------------------- dinero anclado ----

@pytest.mark.parametrize("span,text,expected", [
    ("126.100.000 UF", AVISO_CLP, "$126.100.000"),     # v1: unidad alucinada -> se lee del aviso
    ("$126.100.000", AVISO_CLP, "$126.100.000"),
    ("1.927 UF", AVISO_UF, "1.927 UF"),
    ("Precio: 1.927 UF", AVISO_UF, "1.927 UF"),
    ("$980.000/mes", AVISO_UF, None),                  # número de ejemplo del prompt: no está
    ("$870.000/mes", AVISO_UF, "$870.000"),
    ("143.500", "Valor $143.500.000.", None),          # prefijo truncado no cuenta como el número
    (None, AVISO_CLP, None), ("", AVISO_CLP, None),
])
def test_ground_money(span, text, expected):
    assert grounding.ground_money(span, text) == expected


# ---------------------------------------------------------- distancia anclada ----

@pytest.mark.parametrize("span,text,expected", [
    ("Ubicado a 1,3 km de la estación Franklin, unos 16 minutos caminando", AVISO_UF, "1,3 km"),
    ("unos 16 minutos caminando", AVISO_UF, None),
    ("100m", "A 325m de la estación. 100% pet friendly.", None),   # v1 inventó "100m"
    ("A 325m de la estación", "A 325m de la estación. 100% pet friendly.", "325 m"),
    ("paradero de buses troncal a 901m", AVISO_CLP, "901 m"),
    (None, AVISO_CLP, None),
])
def test_ground_distance(span, text, expected):
    assert grounding.ground_distance(span, text) == expected


# ------------------------------------------------------------------ dormitorios ----

@pytest.mark.parametrize("clause,expected", [
    ("3D/1B", 3), ("4D/2B", 4), ("1D/1B", 1),                       # v1 tomaba los baños
    ("2 dormitorios, 1 baño", 2), ("dos dormitorios", 2),
    ("1 dormitorio + sala de estar amplia que puede usarse como dormitorio adicional, 1B", 1),
    ("1 dormitorio + escritorio (walk-in office, fácilmente convertible en segundo dormitorio), 1B", 1),
    ("estudio, ambiente único + loggia cerrada, ideal como pieza extra, 1B", 0),
    ("Depto estudio en Maipú, 53m², ambiente único + sala de estar amplia", 0),
    ("luminoso, orientación norte", None), (None, None),
])
def test_parse_bedrooms(clause, expected):
    assert grounding.parse_bedrooms(clause) == expected


# -------------------------------------------------------------- estacionamiento ----

@pytest.mark.parametrize("clause,expected", [
    ("Estacionamiento en la calle, sin problemas para aparcar en el sector.", "calle"),  # v1 -> asignado
    ("Estacionamiento de visitas disponible.", "visitas"),
    ("Sin estacionamiento.", "ninguno"), ("No incluye estacionamiento.", "ninguno"),
    ("Incluye 1 estacionamiento techado asignado.", "asignado"),
    ("Incluye estacionamiento propio.", "propio"),
    ("Cuenta con 1 estacionamiento en subterráneo, valor incluido en el precio.", "propio"),
    ("Piso alto, orientación norte.", "no_mencionado"), (None, "no_mencionado"),
])
def test_parse_parking(clause, expected):
    assert grounding.parse_parking(clause) == expected


# --------------------------------------------------------------------- mascotas ----

@pytest.mark.parametrize("clause,text,expected", [
    ("Se aceptan mascotas pequeñas y medianas hasta 6kg, previa autorización", AVISO_UF, 6.0),  # v1 -> null
    ("Pet friendly con límite de 25kg por mascota.", "Pet friendly con límite de 25kg por mascota.", 25.0),
    ("aceptamos perros y gatos de cualquier tamaño", AVISO_CLP, None),
    ("hasta 20kg", AVISO_UF, None),                                   # 20kg no está en este aviso
    (None, AVISO_UF, None),
])
def test_parse_kg(clause, text, expected):
    assert grounding.parse_kg(clause, text) == expected


@pytest.mark.parametrize("answers,expected", [
    (("si", "no", "si"), ("permitidas", ["gato"])),        # "se aceptan gatos, perros no permitidos"
    (("si", "si", "no_dice"), ("permitidas", ["perro"])),  # "solo se admiten perros"
    (("si", "si", "si"), ("permitidas", [])),              # sin restricción de especie
    (("si", "no_dice", "no_dice"), ("permitidas", [])),    # "pet friendly" a secas
    (("no", "no", "no"), ("no_permitidas", [])),
    (("no_dice", "no", "no"), ("no_permitidas", [])),
    (("no_dice", "no_dice", "no_dice"), ("no_mencionada", [])),
    (("no_dice", "no", "no_dice"), ("no_mencionada", ["gato"])),
])
def test_pets_from_answers(answers, expected):
    assert grounding.pets_from_answers(*answers) == expected


# ---------------------------------------------------------------------- ubicación ----

@pytest.mark.parametrize("span,text,expected", [
    ("Depto en Macul, 55m²", AVISO_CLP, "Macul"),
    ("Casa en Estación Central", AVISO_UF, "Estación Central"),     # v1 devolvía '' o 'providencia'
    ("Estación Central", AVISO_UF, "Estación Central"),
    ("Providencia", AVISO_UF, None),                                # no está en el aviso
    (None, AVISO_UF, None),
])
def test_parse_location(span, text, expected):
    assert grounding.parse_location(span, text) == expected


# --------------------------------------------------- spans -> Facts -> decisión ----

HC = HardConstraints(presupuesto_max_clp=165_000_000, mascota_especie="perro", mascota_kg=15,
                     distancia_max_transporte_m=1000, dormitorios_min=2, estacionamiento_requerido=True)
SC = SoftConstraints(ubicaciones_preferidas=["Macul"])


def test_facts_from_spans_end_to_end_rejects_convertible_bedroom():
    """test_0039 / PROP-Q61: con v1 la M4 'acertó' por cancelación (precio alucinado en UF)
    y la RTX aprobó indebidamente. Con spans anclados el precio es correcto Y se rechaza
    por dormitorios, que es la razón real."""
    spans = {
        "location_text": "Depto en Macul",
        "bedrooms_text": "1 dormitorio + sala de estar amplia que puede usarse como dormitorio adicional, 1B",
        "price_text": "126.100.000 UF",                       # el modelo alucina la unidad
        "rent_text": "$980.000/mes",
        "distance_metro_text": "A 2,3km de la estación de metro más cercana",
        "distance_bus_text": "paradero de buses troncal a 901m",
        "parking_text": "Incluye estacionamiento propio.",
        "pets_text": "Comunidad pet friendly, aceptamos perros y gatos de cualquier tamaño.",
        "acepta_mascotas": "si", "acepta_perros": "si", "acepta_gatos": "si",
    }
    kwargs, warnings = grounding.facts_from_spans(spans, AVISO_CLP)
    assert kwargs["price_text"] == "$126.100.000"
    assert kwargs["bedrooms"] == 1
    assert kwargs["parking"] == "propio" and kwargs["pets_species"] == []
    assert any(w.startswith("price_text: no es literal") for w in warnings)   # queda registrado
    assert not any("número no está" in w for w in warnings)                  # pero el número sí está
    d = decide("PROP-Q61", Facts(**kwargs), HC, SC, uf_value=38_850)
    assert d.price_clp == 126_100_000
    assert d.failed_constraints == ["dormitorios"]
    assert d.roi_pct == 9.33 and d.preferred_location


def test_facts_from_spans_unverifiable_never_approves():
    """Número inventado -> campo vacío -> la restricción falla como no verificable."""
    spans = {k: None for k in grounding.SPAN_FIELDS}
    spans.update({"price_text": "$150.000.000", "bedrooms_text": "amplio y luminoso",
                  "acepta_mascotas": "no_dice", "acepta_perros": "no_dice", "acepta_gatos": "no_dice"})
    kwargs, warnings = grounding.facts_from_spans(spans, "Depto en Macul, amplio. Precio: 3.900 UF.")
    assert kwargs["price_text"] == "" and kwargs["bedrooms"] is None
    assert any(w.startswith("price_text") for w in warnings)
    d = decide("PROP-X", Facts(**kwargs), HC, SC, uf_value=38_850)
    assert not d.approved
    assert {"presupuesto", "dormitorios", "mascotas", "distancia_transporte", "estacionamiento"} <= set(d.failed_constraints)


def test_bedrooms_fallback_recovers_compact_notation_and_records_it():
    """dev v5: el modelo devuelve null en 27/211 avisos con "3D/1B"; el parser lo recupera
    del aviso completo (solo formas inequívocas) y deja constancia en warnings."""
    spans = {k: None for k in grounding.SPAN_FIELDS}
    spans.update({"acepta_mascotas": "no_dice", "acepta_perros": "no_dice", "acepta_gatos": "no_dice"})
    kwargs, warnings = grounding.facts_from_spans(spans, "Depto en Macul, 2D/1B. Precio: 3.900 UF.")
    assert kwargs["bedrooms"] == 2 and any(w.startswith("bedrooms: recuperado") for w in warnings)
    kwargs, _ = grounding.facts_from_spans(spans, "Depto en Macul. A 2 de la estación.")
    assert kwargs["bedrooms"] is None                       # "2 de" no es dormitorios


@pytest.mark.parametrize("clause,answers,expected_policy", [
    ("acceptamos mascotas sin restricciones de raza o tamaño", ("si", "si", "si"), "permitidas"),  # typo de copia
    ("acepta_mascotas: si, acepta_perros: si, acepta_gatos: si", ("si", "si", "si"), "no_mencionada"),  # inventada
    (None, ("si", "si", "si"), "no_mencionada"),                                                 # sin cláusula
])
def test_pets_answers_need_an_anchored_clause(clause, answers, expected_policy):
    """train_0009: sin política de mascotas en el aviso, el modelo rellenó pets_text con los
    nombres del esquema y respondió "si" (decodificación restringida obliga a responder)."""
    text = "Depto en Macul, 2D/1B. Edificio pet friendly, aceptamos mascotas sin restricciones de raza o tamaño."
    if clause is None or "acepta_" in clause:
        text = "Depto en Macul, 2D/1B. Precio: 3.900 UF."
    spans = {k: None for k in grounding.SPAN_FIELDS}
    spans.update({"pets_text": clause, "acepta_mascotas": answers[0], "acepta_perros": answers[1], "acepta_gatos": answers[2]})
    kwargs, _ = grounding.facts_from_spans(spans, text)
    assert kwargs["pets_policy"] == expected_policy
