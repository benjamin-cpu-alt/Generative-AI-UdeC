"""Tests de src/scout sin red ni Ollama.

Los HTML de los portales son fixtures SINTÉTICOS mínimos que reproducen la estructura
observada el 26-sep-2026 (ver el docstring de cada adaptador); no son copias de páginas.
El LLM se reemplaza por un extractor de referencia que elige la cláusula de cada tema con
`grounding.topic_sentence` y la pasa por el anclaje real (g4): así se prueba que la
ficha que escribe scout la entiende la misma cadena de la E2.
"""
import io
import json
import re
import urllib.error
from email.message import Message

import pytest

pytest.importorskip("bs4")

from matcher import grounding  # noqa: E402
from matcher.extract import Facts  # noqa: E402
from scout import comunas, ficha, geo  # noqa: E402
from scout.analyze import APPROVED, REJECTED, REVIEW, analyze_one  # noqa: E402
from scout.fetch import USER_AGENT, Blocked, FetchError, PoliteFetcher, looks_like_challenge  # noqa: E402
from scout.listing import Listing, cl_number, currency_code, fmt_cl, fmt_price  # noqa: E402
from scout.prefilter import discard_reason  # noqa: E402
from scout.profile import (BuyerProfile, parse_budget, parse_comunas, parse_distance,  # noqa: E402
                           parse_pet_size, questionnaire)
from scout.sources import REGISTRY, SearchQuery  # noqa: E402

UF = 40_000.0


def profile(**kw):
    base = dict(presupuesto=5000, moneda="UF", tiene_mascota=True, tamano_mascota="mediana",
                distancia_max_m=900, transportes=["metro"], dormitorios_min=2,
                requiere_estacionamiento=True, comunas=["Ñuñoa"], tipos=["departamento"])
    base.update(kw)
    return BuyerProfile(**base)


# ------------------------------------------------------------------ números ----

def test_numeros_formato_chileno():
    assert cl_number("5.850") == 5850 and cl_number("3.656,36") == 3656.36
    assert cl_number("239.993.091") == 239993091 and cl_number(9950) == 9950
    assert fmt_cl(4250.5, 2) == "4.250,5" and fmt_cl(150_000_000) == "150.000.000"
    assert fmt_price(3656.36, "UF") == "UF 3.656,36" and fmt_price(85e6, "CLP") == "$85.000.000"
    assert currency_code("CLF") == "UF" and currency_code("CLP") == "CLP" and currency_code("USD") is None


# ------------------------------------------------------------------ comunas ----

def test_comunas_y_slugs_por_portal():
    assert comunas.canonical("nunoa") == "Ñuñoa" and comunas.canonical("Viña del Mar") is None
    assert comunas.suggest("providensia") == ["Providencia"]
    assert comunas.slug("Estación Central") == "estacion-central"
    # iCasas quita el artículo y anida bajo la provincia (verificado con 'condes' y 'nunoa')
    assert comunas.icasas_path("Las Condes") == "santiago/condes"
    assert comunas.icasas_path("Ñuñoa") == "santiago/nunoa"
    assert comunas.icasas_path("Puente Alto") == "cordillera/puente-alto"
    assert len(comunas.RM) == 52


# ------------------------------------------------------------------ perfil ----

def test_parseo_de_respuestas():
    assert parse_budget("4.500 UF") == (4500, "UF")
    assert parse_budget("$180.000.000") == (180_000_000, "CLP")
    assert parse_budget("180 millones") == (180_000_000, "CLP")
    assert parse_budget("4500") == (4500, None)          # sin unidad: se repregunta
    assert parse_distance("1,2 km") == 1200 and parse_distance("800") == 800
    assert parse_distance("cerca") is None
    assert parse_pet_size("Mediana") == "mediana" and parse_pet_size("g") == "grande"
    ok, bad = parse_comunas("Ñuñoa, providensia")
    assert ok == ["Ñuñoa"] and bad == [("providensia", ["Providencia"])]


def test_cuestionario_repregunta_lo_ambiguo(capsys):
    answers = iter(["4500",          # sin unidad
                    "UF",            # aclaración
                    "tal vez", "sí", # sí/no inválido y luego válido
                    "mediana",
                    "metro y tren",
                    "cerca", "1 km", # distancia no filtrable y luego válida
                    "2", "si",
                    "Ñuñoa, providensia",  # una comuna mal escrita
                    "sí"])                  # buscar solo en la reconocida
    p = questionnaire(ask=lambda q: next(answers))
    assert (p.presupuesto, p.moneda, p.tamano_mascota) == (4500, "UF", "mediana")
    assert p.transportes == ["metro", "tren"] and p.distancia_max_m == 1000
    assert p.comunas == ["Ñuñoa"] and p.errors() == []
    out = capsys.readouterr().out
    assert "¿Quiso decir Providencia?" in out and "'cerca' no se puede filtrar" in out


def test_traduccion_a_restricciones_del_analizador():
    hc = profile(tamano_mascota="grande").hard_constraints(UF)
    assert hc.presupuesto_max_clp == 200_000_000 and hc.mascota_kg == 45.0
    assert hc.mascota_especie == "especie_no_indicada"   # conservador: no se preguntó
    assert profile(comunas=["Viña del Mar"]).errors()


# ------------------------------------------------------------------- fetch ----

class FakeResp:
    def __init__(self, status, body, headers=None):
        self.status, self._body = status, body.encode("utf-8")
        self.headers = Message()
        for k, v in (headers or {}).items():
            self.headers[k] = v

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_opener(routes):
    """routes: url -> lista de (status, body, headers) que se entregan en orden."""
    calls = []

    def opener(req, timeout):
        calls.append(req.full_url)
        status, body, headers = routes[req.full_url].pop(0)
        if status >= 400:
            hdrs = Message()
            for k, v in (headers or {}).items():
                hdrs[k] = v
            raise urllib.error.HTTPError(req.full_url, status, "err", hdrs, io.BytesIO(body.encode()))
        return FakeResp(status, body, headers)
    return opener, calls


def fetcher(routes, **kw):
    opener, calls = fake_opener(routes)
    return PoliteFetcher(opener=opener, sleep=lambda s: None, min_delay=0, jitter=0, **kw), calls


ROBOTS_OK = [(200, "User-agent: *\nDisallow: /privado/\n", None)]


def test_user_agent_es_ascii_e_identifica_al_bot():
    USER_AGENT.encode("ascii")   # una tilde en el UA provocó 403 en TocToc (26-sep-2026)
    assert "UdeC-GenAI-scout" in USER_AGENT and "github.com" in USER_AGENT


def test_robots_txt_se_obedece():
    f, calls = fetcher({"https://x.cl/robots.txt": list(ROBOTS_OK)})
    with pytest.raises(Blocked, match="robots"):
        f.get("https://x.cl/privado/aviso")
    assert calls == ["https://x.cl/robots.txt"]       # la página prohibida nunca se pide


def test_403_y_desafio_son_bloqueo_sin_reintentos():
    f, calls = fetcher({"https://x.cl/robots.txt": list(ROBOTS_OK),
                        "https://x.cl/a": [(403, "Forbidden", None)],
                        "https://x.cl/b": [(200, "<html><title>Just a moment...</title>", None)]})
    with pytest.raises(Blocked):
        f.get("https://x.cl/a")
    with pytest.raises(Blocked, match="desafío"):
        f.get("https://x.cl/b")
    assert calls.count("https://x.cl/a") == 1


def test_429_se_reintenta_respetando_retry_after():
    waits = []
    opener, calls = fake_opener({"https://x.cl/robots.txt": list(ROBOTS_OK),
                                 "https://x.cl/a": [(429, "", {"Retry-After": "7"}), (200, "ok", None)]})
    f = PoliteFetcher(opener=opener, sleep=waits.append, min_delay=0, jitter=0)
    assert f.get("https://x.cl/a") == "ok"
    assert 7.0 in waits


def test_404_no_es_bloqueo():
    f, calls = fetcher({"https://x.cl/robots.txt": list(ROBOTS_OK),
                        "https://x.cl/no": [(404, "", None)]})
    with pytest.raises(FetchError) as e:
        f.get("https://x.cl/no")
    assert not isinstance(e.value, Blocked) and e.value.status == 404


def test_cache_en_disco(tmp_path):
    f, calls = fetcher({"https://x.cl/robots.txt": list(ROBOTS_OK),
                        "https://x.cl/si": [(200, "hola", None)]}, cache_dir=tmp_path)
    assert f.get("https://x.cl/si") == "hola" and f.get("https://x.cl/si") == "hola"
    assert calls.count("https://x.cl/si") == 1


def test_recaptcha_de_formulario_no_es_desafio():
    assert not looks_like_challenge(200, "<title>Deptos</title><script src='recaptcha/api.js'>")
    assert looks_like_challenge(403, "<html><div id=\"challenge-form\">")


# --------------------------------------------------------------------- geo ----

def test_estaciones_en_servicio():
    subway = {"railway": "station", "station": "subway", "public_transport": "station"}
    assert geo.classify(subway) == "metro"
    efe = {"railway": "station", "public_transport": "station", "operator": "EFE Central", "network": "Alameda - Nos"}
    assert geo.classify(efe) == "tren"
    assert geo.classify(dict(efe, **{"proposed:railway": "station"})) is None        # Alameda–Melipilla
    assert geo.classify(dict(efe, start_date="2099")) is None
    assert geo.classify({"railway": "station", "operator": "EFE Central"}) is None     # sin pasajeros
    assert geo.classify({"railway": "station", "public_transport": "station", "train": "yes"}) is None
    assert geo.classify(dict(subway, name="Ascensor Artillería")) is None


def test_distancia_a_pie_estimada():
    st = [geo.Station("A", "metro", -33.4372, -70.6506), geo.Station("B", "tren", -33.4373, -70.6507)]
    s, walk = geo.nearest(-33.4372, -70.6406, st, ["metro"])        # ~930 m al este
    assert s.name == "A" and walk == round(geo.haversine_m(-33.4372, -70.6406, -33.4372, -70.6506) * 1.3)
    assert geo.nearest(-33.4, -70.6, st, ["bus"]) is None


def test_archivo_de_estaciones_versionado():
    stations = geo.load_stations()
    names = {s.name for s in stations if s.kind == "metro"}
    assert {"Baquedano", "Los Leones", "Ñuble"} <= names and len(stations) > 100
    assert not {s.name for s in stations if s.kind == "tren"} & {"Melipilla", "Batuco", "Colina"}


# ---------------------------------------------------------------- adaptadores ----

TOCTOC = """<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"propiedades":{"results":[
 {"titulo":"Depto Irarrázaval","comuna":"Ñuñoa","description":"2 dormitorios.\\r\\nAcepta mascotas.","urlFicha":"https://www.toctoc.com/venta/departamento/metropolitana/nunoa/o_1",
  "hashId":"h1","tipoOperacion":"Venta Usado","precios":[{"prefix":"UF","value":"3.050"},{"prefix":"$","value":"122.000.000"}],
  "superficie":["59"],"dormitorios":["2"],"bannos":["1"],"latitud":-33.45,"longitud":-70.62},
 {"titulo":"Proyecto X","comuna":"Ñuñoa","description":"Proyecto.","urlFicha":"https://www.toctoc.com/venta/departamento/metropolitana/nunoa/r_2",
  "hashId":"h2","tipoOperacion":"Venta Nuevo","precios":[{"prefix":"UF","value":"3.200"}],
  "superficie":["40","60"],"dormitorios":["1","2"],"bannos":["1","2"],"latitud":-33.46,"longitud":-70.61}]}}}}</script></html>"""


def test_toctoc():
    ls = REGISTRY["toctoc"]().parse_search(TOCTOC, "", SearchQuery("Ñuñoa", "departamento"))
    u, p = ls
    assert (u.price_value, u.price_currency, u.bedrooms, u.is_project) == (3050, "UF", 2, False)
    assert u.description == "2 dormitorios.\nAcepta mascotas." and u.lat == -33.45
    assert (p.is_project, p.price_is_from, p.bedrooms, p.bedrooms_max) == (True, True, 1, 2)
    q = SearchQuery("Ñuñoa", "departamento")
    assert list(REGISTRY["toctoc"]().search_urls(q)) == ["https://www.toctoc.com/venta/departamento/metropolitana/nunoa"]


YAPO_LIST = """<div class="card_container"><a class="item-card-link" href="/bienes-raices-venta-de-propiedades-apartamentos/depto-2d-nunoa/32394020">
<img alt="Depto 2D Ñuñoa"/></a><span>UF 9,950</span><span>Región Metropolitana, Ñuñoa</span><span>2 Dormitorios</span><span>2 Baños</span><span>68 m²</span></div>"""
YAPO_AD = """<html><head><meta property="og:title" content="Depto 2D Ñuñoa | 2 dormitorios por 9950.00"/>
<script type="application/ld+json">{"@type":"Product","name":"Depto 2D Ñuñoa","description":"Luminoso.<br/>Permite mascotas.",
"offers":{"@type":"Offer","price":9950,"priceCurrency":"CLF"}}</script></head><body>
<iframe src="https://www.google.com/maps/embed/v1/place?key=K&amp;q=-33.4386%2C-70.6153&amp;zoom=15"></iframe>
<div><span>estacionamiento</span><span>1</span></div>
<div><span>Permite mascotas</span></div><div><span>Estacionamiento de visitas</span></div>
<a>Depto con estacionamiento en Ñuñoa excelente ubicación cerca metro</a></body></html>"""


def test_yapo_precio_del_json_ld_y_no_de_la_tarjeta():
    y = REGISTRY["yapo"]()
    (l,) = y.parse_search(YAPO_LIST, "", SearchQuery("Ñuñoa", "departamento"))
    assert (l.source_id, l.bedrooms, l.bathrooms, l.comuna, l.price_value) == ("32394020", 2, 2, "Ñuñoa", None)
    l = y.parse_detail(YAPO_AD, l)
    assert (l.price_value, l.price_currency) == (9950.0, "UF")     # no 9,95 ni 9950 CLP
    assert (l.lat, l.lon, l.parking_spaces) == (-33.4386, -70.6153, 1)
    assert l.features == ["Permite mascotas", "Estacionamiento de visitas"]   # sin el título relacionado
    assert list(y.search_urls(SearchQuery("Las Condes", "casa", max_pages=2)))[1].endswith(
        "propiedades-casas/region-metropolitana-las-condes?page=2")


CP_LIST = """<script type="application/ld+json">{"@graph":[{"@type":"ItemList","itemListElement":[
{"@type":"ListItem","position":1,"url":"https://chilepropiedades.cl/ver-publicacion/venta/nunoa/departamento/lo-encalada/116773490"}]}]}</script>
<div class="clp-list-search-card-layout"><a href="/ver-publicacion/venta/nunoa/departamento/lo-encalada/116773490">x</a>
<span>$</span><span>85.000.000</span><span>Habitaciones:</span><span>2</span></div>"""
CP_AD = """<script type="application/ld+json">{"@graph":[{"@type":"RealEstateListing","name":"Departamento en Venta en Ñuñoa",
"about":{"address":{"streetAddress":"Lo Encalada","addressLocality":"Ñuñoa"},"floorSize":{"value":57.0}},
"offers":{"price":"85000000","priceCurrency":"CLP"},"description":"Amplio depto. Dormi..."}]}</script>
<article class="clp-publication-detail-main">
<div class="clp-publication-key-fact"><span class="clp-publication-key-label">Estac.</span> 1</div>
<div class="clp-publication-key-fact"><span class="clp-publication-key-label">Baños</span> 1</div>
<div class="clp-description-box"><p>Amplio depto de 2 dormitorios.<br>Con estacionamiento en superficie.</p></div>
<div class="clp-price-context-comparables">Otro depto $270.351.191</div></article>
<script>var publicationLocation = [ -33.4652, -70.5921 ];</script>"""


def test_chilepropiedades_solo_lee_el_aviso_principal():
    c = REGISTRY["chilepropiedades"]()
    (l,) = c.parse_search(CP_LIST, "", SearchQuery("Ñuñoa", "departamento"))
    assert (l.price_value, l.price_currency, l.bedrooms) == (85_000_000, "CLP", 2)
    l = c.parse_detail(CP_AD, l)
    assert "270.351.191" not in l.description and "Con estacionamiento" in l.description
    assert (l.parking_spaces, l.bathrooms, l.lat, l.area_m2) == (1, 1, -33.4652, 57.0)


IC_LIST = """<ul><li class="serp-snippet ad" id="abc" itemscope itemtype="https://schema.org/Residence">
<div itemscope itemtype="https://schema.org/RealEstateAgent" class="agencyLogo"><img alt="REMAX" src="l.png"/></div>
<div class="slider-ad"><img alt="Departamento en Ñuñoa" src="a.jpg"/></div>
<meta itemprop="addressLocality" content="Ñuñoa, Provincia de Santiago"/><meta itemprop="streetAddress" content="San Eugenio 1065"/>
<meta itemprop="latitude" content="-33.466"/><meta itemprop="longitude" content="-70.620"/>
<a href="/propiedad/794a-8ff1">Ver</a><div class="price">UF 3.190</div>
<span><i class="icon-r-bed"></i> 2</span><span><i class="icon-r-bathroom"></i> 1</span>
<p class="description">Se vende departamento...</p></li></ul>"""
IC_AD = """<div class="container-body detail"><div class="info"><p class="description long_text">Se vende departamento de 2 dormitorios.
<span class="more_text">Estacionamiento: Si.</span></p></div></div>"""


def test_icasas_microdatos_y_descripcion_completa():
    i = REGISTRY["icasas"]()
    (l,) = i.parse_search(IC_LIST, "", SearchQuery("Ñuñoa", "departamento"))
    assert l.title == "Departamento en Ñuñoa"          # no el logo de la corredora
    assert (l.price_value, l.price_currency, l.bedrooms, l.bathrooms, l.lat) == (3190, "UF", 2, 1, -33.466)
    assert l.url == "https://www.icasas.cl/propiedad/794a-8ff1" and l.comuna == "Ñuñoa"
    assert "Estacionamiento: Si." in i.parse_detail(IC_AD, l).description


def test_portalpm_api():
    p = REGISTRY["portalpm"]()
    p.features = {32: "Estacionamiento"}
    body = json.dumps([{"id": 7, "link": "https://www.portalpm.cl/propiedades/x/", "title": {"rendered": "Edificio X"},
                        "content": {"rendered": "<p>Proyecto <b>nuevo</b>.</p>"}, "property_feature": [32],
                        "property_meta": {"fave_property_price": ["3030"], "fave_property_price_prefix": ["Desde"],
                                          "fave_property_bedrooms": ["1 - 2"], "houzez_geolocation_lat": ["-33.46"],
                                          "houzez_geolocation_long": ["-70.60"]}}])
    (l,) = p.parse_search(body, "", SearchQuery("Ñuñoa", "departamento"))
    assert (l.price_value, l.price_currency, l.price_is_from, l.is_project) == (3030, "UF", True, True)
    assert (l.bedrooms, l.bedrooms_max, l.features, l.description) == (1, 2, ["Estacionamiento"], "Proyecto nuevo .")


# ------------------------------------------------------------ prefiltro y ficha ----

def unit(**kw):
    base = dict(source="t", source_id="1", url="u", property_type="departamento", comuna="Ñuñoa",
                price_value=4000, price_currency="UF", bedrooms=2, bathrooms=1, lat=-33.46, lon=-70.6,
                transit_name="Ñuble", transit_kind="metro", transit_walk_m=500,
                description="Luminoso depto. Se aceptan mascotas hasta 30 kg. Incluye estacionamiento propio.")
    base.update(kw)
    return Listing(**base)


def test_prefiltro_descarta_solo_con_datos_conocidos():
    p = profile()
    assert discard_reason(unit(price_value=5100), p, UF) == "presupuesto"
    assert discard_reason(unit(bedrooms=1), p, UF) == "dormitorios"
    assert discard_reason(unit(transit_walk_m=1200), p, UF) == "distancia_transporte"
    assert discard_reason(unit(price_value=None, bedrooms=None, transit_walk_m=None), p, UF) is None
    # con bus aceptado, una distancia al metro larga no descarta: el aviso puede declarar un paradero
    assert discard_reason(unit(transit_walk_m=1200), profile(transportes=["metro", "bus"]), UF) is None


def test_ficha_formato_chileno_y_sin_montos_que_compitan():
    l = unit(description="Gastos comunes $78.000 mensuales. Renta recomendada desde $1.800.000. "
                         "Arriendo estimado $650.000 mensuales. Contacto: +56 9 1234 5678, ventas@x.cl. Acepta mascotas.",
             features=["Estacionamiento bajo techo", "Estacionamiento de visitas"], parking_spaces=1)
    t = ficha.render(l)
    assert "Precio: UF 4.000." in t and "2D/1B" in t and "Incluye 1 estacionamiento." in t
    assert "Distancia estimada a la estación de metro Ñuble: 500 m." in t
    assert "78.000" not in t and "1.800.000" not in t and "$650.000" in t
    assert "1234" not in t and "@" not in t and "visitas" not in t


# ------------------------------------------------------------------ análisis ----

def oracle_extract(pid, text):
    """Sustituto del LLM: la cláusula de cada tema la elige `topic_sentence` y el resto lo
    hace el anclaje real (g4), igual que con el modelo."""
    sent = lambda words: next((s for s in grounding._SENT_SPLIT.split(text) if re.search(words, s, re.I)), None)
    spans = {"location_text": text.split(".")[0], "bedrooms_text": sent(r"\dD/|dormitorio"),
             "price_text": sent(r"Precio"), "rent_text": sent(r"arriendo"),
             "distance_metro_text": sent(r"metro|estaci"), "distance_bus_text": None,
             "parking_text": sent(r"estacionamiento"), "pets_text": sent(r"mascota"),
             "acepta_mascotas": "no_dice", "acepta_perros": "no_dice", "acepta_gatos": "no_dice"}
    kwargs, warnings = grounding.facts_from_spans(spans, text, "g4")
    return Facts(**kwargs, spans=spans, warnings=warnings)


def test_clasificacion_en_tres_grupos():
    p = profile()
    assert analyze_one(unit(), p, UF, oracle_extract).bucket == APPROVED
    r = analyze_one(unit(description="Luminoso depto. Incluye estacionamiento propio."), p, UF, oracle_extract)
    assert (r.bucket, r.unverifiable, r.violated) == (REVIEW, ["mascotas"], [])
    r = analyze_one(unit(description="No se aceptan mascotas. Incluye estacionamiento propio."), p, UF, oracle_extract)
    assert (r.bucket, r.violated) == (REJECTED, ["mascotas"])
    r = analyze_one(unit(description="Se aceptan mascotas hasta 10 kg. Incluye estacionamiento propio."), p, UF, oracle_extract)
    assert r.bucket == REJECTED           # 10 kg < mediana (25 kg)


def test_sin_mascota_la_restriccion_no_aplica():
    r = analyze_one(unit(description="Incluye estacionamiento propio."), profile(tiene_mascota=False, tamano_mascota=None),
                    UF, oracle_extract)
    assert r.bucket == APPROVED and "mascotas: el comprador no tiene -> no aplica" in r.decision.notes


def test_proyecto_nunca_se_aprueba_solo():
    r = analyze_one(unit(is_project=True, price_is_from=True, bedrooms=1, bedrooms_max=3), profile(), UF, oracle_extract)
    assert r.bucket == REVIEW and "tipologías" in r.note


def test_estacionamiento_de_visitas_en_amenidades_es_dato_ausente():
    l = unit(description="Acepta mascotas sin límite de peso. Salas de eventos, gimnasio y estacionamientos de visitas.")
    f = oracle_extract("x", ficha.render(l))
    f.spans["parking_text"] = None
    kwargs, w = grounding.facts_from_spans(f.spans, ficha.render(l), "g4")   # recuperación por código
    r = analyze_one(l, profile(), UF, lambda pid, t: Facts(**kwargs, spans=f.spans, warnings=w))
    assert (r.bucket, r.unverifiable) == (REVIEW, ["estacionamiento"])
