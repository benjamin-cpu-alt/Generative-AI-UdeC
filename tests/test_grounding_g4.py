"""g4: dos correcciones de seguridad halladas con avisos reales (src/scout). Cada test
muestra el comportamiento de g3 (que se conserva: es la versión reportada en la E2) y
el de g4. Los textos son los del aviso de chilepropiedades.cl que g3 aprobaba."""
from matcher.grounding import facts_from_spans

AVISO = ("Departamento en Providencia, Av. Providencia 1645. 3D/2B, 80 m². Precio: $150.000.000. "
         "Conserjería y vigilancia 24/7. La administración cuenta con opción de arriendo de "
         "estacionamientos. Se aceptan ofertas. Se acepta canje con corredores.")


def _spans(**kw):
    base = {"location_text": None, "bedrooms_text": "3D/2B", "price_text": "$150.000.000",
            "rent_text": None, "distance_metro_text": None, "distance_bus_text": None,
            "parking_text": None, "pets_text": None,
            "acepta_mascotas": "no_dice", "acepta_perros": "no_dice", "acepta_gatos": "no_dice"}
    base.update(kw)
    return base


def test_clausula_de_mascotas_sin_mascotas_no_aprueba():
    spans = _spans(pets_text="Se aceptan ofertas. Se acepta canje con corredores.")
    g3, _ = facts_from_spans(spans, AVISO, "g3")
    g4, warnings = facts_from_spans(spans, AVISO, "g4")
    assert g3["pets_policy"] == "permitidas"          # el defecto: "acepta" ofertas = acepta mascotas
    assert g4["pets_policy"] == "no_mencionada"
    assert not any("reemplaza" in w for w in warnings)


def test_clausula_de_mascotas_real_sigue_funcionando_en_g4():
    aviso = "Depto 2D/1B en Ñuñoa. Se aceptan mascotas pequeñas, hasta 10 kg."
    spans = _spans(pets_text="Se aceptan mascotas pequeñas, hasta 10 kg.", acepta_mascotas="si")
    f, _ = facts_from_spans(spans, aviso, "g4")
    assert f["pets_policy"] == "permitidas" and f["pets_max_kg"] == 10.0


def test_estacionamiento_en_arriendo_no_esta_incluido():
    spans = _spans(parking_text="La administración cuenta con opción de arriendo de estacionamientos.")
    assert facts_from_spans(spans, AVISO, "g3")[0]["parking"] == "propio"   # el defecto
    assert facts_from_spans(spans, AVISO, "g4")[0]["parking"] == "ninguno"


def test_estacionamiento_incluido_sigue_siendo_propio_en_g4():
    aviso = "Depto 2D/2B. Incluye 1 estacionamiento y bodega."
    spans = _spans(parking_text="Incluye 1 estacionamiento y bodega.")
    assert facts_from_spans(spans, aviso, "g4")[0]["parking"] == "propio"
