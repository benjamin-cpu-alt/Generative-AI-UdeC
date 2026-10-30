"""Sistema multiagente de la E3: Lector -> Verificador <-> Lector, Decisor <-> Verificador.

Cada agente decide qué pasa después; el orquestador solo ejecuta esa decisión dentro de
un presupuesto de rondas y registra cada mensaje en la traza.

  Lector       (por aviso) copia el fragmento literal de cada tema. La herramienta
               `anclar` los convierte en hechos. Ante una relectura decide, campo por
               campo, entre un fragmento nuevo y null ("el aviso no lo dice").
  Verificador  (por aviso) revisa los hechos contra el aviso. Por campo: corregir (llama a
               `comprobar`), releer (vuelve al Lector) o no_verificable. Sin objeciones,
               el aviso pasa al Decisor. Si `comprobar` rechaza una corrección, recibe
               el motivo y puede revisarla (retroalimentación de la herramienta).
  Decisor      (por caso) ve el resultado de `evaluar` y decide: cerrar (llama a
               `ordenar` y termina) o consultar al Verificador por un dato de un aviso.

Condiciones de parada: el Decisor cierra; o se agotan las rondas (relecturas por aviso,
reintentos tras `comprobar`, rondas de consulta). Un dato que sigue sin leerse nunca
aprueba: la restricción queda no_verificable y falla.

Ablaciones (Config): esquema, literal, refinar, retro, herramientas_decisor. Cada una
quita UNA técnica y deja el resto igual. refinar (self-refine) actúa en dos bucles; releer y
consultar quitan solo uno de ellos, para medirlos por separado.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from matcher import grounding, prompt as base_prompt
from matcher.extract import SPANS_SCHEMA_V5
from matcher.pipeline import OUTPUT_SCHEMA
from matcher.schema import Case, Property

from . import llm, tools
from .tools import CAMPOS, SPAN_DE

# Restricción(es) que depende(n) de cada campo (para filtrar las consultas del Decisor).
CAMPO2C = {"precio": ("presupuesto",), "mascotas": ("mascotas",), "mascotas_kg": ("mascotas",),
           "distancia": ("distancia_transporte",),
           "dormitorios": ("dormitorios",), "estacionamiento": ("estacionamiento",)}

def rev_schema(campos: List[str], acciones: List[str]) -> Dict:
    """Las revisiones solo pueden nombrar los campos que se le muestran como dudosos."""
    return {
        "type": "object",
        "properties": {"revisiones": {"type": "array", "maxItems": len(campos), "items": {
            "type": "object",
            "properties": {"campo": {"type": "string", "enum": list(campos)},
                           "accion": {"type": "string", "enum": list(acciones)},
                           "evidencia": {"type": ["string", "null"], "maxLength": 160},
                           "valor": {"type": ["string", "null"], "maxLength": 40}},
            "required": ["campo", "accion", "evidencia", "valor"]}}},
        "required": ["revisiones"],
    }


ACCIONES = {"revisar": ["confirmar", "corregir", "releer", "no_verificable"],
            "consulta": ["confirmar", "corregir", "releer", "no_verificable"],
            "retro": ["mantener", "corregir", "no_verificable"]}


def decisor_schema(ids: List[str]) -> Dict:
    return {
        "type": "object",
        "properties": {
            "accion": {"type": "string", "enum": ["cerrar", "consultar"]},
            "consultas": {"type": "array", "items": {
                "type": "object",
                "properties": {"id": {"type": "string", "enum": ids},
                               "campo": {"type": "string", "enum": list(CAMPOS)},
                               "motivo": {"type": "string"}},
                "required": ["id", "campo", "motivo"]}}},
        "required": ["accion", "consultas"],
    }


@dataclass
class Config:
    model: str = "phi4-mini:latest"
    lector: str = "v1"
    verificador: str = "v1"
    decisor: str = "v2"               # v2: convención E3 (mascotas sin_confirmar, estudio = 1)
    grounding: str = "g3"
    esquema: bool = True               # −esquema: salida libre, se busca el JSON en el texto
    literal: bool = True               # −literal: `comprobar` no exige que el valor salga de la evidencia
    refinar: bool = True               # −refinar: sin relecturas del Lector ni consultas del Decisor
    releer: bool = True                # −releer: solo sin relecturas del Lector
    consultar: bool = True             # −consultar: solo sin consultas del Decisor
    retro: bool = True                 # −retro: el rechazo de `comprobar` no vuelve al Verificador
    herramientas_decisor: bool = True  # −herramientas_A3: el Decisor escribe el JSON final a mano
    max_relecturas: int = 2
    max_retro: int = 1
    max_consultas: int = 1
    max_consultas_por_ronda: int = 4

    @property
    def nombre(self) -> str:
        quitadas = [k for k in ("esquema", "literal", "refinar", "releer", "consultar", "retro",
                                "herramientas_decisor") if not getattr(self, k)]
        return "full" if not quitadas else "sin_" + "_".join(quitadas)


@dataclass
class Traza:
    case_id: str
    mensajes: List[Dict] = field(default_factory=list)
    llamadas: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    wall_s: float = 0.0
    errores: List[str] = field(default_factory=list)
    acciones: Dict[str, int] = field(default_factory=dict)

    def msg(self, de: str, para: str, tipo: str, contenido, aviso: Optional[str] = None, **extra) -> None:
        m = {"paso": len(self.mensajes) + 1, "de": de, "para": para, "tipo": tipo}
        if aviso:
            m["aviso"] = aviso
        m["contenido"] = contenido
        m.update(extra)
        self.mensajes.append(m)

    def contar(self, clave: str, n: int = 1) -> None:
        self.acciones[clave] = self.acciones.get(clave, 0) + n

    def jsonl(self) -> str:
        return "\n".join(json.dumps(m, ensure_ascii=False) for m in self.mensajes) + "\n"


LLM = Callable[..., Tuple[Dict, Dict]]


class Sistema:
    def __init__(self, cfg: Config = Config(), llm_call: LLM = llm.call):
        self.cfg = cfg
        self.call = llm_call
        self.p = {a: llm.load_prompt(a, getattr(cfg, a)) for a in ("lector", "verificador", "decisor")}

    # ------------------------------------------------------------- llamadas ----
    def _llm(self, tr: Traza, agente: str, system: str, user: str, schema: Dict, **kw) -> Dict:
        obj, meta = self.call(self.cfg.model, system, user, schema, esquema=self.cfg.esquema, **kw)
        tr.llamadas += 1
        tr.prompt_tokens += meta["prompt_tokens"]
        tr.output_tokens += meta["output_tokens"]
        tr.wall_s += meta["wall_s"]
        if meta.get("error"):
            tr.errores.append(f"{agente}: {meta['error']}")
        tr.contar(f"llamadas_{agente.lower()}")
        return obj

    # --------------------------------------------------------------- Lector ----
    def lector(self, tr: Traza, prop: Property, pedidos: Optional[Dict[str, str]] = None) -> Dict:
        p = self.p["lector"]
        if pedidos is None:
            user = llm.render(p["inicial"], id=prop.id, texto=prop.text)
            schema = SPANS_SCHEMA_V5
        else:
            spans = sorted({k for c in pedidos for k in SPAN_DE[c]})
            if "pets_text" in spans:
                spans += ["acepta_mascotas", "acepta_perros", "acepta_gatos"]
            schema = {"type": "object", "required": spans,
                      "properties": {k: SPANS_SCHEMA_V5["properties"][k] for k in spans}}
            lista = "\n".join(f"- {' y '.join(SPAN_DE[c])}: {m}" for c, m in pedidos.items())
            user = llm.render(p["relectura"], id=prop.id, texto=prop.text, pedidos=lista)
        obj = self._llm(tr, "Lector", p["system"], user, schema)
        spans_out = {k: obj.get(k) for k in schema["properties"]}
        if self.cfg.esquema is False:   # sin esquema las respuestas cerradas pueden faltar
            for k, v in spans_out.items():   # y un "fragmento" puede llegar como número o lista
                if v is not None and not isinstance(v, str):
                    spans_out[k] = str(v) if isinstance(v, (int, float)) else None
            for k in ("acepta_mascotas", "acepta_perros", "acepta_gatos"):
                if k in spans_out and spans_out[k] not in grounding.ANSWERS:
                    spans_out[k] = "no_dice"
        tr.msg("Lector", "herramienta:anclar", "spans" if pedidos is None else "relectura",
               spans_out, aviso=prop.id)
        return spans_out

    # ---------------------------------------------------------- Verificador ----
    def tabla(self, spans: Dict, h: Dict, marcar: Dict[str, str]) -> str:
        filas = []
        for c in CAMPOS:
            frags = [f'"{spans[k]}"' for k in SPAN_DE[c] if spans.get(k)]
            frag = " / ".join(frags) if frags else "(el Lector no copió nada)"
            marca = f"   ⚠ REVISAR: {marcar[c]}" if c in marcar else "   ✔"
            filas.append(f"- {c}: {frag} -> {tools.lectura(c, h)}{marca}")
        return "\n".join(filas)

    def verificador(self, tr: Traza, prop: Property, spans: Dict, h: Dict, marcar: Dict[str, str],
                    modo: str = "revisar", **extra) -> List[Dict]:
        p = self.p["verificador"]
        user = llm.render(p[modo], id=prop.id, texto=prop.text, tabla=self.tabla(spans, h, marcar), **extra)
        acciones = ACCIONES[modo]
        if modo == "consulta" and all(h.get(c) is None for c in marcar):
            acciones = [a for a in acciones if a != "confirmar"]   # no hay nada que confirmar
        obj = self._llm(tr, "Verificador", p["system"], user, rev_schema(list(marcar), acciones),
                        num_predict=600)
        revs, vistos = [], set()
        for r in obj.get("revisiones") or []:      # una revisión por campo: vale la primera
            if isinstance(r, dict) and r.get("campo") in marcar and r["campo"] not in vistos:
                vistos.add(r["campo"])
                revs.append(r)
        destino = ("Lector" if any(r.get("accion") == "releer" for r in revs)
                   else "herramienta:comprobar" if any(r.get("accion") == "corregir" for r in revs)
                   else "Decisor")
        tr.msg("Verificador", destino, modo, revs, aviso=prop.id)
        for r in revs:
            tr.contar(f"verificador_{r.get('accion')}")
        if not revs:
            tr.contar("verificador_sin_objeciones")
        return revs

    def aplicar(self, tr: Traza, prop: Property, case: Case, revs: List[Dict], h: Dict
                ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Ejecuta las acciones del Verificador. Devuelve (rechazos de comprobar, pedidos al Lector)."""
        rechazos, pedidos = {}, {}
        for r in revs:
            campo, accion = r["campo"], r.get("accion")
            if accion in ("confirmar", "mantener"):
                self._resueltos.add((prop.id, campo))
                continue
            if accion == "releer":
                pedidos[campo] = "el fragmento copiado no corresponde al tema"
            elif accion == "no_verificable":
                self._vaciar(h, campo)
                self._resueltos.add((prop.id, campo))
                tr.msg("Verificador", "hechos", "no_verificable", {"campo": campo}, aviso=prop.id)
            elif accion == "corregir":
                if self.cfg.literal:
                    ok, valor, motivo = tools.comprobar(campo, r.get("valor"), r.get("evidencia"),
                                                        prop.text, case.uf_value)
                else:
                    ok, valor, motivo = self._sin_comprobar(campo, r, case.uf_value)
                tr.msg("herramienta:comprobar", "Verificador", "resultado",
                       {"campo": campo, "valor": r.get("valor"), "evidencia": r.get("evidencia"),
                        "ok": ok, "motivo": motivo}, aviso=prop.id)
                tr.contar("comprobar_ok" if ok else "comprobar_rechaza")
                if ok:
                    self._fijar(h, campo, valor, r.get("evidencia") or "")
                    self._resueltos.add((prop.id, campo))
                else:
                    rechazos[campo] = f"valor {r.get('valor')!r}, evidencia {r.get('evidencia')!r} -> {motivo}"
        return rechazos, pedidos

    def _vaciar(self, h: Dict, campo: str) -> None:
        if campo in ("mascotas", "mascotas_kg"):
            h["mascotas"], h["especies"], h["mascotas_kg"] = "no_explicita", [], None
        elif campo == "estacionamiento":
            h["estacionamiento"] = "no_mencionado"
        elif campo == "distancia":
            h["distancia_metro"] = h["distancia_bus"] = None
        else:
            h[campo] = None

    def _fijar(self, h: Dict, campo: str, valor, evidencia: str) -> None:
        if campo == "distancia":            # la corrección es la distancia que cuenta
            h["distancia_metro"], h["distancia_bus"] = valor, None
            return
        h[campo] = valor
        if campo in ("mascotas", "mascotas_kg"):
            h.pop("_mascotas_duda", None)
        if campo == "mascotas":
            h["especies"] = (tools.especies_de(evidencia) or []) if valor == "permitidas" else []
            if valor != "permitidas":
                h["mascotas_kg"] = None

    @staticmethod
    def _sin_comprobar(campo: str, r: Dict, uf: float):
        """Ablación −literal: se acepta lo que propone el Verificador sin mirar la evidencia."""
        v = r.get("valor")
        if campo in ("comuna", "estacionamiento", "mascotas"):
            ok = bool(v) and (campo == "comuna" or v in (tools.PARKING if campo == "estacionamiento" else tools.MASCOTAS))
            return ok, (v if ok else None), "aceptado sin comprobar" if ok else "valor inválido"
        num = tools.valor_numerico(v)
        if num is None:
            return False, None, "valor no numérico"
        if campo in ("precio", "arriendo") and tools._unidad(f"{v} {r.get('evidencia') or ''}") == "UF":
            return True, int(round(num * uf)) if num < 100_000 else int(round(num)), "aceptado sin comprobar"
        return True, (int(round(num)) if campo != "mascotas_kg" else num), "aceptado sin comprobar"

    def revisar_aviso(self, tr: Traza, prop: Property, case: Case, spans: Dict, h: Dict,
                      marcar: Dict[str, str], modo: str = "revisar", **extra) -> None:
        """Bucle Verificador <-> comprobar <-> Lector para un aviso, dentro del presupuesto.
        `marcar`: campos dudosos (y por qué) que el Verificador debe revisar."""
        if not marcar:
            tr.msg("herramienta:anclar", "Decisor", "sin_dudas",
                   {"motivo": "ningún campo con señales de duda: el aviso pasa al Decisor"}, aviso=prop.id)
            tr.contar("avisos_sin_dudas")
            return
        revs = self.verificador(tr, prop, spans, h, marcar, modo, **extra)
        try:
            self._bucle(tr, prop, case, spans, h, marcar, revs)
        finally:
            self._seguridad(tr, prop, h, marcar)

    def _seguridad(self, tr: Traza, prop: Property, h: Dict, marcar: Dict[str, str]) -> None:
        """Una duda sobre el permiso de mascotas que nadie resolvió no puede aprobar: la
        restricción queda no_verificable (misma regla que un dato faltante). Es distinto de un
        aviso que no declara política, que la convención E3 no descarta."""
        pend = [c for c in ("mascotas", "mascotas_kg") if c in marcar and (prop.id, c) not in self._resueltos]
        if pend and h.get("mascotas") == "permitidas":
            self._vaciar(h, "mascotas")
            h["_mascotas_duda"] = True
            tr.msg("orquestador", "hechos", "duda_sin_resolver",
                   {"campos": pend, "efecto": "mascotas queda no verificable"}, aviso=prop.id)
            tr.contar("dudas_sin_resolver")

    def _bucle(self, tr: Traza, prop: Property, case: Case, spans: Dict, h: Dict,
               marcar: Dict[str, str], revs: List[Dict]) -> None:
        relecturas = retros = 0
        while True:
            rechazos, pedidos = self.aplicar(tr, prop, case, revs, h)
            if rechazos and self.cfg.retro and retros < self.cfg.max_retro:
                retros += 1
                lista = "\n".join(f"- {c}: {m}" for c, m in rechazos.items())
                revs2 = self.verificador(tr, prop, spans, h, {c: marcar.get(c, "") for c in rechazos},
                                         "retro", rechazos=lista)
                _, pedidos2 = self.aplicar(tr, prop, case, revs2, h)
                pedidos.update(pedidos2)
            elif rechazos:
                tr.msg("orquestador", "Verificador", "sin_reintento",
                       {"motivo": "retro desactivada" if not self.cfg.retro else "presupuesto agotado",
                        "rechazos": rechazos}, aviso=prop.id)
            if not pedidos:
                return
            if not (self.cfg.refinar and self.cfg.releer) or relecturas >= self.cfg.max_relecturas:
                tr.msg("orquestador", "Verificador", "sin_relectura",
                       {"motivo": "refinamiento desactivado" if not (self.cfg.refinar and self.cfg.releer)
                        else "presupuesto agotado",
                        "campos": list(pedidos)}, aviso=prop.id)
                return
            relecturas += 1
            tr.contar("relecturas")
            nuevos = self.lector(tr, prop, pedidos)
            spans.update(nuevos)
            h2, _ = tools.anclar(spans, prop.text, case.uf_value, self.cfg.grounding)
            for c in pedidos:
                for k in tools.CLAVES.get(c, (c,)):
                    h[k] = h2[k]
            tr.msg("herramienta:anclar", "Verificador", "hechos",
                   {c: tools.lectura(c, h) for c in pedidos}, aviso=prop.id)
            # tras releer, el Verificador vuelve a mirar los campos devueltos
            marcar = {c: tools.dudas(h, prop.text).get(c, "el Lector volvió a copiar este campo")
                      for c in pedidos}
            revs = self.verificador(tr, prop, spans, h, marcar)

    # -------------------------------------------------------------- Decisor ----
    def perfil(self, case: Case) -> str:
        return base_prompt.render_profile(case)

    def decisor(self, tr: Traza, case: Case, evals: Dict[str, Dict]) -> Dict:
        p = self.p["decisor"]
        bloques = []
        for prop in case.properties:
            e = evals[prop.id]
            lineas = "\n".join(f"   {c}: {e['estado'][c]} ({e['motivo'][c]})" for c in e["estado"])
            bloques.append(f'{prop.id}: "{prop.text}"\n{lineas}')
        user = llm.render(p["decidir"], perfil=self.perfil(case), avisos="\n\n".join(bloques))
        obj = self._llm(tr, "Decisor", p["system"], user, decisor_schema([q.id for q in case.properties]),
                        num_ctx=4096, num_predict=300)
        accion = obj.get("accion") if obj.get("accion") in ("cerrar", "consultar") else "cerrar"
        consultas, descartadas = [], []
        for c in obj.get("consultas") or []:
            if not (isinstance(c, dict) and c.get("id") in evals and c.get("campo") in CAMPOS):
                continue
            # solo se consulta un dato que dejó una restricción sin verificar (o mascotas sin
            # confirmar), y una sola vez
            ok = any(evals[c["id"]]["estado"][r] in ("no_verificable", "sin_confirmar")
                     for r in CAMPO2C.get(c["campo"], ()))
            (consultas if ok and (c["id"], c["campo"]) not in self._consultados else descartadas).append(c)
        if descartadas:
            tr.msg("orquestador", "Decisor", "consultas_descartadas",
                   {"motivo": "la restricción no está no_verificable ni sin_confirmar, o ya se consultó",
                    "consultas": descartadas})
        if accion == "consultar" and not consultas:
            accion = "cerrar"
        tr.msg("Decisor", "herramienta:ordenar" if accion == "cerrar" else "Verificador", accion,
               {"accion": accion, "consultas": consultas, "propuesta": obj})
        tr.contar(f"decisor_{accion}")
        return {"accion": accion, "consultas": consultas}

    def decisor_sin_herramientas(self, tr: Traza, case: Case, hechos: Dict[str, Dict]) -> Dict:
        p = self.p["decisor"]
        limpio = {pid: {k: v for k, v in h.items() if not k.startswith("_")} for pid, h in hechos.items()}
        for pid, h in hechos.items():      # una duda sin resolver se muestra como dato no leído
            if h.get("_mascotas_duda"):
                limpio[pid]["mascotas"] = None
        user = llm.render(p["sin_herramientas"], perfil=self.perfil(case),
                          preferencias=base_prompt.render_soft(case),
                          uf="$" + f"{int(case.uf_value):,}".replace(",", "."),
                          hechos=json.dumps(limpio, ensure_ascii=False, indent=1))
        obj = self._llm(tr, "Decisor", base_prompt.SYSTEM, user, OUTPUT_SCHEMA, num_ctx=4096, num_predict=1024)
        tr.msg("Decisor", "salida", "json_final_sin_herramientas", obj)
        return obj

    # ---------------------------------------------------------------- caso ----
    def run_case(self, case: Case) -> Tuple[Dict, Traza]:
        tr = Traza(case.id)
        self._resueltos = set()
        tr.msg("orquestador", "Lector", "inicio",
               {"config": asdict(self.cfg), "avisos": [p.id for p in case.properties]})
        spans_de: Dict[str, Dict] = {}
        hechos: Dict[str, Dict] = {}
        for prop in case.properties:
            spans = self.lector(tr, prop)
            h, warns = tools.anclar(spans, prop.text, case.uf_value, self.cfg.grounding)
            tr.msg("herramienta:anclar", "Verificador", "hechos",
                   {"hechos": {c: tools.lectura(c, h) for c in CAMPOS}, "avisos_anclaje": warns}, aviso=prop.id)
            self.revisar_aviso(tr, prop, case, spans, h, tools.dudas(h, prop.text))
            spans_de[prop.id], hechos[prop.id] = spans, h

        if not self.cfg.herramientas_decisor:
            out = self.decisor_sin_herramientas(tr, case, hechos)
            return out, tr

        props = {p.id: p for p in case.properties}
        evals = {pid: tools.evaluar(pid, h, case) for pid, h in hechos.items()}
        tr.msg("herramienta:evaluar", "Decisor", "evaluacion",
               {pid: e["estado"] for pid, e in evals.items()})
        ronda = 0
        self._consultados = set()
        while True:
            d = self.decisor(tr, case, evals)
            if d["accion"] == "cerrar" or not d["consultas"]:
                break
            if not (self.cfg.refinar and self.cfg.consultar) or ronda >= self.cfg.max_consultas:
                tr.msg("orquestador", "herramienta:ordenar", "cierre_por_presupuesto",
                       {"motivo": "refinamiento desactivado" if not (self.cfg.refinar and self.cfg.consultar)
                        else "presupuesto agotado",
                        "consultas_ignoradas": d["consultas"]})
                tr.contar("cierre_por_presupuesto")
                break
            ronda += 1
            vistos = set()
            for c in d["consultas"][: self.cfg.max_consultas_por_ronda]:
                if (c["id"], c["campo"]) in vistos:
                    continue
                vistos.add((c["id"], c["campo"]))
                self._consultados.add((c["id"], c["campo"]))
                prop, h = props[c["id"]], hechos[c["id"]]
                motivo = c.get("motivo") or "pregunta del Decisor"
                self.revisar_aviso(tr, prop, case, spans_de[c["id"]], h, {c["campo"]: motivo}, "consulta",
                                   campo=c["campo"], motivo=motivo)
                evals[c["id"]] = tools.evaluar(c["id"], h, case)
            tr.msg("herramienta:evaluar", "Decisor", "evaluacion",
                   {pid: e["estado"] for pid, e in evals.items()})
        out = tools.ordenar([evals[p.id] for p in case.properties])
        tr.msg("herramienta:ordenar", "salida", "json_final", out)
        return out, tr
