MODELO: deepseek-r1:7b
EJECUCIÓN: Local (macOS / Ollama)
RESULTADO: Fallo (Alucinación Aritmética y Colapso de Formato)

--- LOG ---
Thinking...
Alright, I need to evaluate each property against the client's hard constraints. Let's go through them one by one.
First, the presupuesto máximo de compra is $4,500 UF. I'll check each property's price...
Prop-D05 is over the budget, so it's rejected. 

[ERROR: La Prop-D05 cuesta 4.100 UF, lo cual es MENOR a 4.500. El modelo alucinó una falla matemática].
...done thinking.

```json
{
  "approved_matches": [
    { "id": "PROP-A42", "price_uf": 4300, "monthly_expenses_clp": 90000 }
  ],
  "rejected": [
    { "id": "PROP-D05", "failed_constraints": ["Presupuesto Máximo de Compra"] }
  ]
}
```

## MODELO: phi4-mini:latest
EJECUCIÓN: Local (macOS / Ollama)
RESULTADO: Fallo (Alucinación de Datos y Colapso de Formato)

--- LOG ---
```json
{
  "approved_matches": [
    {
      "id": "PROP-C88",
      "price_uf": 3900,
      "monthly_expenses_clp": 45000
    }
  ],
  "rejected": [
    {
      "id": "PROP-A42",
      "failed_constraints": ["Monthly expenses (GC) exceed the maximum allowed."]
    },
    {
      "id": "PROP-B19",
      "failed_constraints": ["Pets (felinos) are not allowed.", "Habitaciones are less than the minimum required."]
    },
    {
      "id": "PROP-D05",
      "failed_constraints": ["No includes assigned parking."]
    }
  ]
}
[ANÁLISIS DEL ERROR: El modelo alucinó severamente al extraer la información numérica. Rechazó la PROP-A42 afirmando que sus gastos comunes (90.000) superaban el máximo (120.000). También rechazó la PROP-B19 afirmando que le faltaban habitaciones, cuando el texto indicaba explícitamente "3D/2B" (3 dormitorios). Además, rompió el contrato de formato al inyectar etiquetas de bloque Markdown].
```
##MODELO: granite4.1:8b
EJECUCIÓN: Local (macOS / Ollama)
RESULTADO: Fallo (Atención Selectiva / Lógica)
--- LOG ---
```json

{
  "approved_matches": [
    {
      "id": "PROP-A42",
      "price_uf": 4300,
      "monthly_expenses_clp": 90000
    },
    {
      "id": "PROP-C88",
      "price_uf": 3900,
      "monthly_expenses_clp": 45000
    }
  ],
  "rejected": [
    {
      "id": "PROP-B19",
      "failed_constraints": ["Mascotas: Prohibido felinos"]
    },
    {
      "id": "PROP-D05",
      "failed_constraints": ["Estacionamiento: Faltante estacionamiento interior"]
    }
  ]
}
[ANÁLISIS DEL ERROR: El modelo logró generar el JSON crudo sin inyectar Markdown. Sin embargo, APROBÓ FALSAMENTE la PROP-A42. Dicha propiedad tiene 1 habitación, pero el cliente exigía un mínimo de 2. El modelo sufrió de Atención Selectiva, dándole más peso a las palabras positivas de marketing ("¡Bajo presupuesto!") que a la restricción numérica estricta de las habitaciones].
