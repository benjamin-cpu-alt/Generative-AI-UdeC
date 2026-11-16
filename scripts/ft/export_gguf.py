"""Adaptador LoRA de MLX (adapters.safetensors) -> adaptador GGUF que Ollama aplica sobre
`phi4-mini:latest` con la instrucción ADAPTER de un Modelfile.

No se fusiona nada: los pesos base siguen siendo los del phi4-mini de Ollama (Q4_K_M, digest
78fad5d182a7), el mismo modelo que usan los otros dos agentes. El adaptador solo suma, en cada
capa ajustada, la corrección de bajo rango  ΔW = (alpha / r) · B · A.

Equivalencia con MLX (mlx_lm/tuner/lora.py):  y = W x + scale · (x · lora_a) · lora_b
  A = lora_a.T  (r × entrada)     B = lora_b.T  (salida × r)     alpha = scale · r
Los nombres de los tensores se traducen con el mapa oficial de gguf-py para la arquitectura
phi3 («model.layers.N.self_attn.qkv_proj» -> «blk.N.attn_qkv.weight»).

Uso:
  .venv-ft/bin/python scripts/ft/export_gguf.py ft/lector            # escribe ft/lector/lector-lora-f16.gguf
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import gguf
import numpy as np
from safetensors.numpy import load_file

N_BLOQUES = 32          # Phi-4-mini: 32 capas


def exportar(adapter_dir: Path, salida: Path, pesos: str = "adapters.safetensors") -> dict:
    cfg = json.loads((adapter_dir / "adapter_config.json").read_text())
    lp = cfg["lora_parameters"]
    r, alpha = int(lp["rank"]), float(lp["scale"]) * int(lp["rank"])
    w = load_file(str(adapter_dir / pesos))
    nombres = gguf.get_tensor_name_map(gguf.MODEL_ARCH.PHI3, N_BLOQUES)

    writer = gguf.GGUFWriter(str(salida), arch="phi3")
    writer.add_string(gguf.Keys.General.TYPE, gguf.GGUFType.ADAPTER)
    writer.add_string(gguf.Keys.Adapter.TYPE, "lora")
    writer.add_float32(gguf.Keys.Adapter.LORA_ALPHA, alpha)
    writer.add_string(gguf.Keys.General.NAME, "phi4-mini-lector-lora")
    writer.add_string("general.base_model.0.name", "Phi-4-mini-instruct")
    writer.add_string("general.base_model.0.repo_url", "https://huggingface.co/microsoft/Phi-4-mini-instruct")

    modulos = sorted({k.rsplit(".", 1)[0] for k in w})
    for mod in modulos:
        a, b = w[f"{mod}.lora_a"], w[f"{mod}.lora_b"]            # (entrada, r), (r, salida)
        assert a.shape[1] == r and b.shape[0] == r, (mod, a.shape, b.shape)
        base = nombres.get_name(f"{mod}.weight", try_suffixes=(".weight",))
        if base is None:
            raise SystemExit(f"sin nombre GGUF para {mod}")
        writer.add_tensor(f"{base}.lora_a", np.ascontiguousarray(a.T.astype(np.float16)))   # (r, entrada)
        writer.add_tensor(f"{base}.lora_b", np.ascontiguousarray(b.T.astype(np.float16)))   # (salida, r)
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()
    info = {"archivo": salida.name, "modulos": len(modulos), "rank": r, "alpha": alpha,
            "parametros": int(sum(v.size for v in w.values())),
            "sha256": hashlib.sha256(salida.read_bytes()).hexdigest(),
            "bytes": salida.stat().st_size}
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("adapter_dir", type=Path)
    ap.add_argument("--pesos", default="adapters.safetensors", help="p.ej. 0000300_adapters.safetensors")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args(argv)
    salida = a.salida or a.adapter_dir / "lector-lora-f16.gguf"
    info = exportar(a.adapter_dir, salida, a.pesos)
    if a.pesos != "adapters.safetensors":      # el checkpoint elegido pasa a ser EL adaptador
        (a.adapter_dir / "adapters.safetensors").write_bytes((a.adapter_dir / a.pesos).read_bytes())
    info["checkpoint"] = a.pesos
    sumas = {f: hashlib.sha256((a.adapter_dir / f).read_bytes()).hexdigest()
             for f in (salida.name, "adapters.safetensors", "adapter_config.json")}
    (a.adapter_dir / "SHA256SUMS").write_text("".join(f"{h}  {f}\n" for f, h in sumas.items()))
    (a.adapter_dir / "adaptador.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
