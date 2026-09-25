"""Tests de los dos mecanismos que g2 añade sobre g1 (ver grounding.py):

  A. recuperación de cláusula: si el span copiado no ancla en el aviso, el código localiza
     la frase del tema y la usa;
  B. especies por parseo de la cláusula, en vez de las tres respuestas del modelo.

Cada caso viene de un fallo observado en results/tools_phi4_v5 (test) o dev_tools_v5 (dev).
Los tests de g1 siguen en test_grounding.py: g1 no debe cambiar nunca, porque es la capa con
la que se produjeron los resultados ya publicados.
"""
import pytest

from matcher import grounding as g
from matcher.constraints import decide
from matcher.extract import Facts
from matcher.schema import HardConstraints, SoftConstraints

# test_0012: la frase "Depto en Estación Central" contiene la palabra clave del tema
# distancia sin ser la frase de la distancia.
AD_EST_CENTRAL = ("Depto en Estación Central, 73m², 2 dormitorios, 1 baño. Valor $178.900.000. "
                  "Ideal para inversionistas. A 285m de la estación de metro Lo Vial. Se aceptan "
                  "mascotas pequeñas y medianas hasta 4kg, previa autorización de la "
                  "administración. Incluye estacionamiento propio. Arriendo estimado: "
                  "$1.360.000/mes.")
AD_DOS_DIST = ("Casa 3D/2B, 98 m². $150.000.000. A 1.100 metros del metro, pero a 400 metros de "
               "paradero troncal. Acepta gatos y perros. Estacionamiento propio.")
AD_SOLO_GATOS = ("Depto en La Cisterna, 96m², 4D/1B. Valor $74.100.000. A 2,1km de la estación de "
                 "metro más cercana, pero cuenta con paradero de buses troncal a 691m. Solo se "
                 "admiten gatos de cualquier tamaño. Cuenta con estacionamiento propio.")


# ------------------------------------------------ A · recuperación de cláusula ----

@pytest.mark.parametrize("text,topic,expected", [
    (AD_EST_CENTRAL, "distance_metro_text", "285 m"),       # no la comuna "Estación Central"
    (AD_DOS_DIST, "distance_metro_text", "1.100 metros"),
    (AD_DOS_DIST, "distance_bus_text", "400 metros"),       # la coma separa los dos datos
    (AD_SOLO_GATOS, "distance_metro_text", "2,1 km"),       # la coma decimal NO separa
    (AD_SOLO_GATOS, "distance_bus_text", "691 m"),
    ("Depto 2D/1B. A 12 minutos caminando del metro.", "distance_metro_text", None),
    ("Depto 2D/1B. A pasos del Metro Cerro Blanco, unos 5 minutos a pie.",
     "distance_metro_text", None),                          # "a pasos" no es una distancia
])
def test_recover_distance(text, topic, expected):
    assert g.recover_distance(text, topic) == expected


def test_topic_fragments_devuelve_todos_los_candidatos():
    """No basta el primer fragmento que menciona el tema: hay que poder descartarlo."""
    frags = g.topic_fragments(AD_EST_CENTRAL, "distance_metro_text", clauses=True)
    assert len(frags) >= 2 and frags[0].startswith("Depto en Estación Central")
    assert any("285m" in f for f in frags)


@pytest.mark.parametrize("span", [
    "acepta_mascotas: si",                    # test_0050: copió el nombre del campo
    "acceptamos mascotas sin restricciones",  # errata de copia
    None,                                     # no copió nada
])
def test_pets_recuperado_cuando_el_span_no_ancla(span):
    """El aviso SÍ tiene política de mascotas; el span del modelo no sirve. g2 la recupera;
    g1 se queda sin cláusula y rechaza (falso negativo)."""
    text = ("Casa en Peñalolén, 103m², 4D/1B. Precio: UF 4.900. A 375m de la estación de metro "
            "Príncipe de Gales. 100% pet friendly, sin restricciones de tamaño ni especie. "
            "Incluye estacionamiento propio.")
    spans = {k: None for k in g.SPAN_FIELDS}
    spans.update({"pets_text": span, "acepta_mascotas": "si",
                  "acepta_perros": "no_dice", "acepta_gatos": "no_dice"})
    assert g.facts_from_spans(spans, text, "g1")[0]["pets_policy"] == "no_mencionada"
    kwargs, warnings = g.facts_from_spans(spans, text, "g2")
    assert kwargs["pets_policy"] == "permitidas" and kwargs["pets_species"] == []
    assert any("recuperado del aviso" in w for w in warnings)


def test_location_recuperada_cuando_el_modelo_corrompe_la_tilde():
    """test_0023 / test_0044: el modelo devolvió 'Casa en Maipÿu'. Sin comuna el ranking
    por soft constraints queda mal, aunque el conjunto aprobado sea correcto."""
    text = "Casa en Maipú, 80m², 3D/1B. Precio: 2869 UF. A 703m de la estación de metro Tobalaba."
    spans = {k: None for k in g.SPAN_FIELDS}
    spans.update({"location_text": "Casa en Maipÿu, 80m², 3D/1B.",
                  "acepta_mascotas": "no_dice", "acepta_perros": "no_dice", "acepta_gatos": "no_dice"})
    assert g.facts_from_spans(spans, text, "g1")[0]["location"] is None
    assert g.facts_from_spans(spans, text, "g2")[0]["location"] == "Maipú"


# --------------------------------------------------- B · especies por parseo ----

@pytest.mark.parametrize("clause,expected", [
    ("Solo se admiten gatos de cualquier tamaño.", (True, ["gato"])),
    ("Solo se admiten perros de cualquier tamaño", (True, ["perro"])),
    ("Se aceptan gatos, perros no permitidos por reglamento de copropiedad.", (True, ["gato"])),
    ("Prohibido mantener perros; gatos sí están permitidos.", (True, ["gato"])),
    ("Acepta gatos hasta 4 kilos.", (True, ["gato"])),
    ("Perros bienvenidos.", (True, ["perro"])),
    ("Comunidad pet friendly, aceptamos perros y gatos de cualquier tamaño.", (True, [])),
    ("100% pet friendly, sin restricciones de tamaño ni especie.", (True, [])),
    ("Se aceptan mascotas pequeñas y medianas hasta 6kg, previa autorización.", (True, [])),
    ("El condominio no acepta mascotas.", (False, [])),
    ("NO SE ACEPTAN MASCOTAS.", (False, [])),
    # sin marcador de aceptación/prohibición el parser se abstiene y manda el modelo
    ("No se especifica política de mascotas.", None),
    ("Piso alto, orientación norte.", None),
    ("Solo gatos", None),
    (None, None),
])
def test_parse_species(clause, expected):
    assert g.parse_species(clause) == expected


def test_solo_se_admiten_gatos_g1_rechaza_g2_aprueba():
    """El fallo dominante de v5/g1 en test: con la cláusula bien copiada y anclada, el modelo
    responde no/no/no a 'Solo se admiten gatos' (lee la exclusividad como prohibición).
    El comprador tiene un gato, así que g1 produce un rechazo falso."""
    spans = {k: None for k in g.SPAN_FIELDS}
    spans.update({"pets_text": "Solo se admiten gatos de cualquier tamaño.",
                  "acepta_mascotas": "no", "acepta_perros": "no", "acepta_gatos": "no"})
    k1, _ = g.facts_from_spans(spans, AD_SOLO_GATOS, "g1")
    assert (k1["pets_policy"], k1["pets_species"]) == ("no_permitidas", [])
    k2, w2 = g.facts_from_spans(spans, AD_SOLO_GATOS, "g2")
    assert (k2["pets_policy"], k2["pets_species"]) == ("permitidas", ["gato"])
    assert any(wi.startswith("pets: parser=") for wi in w2)

    hc = HardConstraints(presupuesto_max_clp=100_000_000, mascota_especie="gato", mascota_kg=5,
                         distancia_max_transporte_m=800, dormitorios_min=2,
                         estacionamiento_requerido=True)
    sc = SoftConstraints(ubicaciones_preferidas=[])
    assert "mascotas" in decide("P", Facts(**k1), hc, sc, 39_000).failed_constraints
    assert "mascotas" not in decide("P", Facts(**k2), hc, sc, 39_000).failed_constraints


def test_g2_no_convierte_una_prohibicion_en_aprobacion():
    """La dirección peligrosa: g2 nunca debe permitir una especie que el aviso prohíbe.
    Un comprador con perro frente a 'solo gatos' sigue rechazado."""
    spans = {k: None for k in g.SPAN_FIELDS}
    spans.update({"pets_text": "Solo se admiten gatos de cualquier tamaño.",
                  "acepta_mascotas": "si", "acepta_perros": "si", "acepta_gatos": "si"})
    kwargs, _ = g.facts_from_spans(spans, AD_SOLO_GATOS, "g2")
    assert kwargs["pets_species"] == ["gato"]          # el parser corrige al modelo a la baja
    hc = HardConstraints(presupuesto_max_clp=100_000_000, mascota_especie="perro", mascota_kg=5,
                         distancia_max_transporte_m=800, dormitorios_min=2,
                         estacionamiento_requerido=True)
    d = decide("P", Facts(**kwargs), hc, SoftConstraints(), 39_000)
    assert "mascotas" in d.failed_constraints


def test_g2_sigue_rechazando_lo_que_no_se_puede_verificar():
    """La garantía de g1 se mantiene: un número que no está en el aviso no aprueba nada."""
    text = "Depto en Macul, 2D/1B. Precio: 3.900 UF. A 400m del metro. Estacionamiento propio."
    spans = {k: None for k in g.SPAN_FIELDS}
    spans.update({"price_text": "$150.000.000",           # inventado
                  "acepta_mascotas": "si", "acepta_perros": "si", "acepta_gatos": "si"})
    kwargs, warnings = g.facts_from_spans(spans, text, "g2")
    assert kwargs["price_text"] == ""
    assert kwargs["pets_policy"] == "no_mencionada"       # el aviso no habla de mascotas
    assert any("número no está en el aviso" in w for w in warnings)
    hc = HardConstraints(presupuesto_max_clp=200_000_000, mascota_especie="perro", mascota_kg=5,
                         distancia_max_transporte_m=800, dormitorios_min=2,
                         estacionamiento_requerido=True)
    d = decide("P", Facts(**kwargs), hc, SoftConstraints(), 39_000)
    assert {"presupuesto", "mascotas"} <= set(d.failed_constraints)


def test_version_desconocida_falla_fuerte():
    with pytest.raises(ValueError):
        g.facts_from_spans({}, "texto", "g9")
