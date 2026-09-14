"""Renderiza el prompt que ve el modelo a partir de un caso.

Es el MISMO prompt para el baseline y para la solución: la intervención de la
E2 no cambia el prompt, cambia el modelo (destilado). El esquema de salida es el
del PDF del Entregable 1 (id, price_clp, roi_pct / id, failed_constraints).

Mantiene las SOFT CONSTRAINTS de la E1 (data/prompt_base.txt): ubicación preferida
y ROI no descalifican, pero fijan el orden de `approved_matches` (mejor primero).
El orden es verificable de forma determinista (rules.Expected.ranking).
"""
from __future__ import annotations

from .schema import Case

SYSTEM = (
    "Eres el motor de validación de una plataforma B2B de matching inmobiliario. "
    "Tu tarea es procesar el texto no estructurado de corredores de propiedades y "
    "cruzarlo contra los criterios estrictos (Hard Constraints) de un comprador, "
    "además de ordenar las aprobadas según sus preferencias (Soft Constraints). "
    "No puedes cometer errores aritméticos. No puedes incluir texto conversacional "
    "en tu respuesta, solo el objeto JSON crudo."
)

# Instrucción explícita de formato. Sin ella, phi4-mini envuelve el JSON en fences
# markdown en 50/51 casos y el baseline falla por formato en vez de por lógica.
FORMAT_RULE = (
    "IMPORTANTE: tu respuesta debe empezar con el carácter { y terminar con }. "
    "No uses bloques de código markdown (```), ni explicaciones antes o después del JSON. "
    "price_clp es un entero en pesos chilenos; roi_pct es un número con dos decimales "
    "(null si el texto no publica arriendo). approved_matches va ordenada de mejor a peor."
)

OUTPUT_SCHEMA = """{
  "approved_matches": [
    { "id": "...", "price_clp": 0, "roi_pct": 0.0 }
  ],
  "rejected": [
    { "id": "...", "failed_constraints": ["..."] }
  ]
}"""


def fmt_clp(n: int) -> str:
    return "$" + f"{n:,}".replace(",", ".")


def fmt_kg(kg: float) -> str:
    return f"{kg:g}kg"


def render_profile(case: Case) -> str:
    hc = case.hard_constraints
    especie = "perro" if hc.mascota_especie == "perro" else "gato"
    lines = [
        "PERFIL DEL COMPRADOR — HARD CONSTRAINTS (descalifican si se incumplen):",
        f"1. Presupuesto Máximo de Compra: {fmt_clp(hc.presupuesto_max_clp)} CLP "
        "(usa el valor de la UF de hoy si el precio viene en UF).",
        f"2. Mascotas: Tiene 1 {especie} de {fmt_kg(hc.mascota_kg)} (la propiedad debe permitir "
        "explícitamente mascotas de ese tamaño y especie).",
        f"3. Distancia máxima a transporte público (metro O paradero de buses troncal): "
        f"{hc.distancia_max_transporte_m} m.",
        f"4. Dormitorios: Mínimo {hc.dormitorios_min} dormitorios reales.",
    ]
    if hc.estacionamiento_requerido:
        lines.append(
            "5. Estacionamiento: Debe incluir al menos 1 estacionamiento propio o asignado "
            "(no sirve estacionamiento de visitas ni en la calle)."
        )
    else:
        lines.append("5. Estacionamiento: No es requisito.")
    return "\n".join(lines)


def render_soft(case: Case) -> str:
    prefs = case.soft_constraints.ubicaciones_preferidas
    ubic = " o ".join(prefs) if prefs else "sin preferencia"
    return "\n".join([
        "SOFT CONSTRAINTS (no descalifican, pero determinan el ranking de las aprobadas):",
        f"- Ubicación preferida: {ubic} (mayor preferencia). Una propiedad en comuna "
        "preferida NO se aprueba si viola una Hard Constraint.",
        "- ROI esperado: (arriendo mensual estimado × 12) / precio de la propiedad × 100. "
        "Mayor ROI = mejor score.",
        "- Orden del ranking: primero las de comuna preferida, luego el resto; dentro de "
        "cada grupo, de mayor a menor roi_pct (las sin arriendo publicado al final del grupo).",
    ])


def render_catalog(case: Case) -> str:
    return "\n\n".join(f'[{p.id}] "{p.text}"' for p in case.properties)


def render_prompt(case: Case) -> str:
    uf = f"{int(case.uf_value):,}".replace(",", ".")
    return "\n\n".join([
        SYSTEM,
        f"VALOR UF HOY: ${uf} CLP",
        render_profile(case),
        render_soft(case),
        "CATÁLOGO RAW DE PROPIEDADES (datos extraídos con OCR/Scraping):\n\n" + render_catalog(case),
        "TAREA: Evalúa cada propiedad contra las 5 Hard Constraints. Las que violen INCLUSO UNA "
        "deben ir a \"rejected\" con la razón exacta. Para las aprobadas, calcula price_clp "
        "(precio en CLP, convirtiendo desde UF si corresponde) y roi_pct = "
        "(arriendo mensual × 12) / price_clp × 100, con dos decimales, y ordénalas en "
        "\"approved_matches\" según las Soft Constraints, de mejor a peor (las primeras 3 "
        "son el Top 3). Responde ÚNICAMENTE con el siguiente JSON, sin texto adicional:\n\n"
        + OUTPUT_SCHEMA,
        FORMAT_RULE,
    ])


if __name__ == "__main__":
    import sys
    print(render_prompt(Case.load(sys.argv[1])))
