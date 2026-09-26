"""Salidas: terminal, Markdown para compartir y JSON completo (trazable) + el JSON
estricto de la E1."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

from .analyze import APPROVED, REJECTED, REVIEW, Result, e1_output, rank
from .listing import fmt_cl


def _price(r: Result) -> str:
    d = r.decision
    if d and d.price_clp:
        return f"${fmt_cl(d.price_clp)}"
    l = r.listing
    return f"{l.price_currency} {fmt_cl(l.price_value, 2)}" if l.price_value else "—"


def _transit(r: Result) -> str:
    l = r.listing
    return f"{l.transit_kind} {l.transit_name} ~{l.transit_walk_m} m" if l.transit_name else "—"


def _row(r: Result) -> List[str]:
    l = r.listing
    beds = f"{l.bedrooms}" + (f"–{l.bedrooms_max}" if l.bedrooms_max else "") if l.bedrooms is not None else "?"
    return [l.source, (l.title or "")[:48], l.comuna or "", _price(r), beds, _transit(r), l.url]


def summary_text(results: List[Result], discarded: Counter, sources: Dict[str, Dict]) -> str:
    by = {b: rank([r for r in results if r.bucket == b]) for b in (APPROVED, REVIEW, REJECTED)}
    out = []
    out.append(f"\n== APROBADAS ({len(by[APPROVED])}) — cumplen todos los filtros con datos verificados ==")
    for i, r in enumerate(by[APPROVED], 1):
        s, t, c, p, b, tr, u = _row(r)
        out.append(f" {i:2}. [{s}] {t} · {c} · {p} · {b} dorm · {tr}\n     {u}")
    out.append(f"\n== REVISAR ({len(by[REVIEW])}) — no incumplen nada verificable, pero falta un dato ==")
    for r in by[REVIEW]:
        s, t, c, p, b, tr, u = _row(r)
        falta = ", ".join(r.unverifiable) or r.note
        out.append(f"  · [{s}] {t} · {c} · {p} · falta: {falta}\n     {u}")
    reasons = Counter(c for r in by[REJECTED] for c in r.violated)
    out.append(f"\n== RECHAZADAS ({len(by[REJECTED])}) por el analizador; incumplimientos: "
               + (", ".join(f"{k} {v}" for k, v in reasons.most_common()) or "—"))
    if discarded:
        out.append(f"== DESCARTADAS antes del análisis por datos del portal: "
                   + ", ".join(f"{k} {v}" for k, v in discarded.most_common()))
    out.append("\n== FUENTES ==")
    for name, st in sources.items():
        state = "OK" if st["ok"] else "FALLÓ"
        extra = f" — {st['error']}" if st.get("error") else ""
        out.append(f"  {name:17} {state:5} avisos={st.get('listings', 0):3} peticiones={st.get('requests', 0):3}{extra}")
        for w in st.get("warnings", [])[:5]:
            out.append(f"  {'':17}   · {w}")
    return "\n".join(out)


def markdown(results: List[Result], profile_summary: str, uf: float, sources: Dict[str, Dict]) -> str:
    lines = ["# Búsqueda de propiedades", "", "```", profile_summary, f"  UF del día         : ${fmt_cl(uf, 2)}", "```", ""]
    head = "| # | Fuente | Aviso | Comuna | Precio | Dorm. | Transporte | Enlace |\n|---|---|---|---|---|---|---|---|"
    for bucket, title in ((APPROVED, "Aprobadas"), (REVIEW, "Por revisar (falta un dato)")):
        rs = rank([r for r in results if r.bucket == bucket])
        lines += [f"## {title} ({len(rs)})", "", head]
        for i, r in enumerate(rs, 1):
            s, t, c, p, b, tr, u = _row(r)
            lines.append(f"| {i} | {s} | {t.replace('|', '/')} | {c} | {p} | {b} | {tr} | [ver]({u}) |")
            if bucket == REVIEW:
                lines[-1] = lines[-1][:-1] + f" falta: {', '.join(r.unverifiable) or r.note} |"
        lines.append("")
    lines += ["## Fuentes", ""]
    for name, st in sources.items():
        lines.append(f"- **{name}**: {'OK' if st['ok'] else 'falló — ' + st.get('error', '')}"
                     f" ({st.get('listings', 0)} avisos)")
    lines += ["", "La distancia a transporte es una estimación: línea recta a la estación más cercana "
              "de OpenStreetMap × 1,3. Los datos vienen de los portales y pueden estar desactualizados."]
    return "\n".join(lines) + "\n"


def write_all(out_dir: Path, results: List[Result], discarded: Counter, sources: Dict[str, Dict],
              profile, uf: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultados.json").write_text(json.dumps({
        "perfil": profile.__dict__, "uf": uf, "fuentes": sources, "descartadas_prefiltro": dict(discarded),
        "resultados": [r.to_dict() for r in rank(results)],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "salida_e1.json").write_text(json.dumps(e1_output(results), ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    (out_dir / "reporte.md").write_text(markdown(results, profile.summary(), uf, sources), encoding="utf-8")
