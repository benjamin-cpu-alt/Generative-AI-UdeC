# Benchmarks de Memoria (Hardware Local / Edge AI)

Para asegurar que los modelos candidatos corren sin errores de Out-Of-Memory (OOM) al inyectar el catálogo completo de propiedades, se evaluó la huella de VRAM utilizando cuantización a 4-bits (GGUF/NF4) en nuestro hardware disponible.

## Entorno de Ejecución Híbrido:
1. **Workstation Windows:** Intel Core i5-13420H, 16GB RAM, GPU NVIDIA RTX 3050 (6 GB VRAM).
2. **Apple Silicon:** MacBook Air M4 (Memoria Unificada, aceleración Metal).

## Consumo Base de Modelos Candidatos (4-bits):
* **Llama-3.1-8B-Instruct (8B):** ~5.8 GB
* **Granite 4.1 (8B):** ~5.3 GB
* **DeepSeek-R1-Distill-Qwen (7B):** ~4.7 GB

**Conclusión de Factibilidad:**  
Los modelos cuantizados logran ajustarse al estricto límite de 6 GB de la RTX 3050. Si el contexto (KV Cache) aumenta significativamente por la ingesta del catálogo de propiedades, el sistema realizará un *offloading* automático hacia los 16 GB de RAM del sistema. En el caso del MacBook Air M4, la arquitectura de Memoria Unificada absorbe estos modelos de ~5 GB de forma nativa con un amplísimo margen libre.
