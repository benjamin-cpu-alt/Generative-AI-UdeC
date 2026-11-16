"""Entrena el adaptador LoRA del Lector con mlx-lm y deja el registro del entrenamiento.

  .venv-ft/bin/python scripts/ft/train_lector.py                 # entrena con scripts/ft/lector_lora.yaml
  .venv-ft/bin/python scripts/ft/train_lector.py --solo-curvas   # solo regenera loss.csv desde train.log

Escribe en ft/lector/:
  adapters.safetensors, NNNNNNN_adapters.safetensors   pesos (final y checkpoints; no se versionan)
  adapter_config.json     configuración efectiva que guarda mlx-lm
  train.log               salida completa del entrenamiento
  loss.csv                iter, train_loss, val_loss, lr, tokens_por_s, mem_gb  (las curvas del informe)
  entrenamiento.json      hardware, versiones, duración, hash de los datos

Requiere Apple Silicon (MLX). Instalar: python3 -m venv .venv-ft && .venv-ft/bin/pip install -r scripts/ft/requirements.txt
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "scripts" / "ft" / "lector_lora.yaml"

_TRAIN = re.compile(r"Iter (\d+): Train loss ([\d.]+), Learning Rate ([\d.e+-]+), It/sec ([\d.]+), "
                    r"Tokens/sec ([\d.]+), Trained Tokens (\d+), Peak mem ([\d.]+) GB")
_VAL = re.compile(r"Iter (\d+): Val loss ([\d.]+)")


def curvas(log: Path, salida: Path) -> dict:
    filas = {}
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _TRAIN.search(line)
        if m:
            it = int(m.group(1))
            filas.setdefault(it, {"iter": it}).update(train_loss=float(m.group(2)), lr=float(m.group(3)),
                                                      tokens_por_s=float(m.group(5)), tokens=int(m.group(6)),
                                                      mem_gb=float(m.group(7)))
        m = _VAL.search(line)
        if m:
            it = int(m.group(1))
            filas.setdefault(it, {"iter": it})["val_loss"] = float(m.group(2))
    cols = ["iter", "train_loss", "val_loss", "lr", "tokens_por_s", "tokens", "mem_gb"]
    with open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for it in sorted(filas):
            w.writerow({c: filas[it].get(c, "") for c in cols})
    vals = {it: f["val_loss"] for it, f in filas.items() if "val_loss" in f}
    return {"val_loss": vals, "pico_mem_gb": max((f.get("mem_gb", 0) for f in filas.values()), default=0),
            "tokens_entrenados": max((f.get("tokens", 0) for f in filas.values()), default=0)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=CFG)
    ap.add_argument("--solo-curvas", action="store_true")
    a = ap.parse_args(argv)

    import yaml
    cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    out = ROOT / cfg["adapter_path"]
    out.mkdir(parents=True, exist_ok=True)
    log = out / "train.log"

    if not a.solo_curvas:
        from huggingface_hub import snapshot_download
        import mlx.core as mx
        import mlx_lm
        modelo = snapshot_download(cfg["model"], revision=cfg["revision"])
        efectiva = {k: v for k, v in cfg.items() if k != "revision"}
        efectiva["model"] = modelo
        tmp = out / "config_efectiva.yaml"
        tmp.write_text(yaml.safe_dump(efectiva, allow_unicode=True, sort_keys=False), encoding="utf-8")
        t0 = time.time()
        with open(log, "w", encoding="utf-8") as fh:
            # mlx_lm.lora tal cual, con la caché de buffers de MLX limitada: sin el límite el
            # proceso llega a 11 GB en un equipo de 16 GB y el sistema empieza a paginar.
            hijo = ("import sys, mlx.core as mx; mx.set_cache_limit(256 * 2**20); "
                    f"sys.argv = ['mlx_lm.lora', '-c', {str(tmp)!r}]; "
                    "from mlx_lm.lora import main; main()")
            p = subprocess.Popen([sys.executable, "-u", "-c", hijo], cwd=ROOT,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in p.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                fh.write(line)
                fh.flush()
            rc = p.wait()
        dur = time.time() - t0
        tmp.unlink()
        if rc != 0:
            print(f"mlx_lm lora terminó con código {rc}")
            return rc
        datos = ROOT / cfg["data"]
        info = {
            "fecha": time.strftime("%Y-%m-%d %H:%M"),
            "duracion_min": round(dur / 60, 1),
            "hardware": {"equipo": platform.machine(), "chip": _sysctl("machdep.cpu.brand_string"),
                         "memoria_gb": round(int(_sysctl("hw.memsize") or 0) / 2 ** 30),
                         "sistema": f"macOS {platform.mac_ver()[0]}"},
            "software": {"python": platform.python_version(), "mlx": mx.__version__, "mlx_lm": mlx_lm.__version__},
            "modelo_base": {"repo": cfg["model"], "revision": cfg["revision"]},
            "datos": {f: hashlib.sha256((datos / f).read_bytes()).hexdigest() for f in ("train.jsonl", "valid.jsonl")},
            "config": {k: cfg[k] for k in ("num_layers", "lora_parameters", "batch_size", "grad_accumulation_steps",
                                           "iters", "optimizer",
                                           "optimizer_config", "learning_rate", "lr_schedule", "mask_prompt",
                                           "max_seq_length", "seed")},
        }
        (out / "entrenamiento.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    res = curvas(log, out / "loss.csv")
    info_p = out / "entrenamiento.json"
    if info_p.exists():
        info = json.loads(info_p.read_text(encoding="utf-8"))
        info.update(pico_mem_gb=res["pico_mem_gb"], tokens_entrenados=res["tokens_entrenados"],
                    val_loss_por_checkpoint={str(k): v for k, v in sorted(res["val_loss"].items())})
        info_p.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("val_loss por checkpoint:", {k: v for k, v in sorted(res["val_loss"].items())})
    return 0


def _sysctl(k: str) -> str:
    try:
        return subprocess.run(["sysctl", "-n", k], capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


if __name__ == "__main__":
    sys.exit(main())
