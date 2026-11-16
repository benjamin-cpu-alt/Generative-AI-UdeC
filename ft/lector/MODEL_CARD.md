---
license: mit
base_model: microsoft/Phi-4-mini-instruct
library_name: mlx
tags:
  - lora
  - phi3
  - gguf
  - ollama
  - spanish
  - information-extraction
  - multi-agent
language:
  - es
---

# phi4-mini-lector-lora

Adaptador LoRA para **Phi-4-mini-instruct (3.8B)** que ajusta al agente **Lector** de un sistema
de tres agentes para matching comprador–propiedad en avisos inmobiliarios chilenos (Entregable 4,
Generative AI 580694, Universidad de Concepción; Benjamín Grandón V. y Carla Maureira V.).

Código, datos, trazas y evaluación: <https://github.com/benjamin-cpu-alt/Generative-AI-UdeC>
(`docs/e4_finetuning.md`).

## Qué hace el Lector

Recibe un aviso en texto libre y devuelve un JSON con el **fragmento literal** del aviso que habla
de cada tema (comuna, dormitorios, precio, arriendo, metro, paradero, estacionamiento, mascotas)
y tres respuestas cerradas sobre mascotas. No interpreta ni calcula: eso lo hacen herramientas de
Python (`anclar`, `comprobar`, `evaluar`, `ordenar`) y los otros dos agentes (Verificador y
Decisor), que usan el modelo base sin adaptador.

El prompt con el que se entrenó y con el que se usa es `prompts/lector/v1.md` del repositorio, y
la salida se restringe con el JSON Schema que arma `mensaje_lector` en
`src/agents/orchestrator.py`.

## Archivos

| Archivo | Para qué |
|---|---|
| `lector-lora-f16.gguf` | El adaptador en formato GGUF (llama.cpp / Ollama), float16, 23 MB. **Es el que produjo los resultados reportados** |
| `Modelfile` | `FROM phi4-mini:latest` + `ADAPTER ./lector-lora-f16.gguf` |
| `mlx/adapters.safetensors`, `mlx/adapter_config.json` | El mismo adaptador en formato MLX (para seguir entrenando con `mlx-lm`) |
| `entrenamiento.json`, `loss.csv` | Hardware, versiones, configuración, duración, sha256 de los datos y curva de pérdida |
| `SHA256SUMS` | sha256 de los archivos con los que se evaluó |

## Uso con Ollama

```bash
ollama pull phi4-mini:latest            # digest 78fad5d182a7 (Q4_K_M)
huggingface-cli download USUARIO_HF/phi4-mini-lector-lora lector-lora-f16.gguf Modelfile --local-dir ft/lector
cd ft/lector && ollama create phi4-mini-lector-ft -f Modelfile
```

En el repositorio, el sistema completo con el Lector ajustado:

```bash
PYTHONPATH=src python3 -m agents.run --split hard_test --run agents_ft_hard_test --modelo-lector phi4-mini-lector-ft
```

## Entrenamiento

| | |
|---|---|
| Método | LoRA con `mlx-lm` 0.29.1 (MLX 0.29.3) |
| Pesos para entrenar | `mlx-community/Phi-4-mini-instruct-8bit`, revisión `93b273a5497a4fcdcfb7ac00143565506b4f72e4` |
| Módulos | `self_attn.qkv_proj`, `self_attn.o_proj`, `mlp.gate_up_proj`, `mlp.down_proj` de las últimas 16 capas |
| Rango / escala / alpha / dropout | 16 / 2,0 / 32 / 0,05 |
| Parámetros entrenables | 11,53 M (0,30 %) |
| Pérdida | Solo sobre la respuesta (`mask_prompt`) |
| Optimizador | AdamW (weight decay 0,01), 1,5e-4 con warmup de 20 pasos y coseno hasta 1,5e-5 |
| Lote | 1 con acumulación de gradiente 4 |
| Iteraciones | 1.300 ejemplos (325 pasos, 1,25 épocas), semilla 0 |
| Hardware / tiempo | MacBook Air M4 16 GB / 202,5 min, 6,7 GB de memoria pico |
| Pérdida de validación | 0,690 (antes) → 0,006 (checkpoint publicado, iteración 1.300) |

## Datos

1.146 pares entrada→salida (1.038 de entrenamiento, 108 de validación), en
`data/ft_lector/` del repositorio y regenerables con `scripts/ft/build_lector_data.py`:
1.083 avisos sintéticos con la salida correcta por construcción (fragmento marcado en cada frase)
y 63 salidas del propio Phi-4-mini base filtradas contra la anotación. Ningún modelo más grande
generó ni etiquetó datos. Se descartó todo ejemplo que compartiera 8 palabras seguidas con algún
set de evaluación.

## Resultados (sistema completo, `hard_test`: 30 casos, 240 avisos)

| Sistema | full_correct | exactitud por aviso | aprob. indebida | rechazo falso |
|---|---|---|---|---|
| Agentes con el Lector base (E3) | 5/30 | 214/240 | 6/127 | 20/113 |
| **Agentes con este adaptador** | **16/30** | **225/240** | 8/127 | **7/113** |
| Lector base + 8 ejemplos few-shot (control) | 11/30 | 221/240 | 7/127 | 12/113 |

Los errores de lectura que nacen en el Lector bajan de 162 a 22.

## Limitaciones

- Entrenado sobre los pesos en 8 bits y usado sobre los de 4 bits (Q4_K_M) de Ollama; todos los
  resultados se midieron en esa configuración.
- Español de Chile, avisos inmobiliarios, un único prompt. Fuera de ese rol no se evaluó.
- Aprueba indebidamente 2 avisos más que el sistema base en `hard_test`: corta fragmentos de
  estacionamiento en la puntuación («Estacionamiento: no» en vez de «no; hay estacionamiento en
  calle»), y la herramienta posterior los lee mal sin marcar duda. Ver el caso de fallo en
  `docs/e4_finetuning.md`.
