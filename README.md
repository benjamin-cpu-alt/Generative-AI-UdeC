# Real Estate AI Matcher (Generative AI - 580694)

**Team Member:** Carla Maureira V.  
**Course:** Generative Artificial Intelligence (Spring 2026)  
**Instructor:** Carlos Navarrete, PhD  

## The Task
Automated Buyer-Property Matching with Cross-Constraint Optimization.
The system acts as an agentic validation engine that reads unstructured property descriptions and evaluates them against strict buyer rules.

## Model Candidates
1. **DeepSeek-R1-Distill-Qwen (7.0B):** Resolves arithmetic hallucinations via Chain-of-Thought.
2. **Granite 4.1 (8.0B):** Resolves format collapse, ensuring strict JSON compliance.
3. **Llama-3.1-8B-Instruct:** Resolves attention drift over long property catalogs.

## State of the Work (Deliverable 1)
* Baseline zero-shot testing complete.
* Executed locally on macOS using Ollama (4-bit quantization).
* Evidence logs are available in the `/logs` directory, proving 8B models fail at math and attention tasks without an agentic harness.
