"""Sistema multiagente de la E3 (src/agents), sin Ollama: herramientas deterministas,
prompts versionados y el orquestador con un LLM simulado.

Lo que se protege:
- `comprobar` nunca acepta una corrección cuya evidencia no esté en el aviso, ni un
  permiso de mascotas que remite a un reglamento (las dos rutas de aprobación indebida).
- Un dato faltante nunca aprueba (`evaluar` lo deja no_verificable y falla).
- Los bucles terminan: relecturas, reintentos y consultas tienen presupuesto.
- Cada agente deja mensajes en la traza.
"""
import glob
import json
import re
from pathlib import Path

import pytest

from agents import llm, tools
from agents.orchestrator import Config, Sistema
from matcher.extract import SYSTEM_V5
from matcher.schema import Case, HardConstraints, PetsPolicy, Property, SoftConstraints, Truth

ROOT = Path(__file__).resolve().parents[1]
UF = 40_000


# ---------------------------------------------------------------- herramientas --

@pytest.mark.parametrize("texto,esperado", [
    ("doscientos cinco millones de pesos", [205_000_000]),
    ("cinco mil cuatrocientas UF", [5400]),
    ("a mil metros del paradero", [1000]),
    ("perros de hasta cinco kilos", [5]),
    ("ciento veintitrés", [123]),
])
def test_numeros_en_palabras(texto, esperado):
    assert tools.numeros_en_palabras(texto) == esperado


@pytest.mark.parametrize("campo,evidencia,esperado", [
    ("precio", "135 palos", [135_000_000]),
    ("precio", "$219 millones", [219_000_000]),
    ("precio", "valor cinco mil cuatrocientas UF", [5400 * UF]),
    ("arriendo", "Arriendo actual: 680 lucas", [680_000]),
    ("arriendo", "Arriendo $420 mil", [420_000]),
    ("arriendo", "Arriendo 15 UF", [15 * UF]),
    ("distancia", "A 0,7 km del Metro", [700]),
    ("distancia", "Está a seiscientos metros del Metro", [600]),
    ("dormitorios", "Casa 3D+E", [3]),
    ("dormitorios", "2 habitaciones, 1 baño", [2]),
    ("mascotas_kg", "Perros de hasta cinco kilos", [5]),
])
def test_interpretar(campo, evidencia, esperado):
    assert tools.interpretar(campo, evidencia, UF) == esperado


def test_comprobar_exige_evidencia_del_aviso():
    texto = "Depto en Ñuñoa, 2D/1B. UF 3.600. Arriendo actual: 680 lucas."
    assert tools.comprobar("arriendo", "680000", "Arriendo actual: 680 lucas", texto, UF)[:2] == (True, 680_000)
    ok, _, motivo = tools.comprobar("arriendo", "900000", "Arriendo: 900 lucas", texto, UF)
    assert not ok and "no está en el aviso" in motivo
    assert not tools.comprobar("precio", "3600", "(el Lector no copió nada)", texto, UF)[0]


def test_comprobar_ambiguedad_la_resuelve_el_valor_del_agente():
    texto = "Precio rebajado: antes UF 5.600, ahora UF 5.200."
    ev = "antes UF 5.600, ahora UF 5.200"
    assert tools.comprobar("precio", "5200", ev, texto, UF)[:2] == (True, 5200 * UF)
    assert not tools.comprobar("precio", "1", ev, texto, UF)[0]
    # los gastos comunes no son un precio verosímil: no compiten
    t2 = "UF 4.025, gastos comunes $95.000."
    assert tools.comprobar("precio", "4025", t2, t2, UF)[:2] == (True, 4025 * UF)


@pytest.mark.parametrize("evidencia", ["Consultar reglamento por mascotas.",
                                       "Mascotas según reglamento de copropiedad.",
                                       "Mascotas: consultar con administración."])
def test_comprobar_no_acepta_permiso_que_remite_a_reglamento(evidencia):
    assert not tools.comprobar("mascotas", "permitidas", evidencia, "Depto. " + evidencia, UF)[0]
    assert tools.comprobar("mascotas", "no_explicita", evidencia, "Depto. " + evidencia, UF)[0]


def test_comprobar_estacionamiento_aparte_no_es_propio():
    t = "Estacionamiento opcional, en venta aparte por UF 250."
    assert not tools.comprobar("estacionamiento", "propio", t, t, UF)[0]
    assert tools.comprobar("estacionamiento", "propio", "2 estac.", "MAIPU. 2 estac.", UF)[0]


def test_especies():
    assert tools.especies_de("Gatos sí, perros no") == ["gato"]
    assert tools.especies_de("Perros de hasta cinco kilos") == ["perro"]
    assert tools.especies_de("Mascotas bienvenidas") == []


HC = HardConstraints(presupuesto_max_clp=150_000_000, mascota_especie="perro", mascota_kg=10,
                     distancia_max_transporte_m=1000, dormitorios_min=2, estacionamiento_requerido=True)
HECHOS = {"comuna": "Ñuñoa", "dormitorios": 2, "precio": 140_000_000, "arriendo": 700_000,
          "distancia_metro": 500, "distancia_bus": None, "estacionamiento": "propio",
          "mascotas": "permitidas", "especies": [], "mascotas_kg": None}


def _case(props, sc=SoftConstraints()):
    return Case(id="c", uf_value=UF, hard_constraints=HC, properties=props, soft_constraints=sc)


def test_evaluar_dato_faltante_nunca_aprueba():
    c = _case([])
    assert not tools.evaluar("P", HECHOS, c)["failed_constraints"]
    for campo in ("precio", "dormitorios"):
        e = tools.evaluar("P", {**HECHOS, campo: None}, c)
        assert e["failed_constraints"] and "no_verificable" in e["estado"].values()
    # convención E3: sin política declarada no se descarta, pero va al final del orden;
    # una duda sobre el permiso que nadie resolvió sí falla
    e = tools.evaluar("P", {**HECHOS, "mascotas": "no_explicita"}, c)
    assert e["estado"]["mascotas"] == "sin_confirmar" and not e["failed_constraints"]
    assert not e["mascotas_confirmadas"]
    e = tools.evaluar("P", {**HECHOS, "mascotas": "no_explicita", "_mascotas_duda": True}, c)
    assert e["estado"]["mascotas"] == "no_verificable" and e["failed_constraints"] == ["mascotas"]


def test_evaluar_estudio_cuenta_como_un_dormitorio():
    c = _case([])
    e = tools.evaluar("P", {**HECHOS, "dormitorios": 0}, c)
    assert e["estado"]["dormitorios"] == ("cumple" if c.hard_constraints.dormitorios_min <= 1 else "falla")


def test_ordenar_mascotas_sin_confirmar_al_final():
    c = _case([], SoftConstraints(ubicaciones_preferidas=["Macul"]))
    evs = [tools.evaluar("A", {**HECHOS, "comuna": "Macul", "mascotas": "no_explicita"}, c),
           tools.evaluar("B", HECHOS, c)]
    assert [m["id"] for m in tools.ordenar(evs)["approved_matches"]] == ["B", "A"]


def test_ordenar_preferida_y_roi():
    c = _case([], SoftConstraints(ubicaciones_preferidas=["Macul"]))
    evs = [tools.evaluar("A", HECHOS, c), tools.evaluar("B", {**HECHOS, "comuna": "Macul", "arriendo": None}, c),
           tools.evaluar("C", {**HECHOS, "arriendo": 900_000}, c)]
    assert [m["id"] for m in tools.ordenar(evs)["approved_matches"]] == ["B", "C", "A"]


def test_dudas_marca_lo_que_fallo_en_la_e2():
    h = {**HECHOS, "precio": None, "estacionamiento": "no_mencionado", "comuna": "Casa",
         "_mascotas_por_parser": False}
    d = tools.dudas(h, "Casa en Vitacura, 135 palos. 2 estac. Consultar reglamento por mascotas.")
    assert {"precio", "estacionamiento", "comuna", "mascotas"} <= set(d)
    limpio = {**HECHOS, "_mascotas_por_parser": True}
    assert tools.dudas(limpio, "Depto en Ñuñoa. UF 3.500. Metro a 500 m. Acepta mascotas. Estac. propio.") == {}


# ---------------------------------------------------------------------- prompts --

@pytest.mark.parametrize("agente,secciones", [
    ("lector", {"system", "inicial", "relectura"}),
    ("verificador", {"system", "revisar", "retro", "consulta"}),
    ("decisor", {"system", "decidir", "sin_herramientas"}),
])
def test_prompts_versionados(agente, secciones):
    assert set(llm.load_prompt(agente, "v1")) == secciones


def test_lector_es_el_extractor_de_la_e2():
    assert llm.load_prompt("lector")["system"] == SYSTEM_V5


def test_numeros_de_ejemplo_no_aparecen_en_los_sets():
    """En la E2 el modelo copiaba los números de ejemplo del prompt: no pueden coincidir
    con ningún aviso (si coincidieran, una copia del ejemplo pasaría por lectura correcta)."""
    texto = llm.load_prompt("verificador")["system"]
    ejemplos = set(re.findall(r'"([^"]*\d[^"]*)" ->', texto))
    assert ejemplos
    avisos = " ".join(p["text"] for f in glob.glob(str(ROOT / "data/cases/*/*.json"))
                      for p in json.loads(Path(f).read_text(encoding="utf-8")).get("properties", []))
    assert not [e for e in ejemplos if e in avisos]


def test_first_json_sin_esquema():
    assert llm.first_json('Claro:\n```json\n{"a": {"b": 1}}\n``` listo') == {"a": {"b": 1}}
    assert llm.first_json("sin json") is None


# ------------------------------------------------------------------ orquestador --

TEXTO = "Depto en Ñuñoa, 2D/1B. Precio 135 palos. A 500 m del Metro. Acepta perros. Estacionamiento propio."
PROP = Property(id="P-1", text=TEXTO, truth=Truth(bedrooms=2, distance_transport_m=500,
                                                 pets=PetsPolicy(explicit=True, allowed=True, species=["perro"]),
                                                 parking="propio", price_clp=135_000_000, location="Ñuñoa"))
SPANS = {"location_text": "Depto en Ñuñoa", "bedrooms_text": "2D/1B", "price_text": "Precio 135 palos",
         "rent_text": None, "distance_metro_text": "A 500 m del Metro", "distance_bus_text": None,
         "parking_text": "Estacionamiento propio", "pets_text": "Acepta perros",
         "acepta_mascotas": "si", "acepta_perros": "si", "acepta_gatos": "no_dice"}


class FakeLLM:
    """Responde según el agente (se reconoce por el system prompt) con guiones fijos."""

    def __init__(self, verificador, decisor):
        self.verificador, self.decisor, self.calls = verificador, decisor, []

    def __call__(self, model, system, user, schema, esquema=True, **kw):
        meta = {"prompt_tokens": 1, "output_tokens": 1, "wall_s": 0.0, "raw": "", "error": None}
        if system.startswith("Eres un localizador"):
            agente, obj = "Lector", {k: SPANS.get(k) for k in schema["properties"]}
        elif system.startswith("Eres el Verificador"):
            agente, obj = "Verificador", self.verificador(user)
        else:
            agente, obj = "Decisor", self.decisor(user)
        self.calls.append(agente)
        return obj, meta


def test_flujo_completo_corrige_jerga_y_aprueba():
    fake = FakeLLM(lambda u: {"revisiones": [{"campo": "precio", "accion": "corregir",
                                              "evidencia": "Precio 135 palos", "valor": "135000000"}]},
                   lambda u: {"accion": "cerrar", "consultas": []})
    out, tr = Sistema(Config(), fake).run_case(_case([PROP]))
    assert out["approved_matches"] == [{"id": "P-1", "price_clp": 135_000_000, "roi_pct": None}]
    autores = {m["de"] for m in tr.mensajes}
    assert {"Lector", "Verificador", "Decisor", "herramienta:comprobar", "herramienta:ordenar"} <= autores
    assert [m["paso"] for m in tr.mensajes] == list(range(1, len(tr.mensajes) + 1))


def test_sin_correccion_el_precio_en_jerga_queda_no_verificable():
    fake = FakeLLM(lambda u: {"revisiones": []}, lambda u: {"accion": "cerrar", "consultas": []})
    out, _ = Sistema(Config(), fake).run_case(_case([PROP]))
    assert out["rejected"] == [{"id": "P-1", "failed_constraints": ["presupuesto"]}]


def test_relecturas_tienen_presupuesto():
    fake = FakeLLM(lambda u: {"revisiones": [{"campo": "precio", "accion": "releer", "evidencia": None,
                                              "valor": None}]},
                   lambda u: {"accion": "cerrar", "consultas": []})
    _, tr = Sistema(Config(), fake).run_case(_case([PROP]))
    assert fake.calls.count("Lector") == 1 + Config().max_relecturas
    assert any(m["tipo"] == "sin_relectura" for m in tr.mensajes)


def test_consultas_del_decisor_tienen_presupuesto():
    fake = FakeLLM(lambda u: {"revisiones": []},
                   lambda u: {"accion": "consultar",
                              "consultas": [{"id": "P-1", "campo": "precio", "motivo": "no se leyó"}]})
    out, tr = Sistema(Config(), fake).run_case(_case([PROP]))
    assert fake.calls.count("Decisor") == 2
    assert out["rejected"]


def test_ablacion_sin_refinar_no_relee_ni_consulta():
    fake = FakeLLM(lambda u: {"revisiones": [{"campo": "precio", "accion": "releer", "evidencia": None,
                                              "valor": None}]},
                   lambda u: {"accion": "consultar",
                              "consultas": [{"id": "P-1", "campo": "precio", "motivo": "x"}]})
    _, tr = Sistema(Config(refinar=False), fake).run_case(_case([PROP]))
    assert fake.calls.count("Lector") == 1
    assert any(m["tipo"] == "cierre_por_presupuesto" for m in tr.mensajes)


def test_ablacion_sin_releer_consulta_pero_no_relee():
    fake = FakeLLM(lambda u: {"revisiones": [{"campo": "precio", "accion": "releer", "evidencia": None,
                                              "valor": None}]},
                   lambda u: {"accion": "consultar",
                              "consultas": [{"id": "P-1", "campo": "precio", "motivo": "x"}]})
    _, tr = Sistema(Config(releer=False), fake).run_case(_case([PROP]))
    assert fake.calls.count("Lector") == 1
    assert any(m["tipo"] == "consulta" for m in tr.mensajes)       # la consulta sí se ejecuta
    assert Config(releer=False).nombre == "sin_releer"


def test_ablacion_sin_consultar_relee_pero_no_consulta():
    fake = FakeLLM(lambda u: {"revisiones": [{"campo": "precio", "accion": "releer", "evidencia": None,
                                              "valor": None}]},
                   lambda u: {"accion": "consultar",
                              "consultas": [{"id": "P-1", "campo": "precio", "motivo": "x"}]})
    _, tr = Sistema(Config(consultar=False), fake).run_case(_case([PROP]))
    assert fake.calls.count("Lector") == 1 + Config().max_relecturas
    assert fake.calls.count("Decisor") == 1
    assert any(m["tipo"] == "cierre_por_presupuesto" for m in tr.mensajes)
    assert Config(consultar=False).nombre == "sin_consultar"


def test_ablacion_sin_literal_acepta_sin_evidencia():
    malo = {"revisiones": [{"campo": "precio", "accion": "corregir", "evidencia": "inventada", "valor": "100000000"}]}
    full, _ = Sistema(Config(), FakeLLM(lambda u: malo, lambda u: {"accion": "cerrar", "consultas": []})).run_case(_case([PROP]))
    sin, _ = Sistema(Config(literal=False), FakeLLM(lambda u: malo, lambda u: {"accion": "cerrar", "consultas": []})).run_case(_case([PROP]))
    assert full["rejected"] and sin["approved_matches"][0]["price_clp"] == 100_000_000


def test_ablacion_sin_esquema_tolera_spans_que_no_son_texto():
    class Raro(FakeLLM):
        def __call__(self, model, system, user, schema, esquema=True, **kw):
            obj, meta = super().__call__(model, system, user, schema, esquema, **kw)
            if self.calls[-1] == "Lector":
                obj = {**obj, "pets_text": ["Acepta perros"], "bedrooms_text": 2}
            return obj, meta
    fake = Raro(lambda u: {}, lambda u: {"accion": "cerrar", "consultas": []})
    _, tr = Sistema(Config(esquema=False), fake).run_case(_case([PROP]))
    spans = next(m["contenido"] for m in tr.mensajes if m["tipo"] == "spans")
    assert spans["pets_text"] is None and spans["bedrooms_text"] == "2"


def test_nombre_de_la_configuracion():
    assert Config().nombre == "full"
    assert Config(retro=False).nombre == "sin_retro"


def test_comprobar_rechaza_precio_inverosimil():
    t = "san miguel, 135 palos, lo arriendan en 720 lucas"
    ok, _, motivo = tools.comprobar("precio", "720000", "lo arriendan en 720 lucas", t, UF)
    assert not ok and "verosímil" in motivo
    assert tools.comprobar("precio", "135000000", "135 palos", t, UF)[:2] == (True, 135_000_000)


def test_comuna_canonica_y_preferencia():
    assert tools.comuna_canonica("Santiago Centro") == "Santiago"
    assert tools.comuna_canonica("Bellavista de La Florida") == "La Florida"
    assert tools.comuna_canonica("Casa") is None
    c = _case([], SoftConstraints(ubicaciones_preferidas=["Santiago Centro"]))
    assert tools.evaluar("P", {**HECHOS, "comuna": "Santiago"}, c)["preferida"]
    assert "comuna" not in tools.dudas({**HECHOS, "comuna": "Santiago Centro", "_mascotas_por_parser": True},
                                        "Depto en Santiago Centro. UF 3.000. Metro a 300 m. Acepta mascotas. Estac. propio.")


def test_duda_de_mascotas_sin_resolver_no_aprueba():
    texto = "Depto en Ñuñoa, 2D/1B. UF 3.000. A 500 m del Metro. Perros de hasta cinco kilos. Estacionamiento propio."
    prop = Property(id="P-2", text=texto, truth=PROP.truth)
    spans = {**SPANS, "price_text": "UF 3.000", "pets_text": "acepta perros"}
    fake = FakeLLM(lambda u: {"revisiones": []}, lambda u: {"accion": "cerrar", "consultas": []})
    fake_lector = fake.__call__

    def call(model, system, user, schema, **kw):
        if system.startswith("Eres un localizador"):
            return {k: spans.get(k) for k in schema["properties"]}, {"prompt_tokens": 0, "output_tokens": 0,
                                                                    "wall_s": 0, "raw": "", "error": None}
        return fake_lector(model, system, user, schema, **kw)
    out, tr = Sistema(Config(), call).run_case(_case([prop]))
    assert out["rejected"] == [{"id": "P-2", "failed_constraints": ["mascotas"]}]
    assert any(m["tipo"] == "duda_sin_resolver" for m in tr.mensajes)


@pytest.mark.parametrize("evidencia,esperado", [
    # frases del generador (train/test): la E2 las lee bien y los agentes no deben tocarlas
    ("Se aceptan mascotas pequeñas y medianas hasta 15kg, previa autorización de la administración.", []),
    ("Se aceptan gatos, perros no permitidos por reglamento de copropiedad.", ["gato"]),
    ("Se aceptan perros, gatos no permitidos por reglamento de copropiedad.", ["perro"]),
    ("Edificio sin mascotas por reglamento de copropiedad.", None),
    ("El reglamento de copropiedad permite mascotas de hasta 8 kilos.", []),
    # frases que aplazan la decisión: no son permiso
    ("Consultar reglamento por mascotas.", None),
    ("Mascotas según reglamento de copropiedad.", None),
])
def test_especies_frases_de_reglamento(evidencia, esperado):
    assert tools.especies_de(evidencia) == esperado


def test_reglamento_explicito_no_es_duda():
    h = {**HECHOS, "_mascotas_por_parser": True}
    t = "Depto en Recoleta. UF 3.000. Metro a 400 m. Se aceptan gatos, perros no permitidos por reglamento de copropiedad. Estacionamiento propio."
    assert "mascotas" not in tools.dudas({**h, "especies": ["gato"]}, t)
