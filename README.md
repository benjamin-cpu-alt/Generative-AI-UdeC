# Real Estate AI Matcher (Generative AI - 580694)

**Miembro del Equipo:** Carla Maureira V.  
**Curso:** Generative Artificial Intelligence (Primavera 2026)  
**Profesor:** Carlos Navarrete, PhD  

## La Tarea
Matching Automático Comprador-Propiedad con Optimización de Restricciones.
El sistema actúa como un motor de validación que lee descripciones de propiedades no estructuradas y las cruza contra reglas estrictas de un comprador.

## Modelos Candidatos
1. **DeepSeek-R1-Distill-Qwen (7.0B):** Resuelve alucinaciones aritméticas usando Cadena de Pensamiento (CoT).
2. **Granite 4.1 (8.0B):** Resuelve el colapso de formato, garantizando cumplimiento estricto de JSON.
3. **Llama-3.1-8B-Instruct:** Resuelve la pérdida de atención en catálogos extensos de propiedades.

## Estado del Trabajo (Entregable 1)
* Pruebas base de *zero-shot* completadas.
* Ejecutado localmente en macOS usando Ollama (cuantización a 4-bits).
* Los registros de evidencia están disponibles en el directorio `/logs`, demostrando que los modelos <8B fallan en atención y matemáticas si no se utiliza un flujo con herramientas (Agentic Harness).
