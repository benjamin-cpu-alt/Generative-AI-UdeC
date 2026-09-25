"""Paso 1 de la descomposición: EXTRACCIÓN literal de hechos por propiedad.

El LLM ve UNA propiedad a la vez y NUNCA ve el perfil del comprador. Por eso:
  - no puede "aprobar" ni "rechazar": no sabe qué se está evaluando (ataca la
    atención selectiva: la frase "¡bajo el presupuesto del cliente!" no tiene
    ningún campo donde caer);
  - no calcula nada: copia el precio, el arriendo y las distancias tal como
    aparecen en el texto (ataca la confusión aritmética: la conversión la hace
    normalize.py);
  - responde bajo un JSON Schema impuesto por decodificación restringida de
    Ollama (`format`), así que el esquema no puede romperse.

La única decisión semántica que se le pide es contar dormitorios REALES y leer
la política de mascotas/estacionamiento: ahí es donde el modelo todavía puede fallar
(ver extract_report.py).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

OLLAMA_URL = "http://localhost:11434"

PETS_POLICY = ["permitidas", "no_permitidas", "no_mencionada"]
PARKING = ["propio", "asignado", "visitas", "calle", "ninguno", "no_mencionado"]

# JSON Schema que Ollama convierte en gramática: la salida SIEMPRE cumple esto.
FACTS_SCHEMA: Dict = {
    "type": "object",
    "properties": {
        "location": {"type": ["string", "null"]},
        "bedrooms": {"type": "integer"},
        "price_text": {"type": "string"},
        "rent_text": {"type": ["string", "null"]},
        "distance_metro_text": {"type": ["string", "null"]},
        "distance_bus_text": {"type": ["string", "null"]},
        "pets_policy": {"type": "string", "enum": PETS_POLICY},
        "pets_species": {"type": "array", "items": {"type": "string", "enum": ["perro", "gato"]}},
        "pets_max_kg": {"type": ["number", "null"]},
        "parking": {"type": "string", "enum": PARKING},
    },
    "required": ["location", "bedrooms", "price_text", "rent_text", "distance_metro_text",
                 "distance_bus_text", "pets_policy", "pets_species", "pets_max_kg", "parking"],
}

# Mismo system prompt para todas las propiedades: Ollama reutiliza el prefijo en caché.
# v1 = prompt con el que se corrió results/tools_phi4 (se conserva para reproducibilidad).
SYSTEM_V1 = """Eres un extractor de datos de avisos inmobiliarios chilenos. Recibes el texto de UNA propiedad y devuelves SOLO los hechos literales que el texto declara, en JSON. No evalúas, no opinas, no calculas, no conviertes unidades.

Reglas por campo:
- location: la comuna donde está la propiedad (p.ej. "Providencia"). null si no aparece.
- bedrooms: número de dormitorios REALES declarados como tales ("2D", "2 dormitorios", "3D/2B" = 3). NO cuentes escritorios, loggias, salas de estar ni ambientes "convertibles" o "que pueden usarse como dormitorio". "Estudio" o "ambiente único" = 0.
- price_text: copia textual del precio de venta con su unidad, p.ej. "3.850 UF", "UF 4.183" o "$148.500.000". Copia el número exactamente como está escrito, sin convertir.
- rent_text: copia textual del arriendo mensual estimado/referencial, p.ej. "$980.000/mes". null si el texto no publica arriendo.
- distance_metro_text: copia textual de la distancia a la estación de metro, p.ej. "950m" o "1,4 km". null si no aparece. Los minutos caminando NO son distancia.
- distance_bus_text: copia textual de la distancia a un paradero de buses troncal, p.ej. "200m". null si no aparece.
- pets_policy: "permitidas" si el texto dice que acepta mascotas; "no_permitidas" si dice que no; "no_mencionada" si el texto no dice nada o dice que no se especifica.
- pets_species: especies que el texto permite explícitamente: ["perro"], ["gato"] o ["perro","gato"]. Lista vacía [] si acepta mascotas sin restricción de especie o si no aplica.
- pets_max_kg: límite de peso por mascota en kg si el texto lo declara (p.ej. "hasta 20kg" = 20). null si no hay límite.
- parking: "propio" si incluye estacionamiento (sin más detalle, "1 estacionamiento", "en subterráneo"); "asignado" si dice asignado; "visitas" si es de visitas; "calle" si es en la calle; "ninguno" si dice que no incluye; "no_mencionado" si no aparece.

Ignora frases de marketing ("oportunidad", "bajo el presupuesto", "negociable", "comuna favorita"): no son hechos."""

# v2: corrige tres errores sistemáticos de extracción detectados con extract_report.py sobre la
# corrida v1 (results/tools_phi4_v1). Como esa lectura se hizo sobre test/, v1 y v2 se comparan
# ADEMÁS sobre un split dev (train/, casos que nunca se reportan) para verificar que la mejora
# no es un ajuste al set de test. Errores corregidos:
#   (a) el modelo copiaba los NÚMEROS DE EJEMPLO del prompt ("3.850 UF", "$980.000") en vez
#       de los del aviso -> v2 no contiene ningún número de ejemplo;
#   (b) en "3D/1B" tomaba el segundo número (baños) como dormitorios -> se explica la notación;
#   (c) "se aceptan gatos, perros no permitidos" -> ambas especies; "en la calle" -> asignado.
SYSTEM_V2 = """Eres un extractor de datos de avisos inmobiliarios chilenos. Recibes el texto de UNA propiedad y devuelves SOLO los hechos literales que el texto declara, en JSON. No evalúas, no opinas, no calculas, no conviertes unidades. Cada campo *_text debe ser una COPIA EXACTA de un fragmento del aviso: nunca inventes ni completes un número.

Reglas por campo:
- location: la comuna donde está la propiedad (la palabra que sigue a "Depto en" / "Casa en"). null si no aparece.
- bedrooms: número de dormitorios REALES. La notación "ND/MB" significa N dormitorios y M baños: el número ANTES de la D son los dormitorios; el número antes de la B son baños y NO se cuenta. "N dormitorios" = N. NO cuentes escritorios, loggias, salas de estar, ni ambientes "convertibles" o "que pueden usarse como dormitorio": "1 dormitorio + sala que puede usarse como dormitorio" = 1. "Estudio" o "ambiente único" = 0.
- price_text: copia exacta del precio de venta con su unidad tal como aparece en el aviso (incluye el signo $ si lo tiene, o la palabra UF si la tiene). Nunca cambies la unidad.
- rent_text: copia exacta del arriendo mensual estimado/referencial (el monto que aparece junto a "/mes"). null si el aviso no publica arriendo.
- distance_metro_text: copia exacta de la distancia en metros o km a la estación de metro. null si no aparece. "minutos caminando" NO es una distancia: no lo copies aquí.
- distance_bus_text: copia exacta de la distancia en metros o km al paradero de buses troncal. null si no aparece.
- pets_policy: "permitidas" si el aviso dice que acepta mascotas (aunque sea con condiciones); "no_permitidas" si dice que no acepta; "no_mencionada" si no dice nada o dice que no se especifica.
- pets_species: SOLO las especies que el aviso permite. Si dice "se aceptan gatos, perros no permitidos" -> ["gato"]. Si dice "solo se admiten perros" -> ["perro"]. Si acepta "perros y gatos" o "sin restricción de especie" -> [].
- pets_max_kg: límite de peso por mascota en kg si el aviso lo declara ("hasta N kg", "límite de N kg"). null si no hay límite.
- parking: "calle" si dice "en la calle"; "visitas" si es estacionamiento de visitas; "ninguno" si dice que no incluye o "sin estacionamiento"; "asignado" solo si el aviso usa la palabra "asignado"; "propio" si incluye estacionamiento sin más detalle ("incluye 1 estacionamiento", "estacionamiento propio", "en subterráneo"); "no_mencionado" si no aparece.

Ignora frases de marketing ("oportunidad", "bajo el presupuesto", "negociable", "comuna favorita", "a pasos de todo"): no son hechos."""


# v3 = v2 para precio/arriendo/dormitorios/distancia (lo que v2 mejoró en dev: precio 13→0 errores,
# dormitorios 27→6) + las líneas de v1 para mascotas y estacionamiento (lo que v2 empeoró en dev:
# pets_max_kg 6→32, parking 5→22, pets_species 2→18). Lección: en un 3.8B, reescribir una regla
# tiene efectos no locales sobre las demás; por eso cada versión se mide en dev antes de test.
SYSTEM_V3 = """Eres un extractor de datos de avisos inmobiliarios chilenos. Recibes el texto de UNA propiedad y devuelves SOLO los hechos literales que el texto declara, en JSON. No evalúas, no opinas, no calculas, no conviertes unidades. Cada campo *_text debe ser una COPIA EXACTA de un fragmento del aviso: nunca inventes ni completes un número.

Reglas por campo:
- location: la comuna donde está la propiedad (la palabra que sigue a "Depto en" / "Casa en"). null si no aparece.
- bedrooms: número de dormitorios REALES. La notación "ND/MB" significa N dormitorios y M baños: el número ANTES de la D son los dormitorios; el número antes de la B son baños y NO se cuenta. "N dormitorios" = N. NO cuentes escritorios, loggias, salas de estar, ni ambientes "convertibles" o "que pueden usarse como dormitorio": "1 dormitorio + sala que puede usarse como dormitorio" = 1. "Estudio" o "ambiente único" = 0.
- price_text: copia exacta del precio de venta con su unidad tal como aparece en el aviso (incluye el signo $ si lo tiene, o la palabra UF si la tiene). Nunca cambies la unidad.
- rent_text: copia exacta del arriendo mensual estimado/referencial (el monto que aparece junto a "/mes"). null si el aviso no publica arriendo.
- distance_metro_text: copia exacta de la distancia en metros o km a la estación de metro. null si no aparece. "minutos caminando" NO es una distancia: no lo copies aquí.
- distance_bus_text: copia exacta de la distancia en metros o km al paradero de buses troncal. null si no aparece.
- pets_policy: "permitidas" si el texto dice que acepta mascotas; "no_permitidas" si dice que no; "no_mencionada" si el texto no dice nada o dice que no se especifica.
- pets_species: especies que el texto permite explícitamente: ["perro"], ["gato"] o ["perro","gato"]. Lista vacía [] si acepta mascotas sin restricción de especie o si no aplica.
- pets_max_kg: límite de peso por mascota en kg si el texto lo declara (p.ej. "hasta 20kg" = 20). null si no hay límite.
- parking: "propio" si incluye estacionamiento (sin más detalle, "1 estacionamiento", "en subterráneo"); "asignado" si dice asignado; "visitas" si es de visitas; "calle" si es en la calle; "ninguno" si dice que no incluye; "no_mencionado" si no aparece.

Ignora frases de marketing ("oportunidad", "bajo el presupuesto", "negociable", "comuna favorita", "a pasos de todo"): no son hechos."""


# v4 = v3 sin la frase inicial "nunca inventes ni completes un número" (hipótesis: v3 la
# sobre-generalizaba a pets_max_kg). En dev v4 dio 8/30 igual que v3, con pets_max_kg todavía
# en 24 nulos: la hipótesis era falsa. La regresión viene de la interacción entre las líneas
# reescritas de precio/dormitorios/distancia y el campo de mascotas, y no es aislable por
# inspección. Lección para el PDF: en un 3.8B el prompt no es composicional campo a campo.
SYSTEM_V4 = """Eres un extractor de datos de avisos inmobiliarios chilenos. Recibes el texto de UNA propiedad y devuelves SOLO los hechos literales que el texto declara, en JSON. No evalúas, no opinas, no calculas, no conviertes unidades.

Reglas por campo:
- location: la comuna donde está la propiedad (la palabra que sigue a "Depto en" / "Casa en"). null si no aparece.
- bedrooms: número de dormitorios REALES. La notación "ND/MB" significa N dormitorios y M baños: el número ANTES de la D son los dormitorios; el número antes de la B son baños y NO se cuenta. "N dormitorios" = N. NO cuentes escritorios, loggias, salas de estar, ni ambientes "convertibles" o "que pueden usarse como dormitorio": "1 dormitorio + sala que puede usarse como dormitorio" = 1. "Estudio" o "ambiente único" = 0.
- price_text: copia exacta del precio de venta con su unidad tal como aparece en el aviso (incluye el signo $ si lo tiene, o la palabra UF si la tiene). Nunca cambies la unidad.
- rent_text: copia exacta del arriendo mensual estimado/referencial (el monto que aparece junto a "/mes"). null si el aviso no publica arriendo.
- distance_metro_text: copia exacta de la distancia en metros o km a la estación de metro. null si no aparece. "minutos caminando" NO es una distancia: no lo copies aquí.
- distance_bus_text: copia exacta de la distancia en metros o km al paradero de buses troncal. null si no aparece.
- pets_policy: "permitidas" si el texto dice que acepta mascotas; "no_permitidas" si dice que no; "no_mencionada" si el texto no dice nada o dice que no se especifica.
- pets_species: especies que el texto permite explícitamente: ["perro"], ["gato"] o ["perro","gato"]. Lista vacía [] si acepta mascotas sin restricción de especie o si no aplica.
- pets_max_kg: límite de peso por mascota en kg si el texto lo declara (p.ej. "hasta 20kg" = 20). null si no hay límite.
- parking: "propio" si incluye estacionamiento (sin más detalle, "1 estacionamiento", "en subterráneo"); "asignado" si dice asignado; "visitas" si es de visitas; "calle" si es en la calle; "ninguno" si dice que no incluye; "no_mencionado" si no aparece.

Ignora frases de marketing ("oportunidad", "bajo el presupuesto", "negociable", "comuna favorita", "a pasos de todo"): no son hechos."""

# v5 = "localizar, no interpretar". Diagnóstico sobre tools_phi4_v1 (extract_report, 352 propiedades):
# los errores se concentran en los campos que el modelo debía INTERPRETAR (bedrooms 42, parking 10,
# pets_species 12, pets_max_kg 4) y en alucinaciones de unidad/ejemplo en los que debía COPIAR
# (price 15, rent 4). v5 pide solo COPIAS LITERALES de la cláusula de cada tema y tres respuestas
# cerradas sobre mascotas; grounding.py verifica que cada span exista en el aviso y lo parsea.
# Sin números de ejemplo en el prompt (v1 contaminaba: "$980.000" aparecía como arriendo).
SPANS_SCHEMA_V5: Dict = {
    "type": "object",
    "properties": {
        "location_text": {"type": ["string", "null"]},
        "bedrooms_text": {"type": ["string", "null"]},
        "price_text": {"type": ["string", "null"]},
        "rent_text": {"type": ["string", "null"]},
        "distance_metro_text": {"type": ["string", "null"]},
        "distance_bus_text": {"type": ["string", "null"]},
        "parking_text": {"type": ["string", "null"]},
        "pets_text": {"type": ["string", "null"]},
        "acepta_mascotas": {"type": "string", "enum": ["si", "no", "no_dice"]},
        "acepta_perros": {"type": "string", "enum": ["si", "no", "no_dice"]},
        "acepta_gatos": {"type": "string", "enum": ["si", "no", "no_dice"]},
    },
    "required": ["location_text", "bedrooms_text", "price_text", "rent_text", "distance_metro_text",
                 "distance_bus_text", "parking_text", "pets_text",
                 "acepta_mascotas", "acepta_perros", "acepta_gatos"],
}

SYSTEM_V5 = """Eres un localizador de frases en avisos inmobiliarios chilenos. Recibes el texto de UNA propiedad. Para cada campo devuelves la COPIA LITERAL del fragmento del aviso que habla de ese tema, o null si el aviso no lo menciona. No interpretas, no calculas, no conviertes, no resumes ni corriges: copia el fragmento tal cual, con los mismos números, signos y unidades que aparecen en el aviso.

Campos (fragmentos copiados):
- location_text: el fragmento que dice dónde está la propiedad (la frase que empieza con "Depto en" o "Casa en").
- bedrooms_text: el fragmento del aviso que dice cuántos dormitorios y baños tiene, copiado tal cual con sus números. Muchos avisos lo abrevian como un número pegado a la letra D (dormitorios), una barra, y un número pegado a la letra B (baños): copia esa abreviatura tal como aparece. Incluye en el fragmento los ambientes extra que mencione en la misma frase (escritorio, loggia, sala de estar). Si el aviso dice "estudio" o "ambiente único", copia esa frase.
- price_text: el fragmento con el precio de venta, con su signo $ o su UF exactamente como aparece.
- rent_text: el fragmento con el arriendo mensual estimado o referencial (el que dice "/mes"). null si el aviso no publica arriendo.
- distance_metro_text: la frase completa sobre la distancia a la estación de metro, aunque también mencione minutos caminando. null si no aparece.
- distance_bus_text: la frase completa sobre la distancia a un paradero de buses troncal. null si no aparece.
- parking_text: la frase completa sobre estacionamiento. null si el aviso no lo menciona.
- pets_text: la frase completa sobre mascotas (política, especies, límite de peso). null si el aviso no lo menciona.

Campos (respuestas cerradas, solo sobre lo que dice pets_text):
- acepta_mascotas: "si" si el aviso dice que acepta mascotas (aunque sea con condiciones o límites); "no" si dice que no acepta; "no_dice" si no lo menciona o dice que no se especifica.
- acepta_perros: "si" si permite perros explícitamente o acepta mascotas sin restringir la especie; "no" si dice que los perros no están permitidos o que solo admite gatos; "no_dice" en otro caso.
- acepta_gatos: lo mismo para gatos.

Las frases de marketing ("oportunidad", "bajo el presupuesto", "negociable", "comuna favorita", "a pasos de todo") no son hechos: no las copies en ningún campo."""

PROMPTS = {"v1": SYSTEM_V1, "v2": SYSTEM_V2, "v3": SYSTEM_V3, "v4": SYSTEM_V4, "v5": SYSTEM_V5}
# Versiones cuyo esquema es de SPANS (se pasan por grounding.py para obtener Facts).
SPAN_VERSIONS = {"v5"}
# Versión REPORTADA en la E2: v5 (test 51/51 e1_strict, dev 30/30). v1 se conserva como
# evidencia de la iteración (test 30/51) y v2–v4 perdieron en dev y nunca se corrieron en test.
DEFAULT_PROMPT = "v5"
SYSTEM = PROMPTS[DEFAULT_PROMPT]


@dataclass
class Facts:
    location: Optional[str]
    bedrooms: Optional[int]             # None = no verificable (v5: cláusula sin número)
    price_text: str
    rent_text: Optional[str]
    distance_metro_text: Optional[str]
    distance_bus_text: Optional[str]
    pets_policy: str
    pets_species: List[str]
    pets_max_kg: Optional[float]
    parking: str
    # trazabilidad
    raw: str = ""
    prompt_tokens: int = 0
    output_tokens: int = 0
    wall_s: float = 0.0
    error: Optional[str] = None
    spans: Dict = field(default_factory=dict)        # v5: lo que devolvió el modelo, antes del anclaje
    warnings: List[str] = field(default_factory=list)  # v5: spans no literales / números no anclados

    def to_dict(self) -> Dict:
        return asdict(self)


def ollama_chat(model: str, system: str, user: str, options: Dict, fmt=None,
                timeout: int = 120, url: str = OLLAMA_URL) -> Dict:
    body = {
        "model": model, "stream": False, "options": options, "keep_alive": "15m",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if fmt is not None:
        body["format"] = fmt
    req = urllib.request.Request(f"{url}/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def default_options(num_ctx: int = 2048, num_predict: int = 256) -> Dict:
    # Determinista y corto: cada llamada ve ~300 tokens de entrada y emite ~80.
    return {"temperature": 0.0, "seed": 0, "num_ctx": num_ctx, "num_predict": num_predict}


def extract_facts(model: str, prop_id: str, text: str, options: Optional[Dict] = None,
                  timeout: int = 120, prompt_version: str = DEFAULT_PROMPT) -> Facts:
    """Una llamada al modelo por propiedad. Nunca recibe el perfil del comprador."""
    options = options or default_options()
    system = PROMPTS[prompt_version]
    spans_mode = prompt_version in SPAN_VERSIONS
    schema = SPANS_SCHEMA_V5 if spans_mode else FACTS_SCHEMA
    user = f"Texto del aviso {prop_id}:\n\"{text}\"\n\nDevuelve el JSON de hechos."
    t0 = time.time()
    try:
        r = ollama_chat(model, system, user, options, fmt=schema, timeout=timeout)
        raw = r.get("message", {}).get("content", "")
        obj = json.loads(raw)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        return Facts(location=None, bedrooms=None, price_text="", rent_text=None,
                     distance_metro_text=None, distance_bus_text=None,
                     pets_policy="no_mencionada", pets_species=[], pets_max_kg=None,
                     parking="no_mencionado", raw="", wall_s=time.time() - t0, error=str(e))
    meta = dict(raw=raw, prompt_tokens=r.get("prompt_eval_count") or 0,
                output_tokens=r.get("eval_count") or 0, wall_s=round(time.time() - t0, 2))
    if spans_mode:
        # El modelo solo localizó fragmentos; grounding.py los ancla al aviso y los interpreta.
        from . import grounding
        kwargs, warnings = grounding.facts_from_spans(obj, text)
        return Facts(**kwargs, spans=obj, warnings=warnings, **meta)
    return Facts(
        location=obj.get("location"),
        bedrooms=int(obj.get("bedrooms") or 0),
        price_text=obj.get("price_text") or "",
        rent_text=obj.get("rent_text"),
        distance_metro_text=obj.get("distance_metro_text"),
        distance_bus_text=obj.get("distance_bus_text"),
        pets_policy=obj.get("pets_policy") or "no_mencionada",
        pets_species=list(obj.get("pets_species") or []),
        pets_max_kg=obj.get("pets_max_kg"),
        parking=obj.get("parking") or "no_mencionado",
        **meta,
    )
