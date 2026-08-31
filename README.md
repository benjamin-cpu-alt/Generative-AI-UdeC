# Real Estate AI Matcher (Generative AI - 580694)

**Miembros del Equipo:** Benjamín Grandón V, Carla Maureira V.  
**Curso:** Generative Artificial Intelligence 
**Profesor:** Carlos Navarrete, PhD  

## La Tarea
Matching Automático Comprador-Propiedad con Optimización de Restricciones Cruzadas.  
El sistema actúa como un motor de validación basado en agentes que lee descripciones de propiedades no estructuradas y las evalúa frente a reglas estrictas del comprador. Esto incluye resolver operaciones matemáticas dinámicas (conversiones de UF a CLP, cálculos de ROI) y restricciones espaciales o lógicas. *(El prompt base y los datos de prueba se encuentran en la carpeta `/data`)*.

## Modelos Candidatos
1. **DeepSeek-R1-Distill-Qwen (7.0B) [PRINCIPAL]:** Resuelve las alucinaciones aritméticas mediante el uso de Cadena de Pensamiento (CoT).
2. **Granite 4.1 (8.0B):** Resuelve el colapso de formato, garantizando un esquema JSON estricto para que el sistema pueda procesarlo sin errores.
3. **Phi-4-mini (3.8B):** Propuesto para investigar si una arquitectura multi-agente puede mitigar su severo colapso lógico, manteniendo al mismo tiempo un consumo de memoria ultra-bajo (Edge AI).

## Estado del Trabajo (Entregable 1)
* Pruebas empíricas de línea base (*zero-shot*) completadas.
* Ejecutado 100% de forma local (Edge AI) en un entorno híbrido: Workstation Windows (NVIDIA RTX 3050 6GB) y Apple Silicon (MacBook Air M4), utilizando Ollama con cuantización a 4-bits.
* Los registros de evidencia empírica están disponibles en la carpeta `/experiments`, demostrando que los modelos de 3B a 8B fallan catastróficamente en tareas matemáticas y de retención lógica si no están apoyados por un sistema de agentes (Agentic Harness).
