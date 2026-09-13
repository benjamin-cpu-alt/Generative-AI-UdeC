"""Juez 0/1 de la salida de un modelo.

Criterio principal = las 3 condiciones del Entregable 1, en este orden:
  3. Texto conversacional / esquema JSON incumplido      -> schema_error
  1. Aprueba una propiedad que viola una hard constraint -> false_approval
  2. Error aritmético (UF->CLP o ROI)                     -> arithmetic_error

Métrica secundaria (exact_match): el conjunto aprobado y el rechazado coinciden
exactamente con el esperado. Se calcula siempre, pero no forma parte del
criterio principal para mantener la definición de la E1.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .rules import Expected, expected_output
from .schema import Case

PRICE_TOL_CLP = 1          # tolerancia en CLP para price_clp
ROI_TOL_PP = 0.05          # tolerancia en puntos porcentuales para el ROI

# El PDF de la E1 usa "roi_pct"; prompt_base.txt usa "roi_calculado_pct".
ROI_KEYS = ("roi_pct", "roi_calculado_pct")

REASON_OK = "ok"
REASON_SCHEMA = "schema_error"
REASON_FALSE_APPROVAL = "false_approval"
REASON_ARITHMETIC = "arithmetic_error"


@dataclass
class Verdict:
    case_id: str
    e1_correct: bool                  # criterio principal (E1)
    exact_match: bool                 # métrica secundaria
    reason: str                       # ok | schema_error | false_approval | arithmetic_error
    details: List[str] = field(default_factory=list)
    approved_ids: List[str] = field(default_factory=list)
    rejected_ids: List[str] = field(default_factory=list)
    expected_approved: List[str] = field(default_factory=list)
    expected_rejected: List[str] = field(default_factory=list)
    # Diagnóstico (no forma parte del criterio): veredicto tras limpiar el formato.
    lenient_e1: Optional[bool] = None
    lenient_reason: Optional[str] = None

    def as_row(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "e1_correct": int(self.e1_correct),
            "exact_match": int(self.exact_match),
            "reason": self.reason,
            "details": " | ".join(self.details),
            "lenient_e1": "" if self.lenient_e1 is None else int(self.lenient_e1),
            "lenient_reason": self.lenient_reason or "",
        }


# ---------------------------------------------------------------- parseo ----

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_strict(raw: str) -> Tuple[Optional[dict], Optional[str]]:
    """La respuesta completa debe ser un único objeto JSON. Devuelve (obj, error)."""
    text = raw.strip()
    if not text:
        return None, "respuesta vacía"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None, _diagnose_non_json(raw)
    if not isinstance(obj, dict):
        return None, "el JSON raíz no es un objeto"
    return obj, None


def _diagnose_non_json(raw: str) -> str:
    """Clasifica por qué falló el parseo estricto (útil para la sección de límites)."""
    if _THINK_RE.search(raw):
        return "bloque <think> antes del JSON"
    if _FENCE_RE.search(raw):
        return "JSON envuelto en fences markdown"
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return "no hay objeto JSON en la respuesta"
    try:
        json.loads(raw[start:end + 1])
        return "texto conversacional alrededor del JSON"
    except json.JSONDecodeError:
        return "JSON malformado"


def lenient_clean(raw: str) -> str:
    """SOLO para diagnóstico: quita <think> y fences, y recorta al objeto JSON exterior.
    No se usa en la métrica principal (el criterio E1 exige JSON crudo)."""
    text = _THINK_RE.sub("", raw)
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    return text.strip()


def validate_schema(obj: dict, valid_ids: set) -> Tuple[Optional[dict], Optional[str]]:
    """Comprueba claves y tipos. Devuelve una versión normalizada o un error."""
    for key in ("approved_matches", "rejected"):
        if key not in obj:
            return None, f"falta la clave '{key}'"
        if not isinstance(obj[key], list):
            return None, f"'{key}' no es una lista"

    approved = []
    for i, item in enumerate(obj["approved_matches"]):
        if not isinstance(item, dict) or "id" not in item:
            return None, f"approved_matches[{i}] sin 'id'"
        if "price_clp" not in item:
            return None, f"approved_matches[{i}] ({item['id']}) sin 'price_clp'"
        roi_key = next((k for k in ROI_KEYS if k in item), None)
        if roi_key is None:
            return None, f"approved_matches[{i}] ({item['id']}) sin ROI ({'/'.join(ROI_KEYS)})"
        if not _is_number(item["price_clp"]):
            return None, f"{item['id']}: price_clp no es numérico"
        if item[roi_key] is not None and not _is_number(item[roi_key]):
            return None, f"{item['id']}: {roi_key} no es numérico"
        approved.append({"id": _norm_id(item["id"], valid_ids), "price_clp": item["price_clp"], "roi": item[roi_key]})

    rejected = []
    for i, item in enumerate(obj["rejected"]):
        if not isinstance(item, dict) or "id" not in item:
            return None, f"rejected[{i}] sin 'id'"
        if "failed_constraints" not in item or not isinstance(item["failed_constraints"], list):
            return None, f"rejected[{i}] ({item['id']}) sin lista 'failed_constraints'"
        rejected.append({"id": _norm_id(item["id"], valid_ids), "failed_constraints": item["failed_constraints"]})

    ids = [a["id"] for a in approved] + [r["id"] for r in rejected]
    unknown = [i for i in ids if i not in valid_ids]
    if unknown:
        return None, f"ids inexistentes en el catálogo: {unknown}"
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        return None, f"ids repetidos o en ambas listas: {sorted(dupes)}"

    return {"approved": approved, "rejected": rejected}, None


def _norm_id(x: Any, valid_ids: set) -> str:
    """'[PROP-A42]' / ' prop-a42 ' / 'A42' -> 'PROP-A42'. Formato distinto no es id distinto.
    Un id que no exista en el catálogo se devuelve tal cual y falla después como inexistente."""
    s = str(x).strip().strip("[]").strip().upper()
    if s in valid_ids:
        return s
    by_suffix = {v.split("-", 1)[-1]: v for v in valid_ids}
    return by_suffix.get(s.split("-", 1)[-1], s)


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ------------------------------------------------------------- veredicto ----

def verify(case: Case, raw_response: str, expected: Optional[Expected] = None) -> Verdict:
    exp = expected or expected_output(case)
    v = Verdict(
        case_id=case.id, e1_correct=False, exact_match=False, reason=REASON_SCHEMA,
        expected_approved=sorted(exp.approved_ids),
        expected_rejected=sorted(exp.rejected_ids),
    )

    obj, err = parse_strict(raw_response)
    if err:
        v.details.append(err)
        _fill_lenient(v, case, raw_response, exp)
        return v
    norm, err = validate_schema(obj, set(exp.by_id))
    if err:
        v.details.append(err)
        return v

    v.approved_ids = sorted(a["id"] for a in norm["approved"])
    v.rejected_ids = sorted(r["id"] for r in norm["rejected"])

    # Condición 1: aprobación de una propiedad que viola una hard constraint.
    false_approvals = [
        f"{a['id']} aprobada pero viola {exp.by_id[a['id']].failed_constraints}"
        for a in norm["approved"] if not exp.by_id[a["id"]].approved
    ]
    # Condición 2: aritmética sobre las aprobadas (UF->CLP y ROI).
    arithmetic = []
    for a in norm["approved"]:
        e = exp.by_id[a["id"]]
        if abs(a["price_clp"] - e.price_clp) > PRICE_TOL_CLP:
            arithmetic.append(f"{a['id']}: price_clp={a['price_clp']} esperado={e.price_clp}")
        if e.roi_pct is not None:
            if a["roi"] is None or abs(a["roi"] - e.roi_pct) > ROI_TOL_PP:
                arithmetic.append(f"{a['id']}: roi={a['roi']} esperado={e.roi_pct}")

    # Métrica secundaria.
    v.exact_match = (
        set(v.approved_ids) == exp.approved_ids and set(v.rejected_ids) == exp.rejected_ids
    )
    if not v.exact_match:
        missing_ok = sorted(exp.approved_ids - set(v.approved_ids))
        if missing_ok:
            v.details.append(f"rechazo falso u omisión de aprobadas: {missing_ok}")
        absent = sorted(set(exp.by_id) - set(v.approved_ids) - set(v.rejected_ids))
        if absent:
            v.details.append(f"propiedades sin clasificar: {absent}")

    if false_approvals:
        v.reason = REASON_FALSE_APPROVAL
        v.details = false_approvals + v.details
        return v
    if arithmetic:
        v.reason = REASON_ARITHMETIC
        v.details = arithmetic + v.details
        return v

    v.reason = REASON_OK
    v.e1_correct = True
    return v


def _fill_lenient(v: Verdict, case: Case, raw: str, exp: Expected) -> None:
    cleaned = lenient_clean(raw)
    if not cleaned or cleaned == raw.strip():
        return
    inner = verify(case, cleaned, exp)
    v.lenient_e1 = inner.e1_correct
    v.lenient_reason = inner.reason
    v.exact_match = inner.exact_match  # el conjunto aprobado/rechazado sí es observable
    v.approved_ids, v.rejected_ids = inner.approved_ids, inner.rejected_ids
    if inner.details:
        v.details.append("tras limpiar formato: " + " | ".join(inner.details))


# ------------------------------------------------------------------- CLI ----

def _main(argv: List[str]) -> int:
    import sys
    if len(argv) != 2:
        print("uso: python -m matcher.verifier <caso.json> <respuesta.txt>", file=sys.stderr)
        return 2
    case = Case.load(argv[0])
    with open(argv[1], encoding="utf-8") as f:
        raw = f.read()
    v = verify(case, raw)
    print(json.dumps(v.__dict__, ensure_ascii=False, indent=2))
    return 0 if v.e1_correct else 1


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
