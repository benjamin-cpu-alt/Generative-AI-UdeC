"""Publica el adaptador del Lector en Hugging Face (repositorio público de modelo).

Antes, UNA vez, iniciar sesión con un token de escritura (https://huggingface.co/settings/tokens):
  .venv-ft/bin/huggingface-cli login

Publicar (crea el repositorio si no existe) y comprobar:
  .venv-ft/bin/python scripts/ft/subir_hf.py USUARIO/phi4-mini-lector-lora
  .venv-ft/bin/python scripts/ft/subir_hf.py USUARIO/phi4-mini-lector-lora --verificar

Sube exactamente los archivos con los que se obtuvieron los resultados del informe: el script
compara el sha256 de cada archivo local con `ft/lector/SHA256SUMS` (escrito al exportar el
adaptador) y se niega a subir si alguno cambió. `--verificar` descarga lo publicado y repite la
comparación, para que el enlace del informe apunte a los mismos pesos.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "ft" / "lector"
# archivo local -> nombre en Hugging Face
ARCHIVOS = {
    "lector-lora-f16.gguf": "lector-lora-f16.gguf",          # el adaptador que usa Ollama (el de los resultados)
    "adapters.safetensors": "mlx/adapters.safetensors",      # el mismo adaptador en formato MLX (para seguir entrenando)
    "adapter_config.json": "mlx/adapter_config.json",
    "Modelfile": "Modelfile",
    "MODEL_CARD.md": "README.md",
    "entrenamiento.json": "entrenamiento.json",
    "loss.csv": "loss.csv",
    "SHA256SUMS": "SHA256SUMS",
}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sumas() -> dict:
    return dict(reversed(l.split("  ", 1)) for l in (DIR / "SHA256SUMS").read_text().splitlines() if l.strip())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", help="USUARIO/NOMBRE del repositorio de modelo en Hugging Face")
    ap.add_argument("--verificar", action="store_true", help="no sube: descarga lo publicado y compara sha256")
    a = ap.parse_args(argv)
    from huggingface_hub import HfApi, hf_hub_download

    esperado = sumas()
    if a.verificar:
        mal = 0
        for local, remoto in ARCHIVOS.items():
            if local not in esperado:
                continue
            p = hf_hub_download(a.repo, remoto, force_download=True)
            ok = sha(Path(p)) == esperado[local]
            mal += not ok
            print(f"{'OK ' if ok else 'MAL'} {remoto}")
        print("Los pesos publicados son los del informe." if not mal else "HAY ARCHIVOS DISTINTOS.")
        return 1 if mal else 0

    for local in esperado:
        if sha(DIR / local) != esperado[local]:
            print(f"{local} no coincide con SHA256SUMS: no se sube nada. ¿Se reentrenó después de evaluar?")
            return 1
    api = HfApi()
    api.create_repo(a.repo, repo_type="model", private=False, exist_ok=True)
    for local, remoto in ARCHIVOS.items():
        if not (DIR / local).exists():
            print(f"falta {local}")
            return 1
        api.upload_file(path_or_fileobj=str(DIR / local), path_in_repo=remoto, repo_id=a.repo, repo_type="model")
        print(f"subido {remoto}")
    print(f"\nPublicado: https://huggingface.co/{a.repo}\nAhora: .venv-ft/bin/python scripts/ft/subir_hf.py {a.repo} --verificar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
