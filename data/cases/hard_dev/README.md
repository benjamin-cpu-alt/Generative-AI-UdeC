# Set HARD — dev

10 casos y 70 avisos escritos a mano: 31 aprobadas (44 %). Es el conjunto de **ajuste** de
la E3: aquí se iteran los prompts y agentes, se mira cada fallo y se corrige.

Cubre los mismos fenómenos que `hard_test/` con redacciones distintas. El protocolo, las
cuotas y las convenciones de anotación están en `../hard_test/README.md`, y la fuente en
`scripts/hard_cases_dev.py` (se regenera con `python3 scripts/build_hard.py`).
