# Benchmarks de Memoria (Hardware: NVIDIA T4 15GB - Google Colab)

Para asegurar que los modelos candidatos corren sin errores de Out-Of-Memory (OOM) al inyectar el catálogo completo de propiedades, se evaluó la huella de VRAM utilizando cuantización a 4-bits (GGUF/NF4).

## Consumo Base de Modelos Candidatos:
* **DeepSeek-R1-Distill-Qwen (7B):** ~4.7 GB VRAM
* **Granite 4.1 (8B):** ~5.3 GB VRAM
* **Phi-4-mini (3.8B):** ~2.5 GB VRAM

**Conclusión:** La estructura deja un margen superior a 9 GB de VRAM totalmente libres para alojar el KV Cache, garantizando la factibilidad técnica del proyecto.
