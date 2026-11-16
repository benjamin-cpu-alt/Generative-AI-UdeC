"""E4 (fine-tuning del Lector), sin Ollama ni MLX.

Lo que se protege:
- Los datos de entrenamiento se regeneran idénticos desde el script (semilla fija).
- Cada etiqueta es una subcadena literal del aviso y el mensaje tiene el formato exacto que el
  Lector ve en el sistema (mismo `system`, mismo esquema).
- Separación de la evaluación: ningún aviso de entrenamiento comparte 8 palabras seguidas con
  un aviso de hard_test, real_e3, test, ood ni hard_dev.
- El modelo por agente: solo el Lector cambia de modelo; Verificador y Decisor siguen con el base.
- La vista con roles distingue agentes de herramientas y numera cada vuelta de bucle.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from agents import llm, show
from agents.orchestrator import Config, Sistema, mensaje_lector
from matcher.extract import SPANS_SCHEMA_V5, SYSTEM_V5
from matcher.grounding import ANSWER_FIELDS, SPAN_FIELDS
from matcher.schema import Case

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "ft_lector"


def _script(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, ROOT / "scripts" / "ft" / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def build():
    return _script("build_lector_data")


@pytest.fixture(scope="module")
def ejemplos():
    return [json.loads(l) for l in (DATA / "ejemplos.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def mensajes():
    return {s: [json.loads(l) for l in (DATA / f"{s}.jsonl").read_text(encoding="utf-8").splitlines()]
            for s in ("train", "valid")}


# ------------------------------------------------------------------- datos ----

def test_numeros_en_palabras_los_entiende_la_herramienta(build):
    from agents import tools
    for n in (5, 21, 100, 116, 600, 1000, 1500, 5400, 130_000_000, 205_000_000, 221_000_000):
        assert tools.numeros_en_palabras(build.palabras(n)) == [n], build.palabras(n)
    assert build.palabras(5400, fem=True) == "cinco mil cuatrocientas"


def test_los_datos_se_regeneran_identicos(build):
    rep = json.loads((DATA / "reporte.json").read_text(encoding="utf-8"))
    assert build.main(["--check"]) == 0
    assert rep["train"] + rep["valid"] == rep["sinteticos"] + rep["autoetiquetados"]


def test_cada_fragmento_es_literal_y_el_formato_es_el_del_sistema(ejemplos, mensajes):
    textos = {e["texto"]: e for e in ejemplos}
    prompt = llm.load_prompt("lector", "v1")
    n = 0
    for m in mensajes["train"] + mensajes["valid"]:
        sistema, usuario, salida = (x["content"] for x in m["messages"])
        assert sistema == prompt["system"] == SYSTEM_V5
        aviso = usuario.split('"', 1)[1].rsplit('"\n\n', 1)[0]
        assert aviso in textos
        obj = json.loads(salida)
        assert salida == json.dumps(obj, ensure_ascii=False, indent=2)      # el formato que emite Ollama
        for k, v in obj.items():
            if k in SPAN_FIELDS:
                assert v is None or v in aviso, (k, v)
            else:
                assert k in ANSWER_FIELDS and v in ("si", "no", "no_dice")
        if "El Verificador revisó" in usuario:
            assert set(obj) < set(SPANS_SCHEMA_V5["properties"])
        else:
            assert list(obj) == list(SPANS_SCHEMA_V5["properties"])
        n += 1
    assert n == len(ejemplos)


def test_etiquetas_comprobadas_con_las_herramientas(build, ejemplos):
    """Cada fragmento correcto lleva al truth con `anclar`, o `dudas` lo manda al Verificador."""
    for e in ejemplos:
        if e["fuente"] != "sintetico":
            continue
        ok, estado = build.comprobar_ejemplo(e)
        assert ok, (e["id"], estado)


def test_separacion_de_los_sets_de_evaluacion(build, ejemplos):
    evals = build.avisos_de_evaluacion()
    assert {"hard_test", "real_e3", "test", "ood", "hard_dev"} <= set(evals)
    prohibidos = set().union(*(build.ngramas(t) for ts in evals.values() for t in ts))
    textos_eval = {t.strip().casefold() for ts in evals.values() for t in ts}
    for e in ejemplos:
        if e["fuente"] == "sintetico":
            assert e["texto"].strip().casefold() not in textos_eval
            assert not (build.ngramas(e["texto"]) & prohibidos), e["id"]
    # los autoetiquetados son avisos del split train del generador, nunca de un set de evaluación
    train_txt = {p["text"] for f in (ROOT / "data" / "cases" / "train").glob("*.json")
                 for p in json.loads(f.read_text(encoding="utf-8"))["properties"]}
    assert all(e["texto"] in train_txt for e in ejemplos if e["fuente"] != "sintetico")
    assert not any(e["texto"].strip().casefold() in textos_eval for e in ejemplos)


def test_validacion_disjunta_del_entrenamiento(mensajes):
    aviso = lambda m: m["messages"][1]["content"].split('"', 1)[1].rsplit('"\n\n', 1)[0]   # noqa: E731
    assert not ({aviso(m) for m in mensajes["train"]} & {aviso(m) for m in mensajes["valid"]})


def test_prompt_few_shot_del_control_sale_de_los_datos():
    fs = _script("build_fewshot_prompt")
    assert fs.main(["--check"]) == 0
    p = llm.load_prompt("lector", "v2_fewshot")
    v1 = llm.load_prompt("lector", "v1")
    assert p["system"].startswith(v1["system"]) and p["inicial"] == v1["inicial"] and p["relectura"] == v1["relectura"]
    assert p["system"].count("\nAviso: ") == fs.K


# ------------------------------------------------------------ modelo por agente --

def _caso():
    return Case.load(ROOT / "data" / "cases" / "hard_dev" / "hd_01.json")


def test_solo_el_lector_cambia_de_modelo():
    llamadas = []

    def fake(model, system, user, schema, esquema=True, **kw):
        llamadas.append((model, kw.get("num_ctx")))
        props = schema["properties"]
        if "revisiones" in props:
            return {"revisiones": []}, {"prompt_tokens": 1, "output_tokens": 1, "wall_s": 0.0}
        if "accion" in props:
            return {"accion": "cerrar", "consultas": []}, {"prompt_tokens": 1, "output_tokens": 1, "wall_s": 0.0}
        return ({k: None if k.endswith("_text") else "no_dice" for k in props},
                {"prompt_tokens": 1, "output_tokens": 1, "wall_s": 0.0})

    cfg = Config(model_lector="phi4-mini-lector-ft")
    out, tr = Sistema(cfg, llm_call=fake).run_case(_caso())
    por_agente = {}
    for m in tr.mensajes:
        if m["de"] in ("Lector", "Verificador", "Decisor") and m["tipo"] in ("spans", "revisar", "cerrar"):
            por_agente.setdefault(m["de"], set()).add(m.get("modelo"))
    assert por_agente["Lector"] == {"phi4-mini-lector-ft"}            # la traza dice qué modelo leyó
    assert por_agente.get("Verificador", {None}) == {None} and por_agente["Decisor"] == {None}
    modelos = {m for m, _ in llamadas}
    assert modelos == {"phi4-mini-lector-ft", "phi4-mini:latest"}
    assert sum(m == "phi4-mini-lector-ft" for m, _ in llamadas) == tr.acciones["llamadas_lector"]
    assert cfg.modelo_de("Verificador") == cfg.modelo_de("Decisor") == "phi4-mini:latest"


def test_config_de_la_e3_no_cambia():
    cfg = Config()
    assert cfg.model_lector is None and cfg.modelo_de("Lector") == "phi4-mini:latest"
    assert cfg.lector == "v1" and cfg.num_ctx_lector == 2048 and cfg.nombre == "full"
    # una traza de la E3 se sigue pudiendo cargar como Config
    primera = json.loads((ROOT / "results" / "agents_v2_hard_dev" / "hd_01.trace.jsonl")
                         .read_text(encoding="utf-8").splitlines()[0])
    assert Config(**primera["contenido"]["config"]) == cfg


def test_mensaje_lector_relectura_pide_solo_los_campos_devueltos():
    p = llm.load_prompt("lector", "v1")
    user, schema = mensaje_lector(p, "X-1", "Depto 2D. UF 3.000.", {"mascotas": "motivo", "precio": "motivo"})
    assert list(schema["properties"]) == ["pets_text", "price_text", "acepta_mascotas", "acepta_perros", "acepta_gatos"]
    assert "- price_text: motivo" in user and "- pets_text: motivo" in user
    user0, schema0 = mensaje_lector(p, "X-1", "Depto 2D. UF 3.000.")
    assert schema0 is SPANS_SCHEMA_V5 and user0.endswith("Devuelve el JSON de hechos.")


# ----------------------------------------------- vista: agentes, herramientas, bucles --

def test_roles_distinguen_agente_de_herramienta():
    assert show.rol("Lector").strip() == show.rol("Verificador").strip() == show.rol("Decisor").strip() == "AGENTE"
    assert show.rol("herramienta:anclar").strip() == "HERRAMIENTA"
    assert show.rol("orquestador") == "" and show.rol("salida") == ""


def test_bucles_numera_cada_vuelta_y_marca_la_parada():
    b = show.Bucles()
    b.anotar({"de": "orquestador", "para": "Lector", "tipo": "inicio",
              "contenido": {"config": {"max_relecturas": 2, "max_retro": 1, "max_consultas": 1}}})
    releer = {"de": "Verificador", "para": "Lector", "tipo": "revisar", "aviso": "A-1", "contenido": []}
    assert "RELECTURA, vuelta 1 de máx. 2" in b.anotar(releer)
    assert "RELECTURA, vuelta 2 de máx. 2" in b.anotar(releer)
    assert "RELECTURA, vuelta 1 de máx. 2" in b.anotar({**releer, "aviso": "A-2"})      # el presupuesto es por aviso
    assert "REINTENTO, vuelta 1 de máx. 1" in b.anotar(
        {"de": "Verificador", "para": "herramienta:comprobar", "tipo": "retro", "aviso": "A-1", "contenido": []})
    assert "CONSULTA, vuelta 1 de máx. 1" in b.anotar(
        {"de": "Decisor", "para": "Verificador", "tipo": "consultar", "contenido": {"consultas": []}})
    assert "PARADA" in b.anotar({"de": "Decisor", "para": "herramienta:ordenar", "tipo": "cerrar",
                                 "contenido": {"consultas": []}})
    assert "FIN DEL BUCLE" in b.anotar({"de": "orquestador", "para": "Verificador", "tipo": "sin_relectura",
                                        "aviso": "A-1", "contenido": {}})
    # un mensaje de herramienta nunca abre un bucle
    assert b.anotar({"de": "herramienta:anclar", "para": "Verificador", "tipo": "hechos", "aviso": "A-1",
                     "contenido": {}}) is None


def test_show_con_roles_imprime_el_modelo_del_agente(capsys):
    show.imprimir({"paso": 2, "de": "Lector", "para": "herramienta:anclar", "tipo": "spans", "aviso": "A-1",
                   "contenido": {"price_text": "UF 3.000"}, "modelo": "phi4-mini-lector-ft"}, False, show.Bucles())
    out = capsys.readouterr().out
    assert "AGENTE Lector → HERRAMIENTA anclar" in out and "modelo: phi4-mini-lector-ft" in out


# ------------------------------------------------------------ entrenamiento ----

def test_curvas_de_perdida_desde_el_log(tmp_path):
    pytest.importorskip("yaml")
    tl = _script("train_lector")
    log = tmp_path / "train.log"
    log.write_text("Iter 1: Val loss 1.234, Val took 3.2s\n"
                   "Iter 10: Train loss 0.900, Learning Rate 2.500e-05, It/sec 0.4, Tokens/sec 310.0, "
                   "Trained Tokens 3100, Peak mem 7.5 GB\n"
                   "Iter 86: Val loss 0.120, Val took 3.0s\n", encoding="utf-8")
    res = tl.curvas(log, tmp_path / "loss.csv")
    assert res["val_loss"] == {1: 1.234, 86: 0.12} and res["pico_mem_gb"] == 7.5
    filas = (tmp_path / "loss.csv").read_text(encoding="utf-8").splitlines()
    assert filas[0].startswith("iter,train_loss,val_loss") and filas[2].startswith("10,0.9,,")


def test_exportar_gguf_conserva_la_correccion_de_bajo_rango(tmp_path):
    """ΔW = scale · lora_b.T · lora_a.T (MLX) == (alpha / r) · B · A (GGUF), con alpha = scale · r."""
    gguf = pytest.importorskip("gguf")
    np = pytest.importorskip("numpy")
    st = pytest.importorskip("safetensors.numpy")
    ex = _script("export_gguf")
    rng = np.random.default_rng(0)
    r, scale, din, dout = 4, 2.0, 3072, 5120
    a = rng.normal(0, 0.05, (din, r)).astype(np.float32)
    b = rng.normal(0, 0.05, (r, dout)).astype(np.float32)
    st.save_file({"model.layers.31.self_attn.qkv_proj.lora_a": a, "model.layers.31.self_attn.qkv_proj.lora_b": b},
                 str(tmp_path / "adapters.safetensors"))
    (tmp_path / "adapter_config.json").write_text(json.dumps({"lora_parameters": {"rank": r, "scale": scale}}))
    info = ex.exportar(tmp_path, tmp_path / "x.gguf")
    assert info["alpha"] == scale * r and info["modulos"] == 1
    rd = gguf.GGUFReader(str(tmp_path / "x.gguf"))
    t = {x.name: np.array(x.data).reshape(x.shape.tolist()[::-1]) for x in rd.tensors}
    A, B = t["blk.31.attn_qkv.weight.lora_a"], t["blk.31.attn_qkv.weight.lora_b"]
    assert A.shape == (r, din) and B.shape == (dout, r)
    delta_mlx = scale * (b.T @ a.T)
    delta_gguf = (info["alpha"] / r) * (B.astype(np.float32) @ A.astype(np.float32))
    assert np.allclose(delta_mlx, delta_gguf, atol=2e-3)


# ------------------------------------------------------------- corridas E4 ----

def _resumen():
    spec = importlib.util.spec_from_file_location("resumen_e4", ROOT / "scripts" / "resumen_e4.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_resumen_cuenta_los_bucles_de_la_e3_desde_las_trazas():
    """Las cifras de bucles que cita el informe salen de las trazas versionadas."""
    c = _resumen().resumen("agents_v2_hard_test")
    assert (c["casos"], c["avisos"], c["llamadas"]) == (30, 240, 614)
    assert (c["Lector"], c["Verificador"], c["Decisor"]) == (245, 315, 54)
    assert (c["relecturas"], c["reintentos"], c["rondas_consulta"], c["consultas"]) == (7, 93, 24, 41)


@pytest.mark.parametrize("split", ["hard_dev", "hard_test", "real_e3", "test", "ood"])
def test_corridas_e4_solo_cambian_el_lector(split):
    """E4: mismo prompt y mismas opciones que la E3, otro modelo SOLO en el Lector.
    Control: mismo modelo que la E3, otro prompt SOLO en el Lector."""
    ft, ctrl = ROOT / "results" / f"agents_ft_{split}", ROOT / "results" / f"agents_ctrl_{split}"
    if not ft.is_dir() and not ctrl.is_dir():
        pytest.skip("corrida no versionada")
    n = len(list((ROOT / "data" / "cases" / split).glob("*.json")))
    for d, modelo, prompt in ((ft, "phi4-mini-lector-ft", "v1"), (ctrl, "phi4-mini:latest", "v2_fewshot")):
        if not d.is_dir():
            continue
        metas = [json.loads(p.read_text(encoding="utf-8")) for p in d.glob("*.meta.json")]
        assert len(metas) == n, f"{d.name}: {len(metas)} de {n} casos"
        for m in metas:
            assert m["modelos"] == {"lector": modelo, "verificador": "phi4-mini:latest", "decisor": "phi4-mini:latest"}
            assert m["prompts"] == {"lector": prompt, "verificador": "v1", "decisor": "v2"}
            assert m["config"] == "full" and m["grounding_version"] == "g3" and not m["errors"]


def test_los_pesos_publicados_son_los_de_los_resultados():
    """`SHA256SUMS` fija el adaptador con el que se corrió; `adaptador.json` y el entrenamiento lo respaldan."""
    d = ROOT / "ft" / "lector"
    if not (d / "SHA256SUMS").exists():
        pytest.skip("adaptador no exportado")
    sumas = dict(reversed(l.split("  ", 1)) for l in (d / "SHA256SUMS").read_text().splitlines() if l.strip())
    info = json.loads((d / "adaptador.json").read_text(encoding="utf-8"))
    assert sumas["lector-lora-f16.gguf"] == info["sha256"] and info["rank"] == 16 and info["modulos"] == 64
    ent = json.loads((d / "entrenamiento.json").read_text(encoding="utf-8"))
    rep = json.loads((ROOT / "data" / "ft_lector" / "reporte.json").read_text(encoding="utf-8"))
    assert ent["datos"]["train.jsonl"] == rep["sha256"]["train.jsonl"], "se entrenó con otros datos"
    assert ent["datos"]["valid.jsonl"] == rep["sha256"]["valid.jsonl"]
    assert "ADAPTER ./lector-lora-f16.gguf" in (d / "Modelfile").read_text(encoding="utf-8")
