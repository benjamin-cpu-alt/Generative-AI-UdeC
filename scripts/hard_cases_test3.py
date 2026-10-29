"""hard_test, casos 21-30 (8 avisos cada uno). SOLO para medir: no se ajusta nada mirándolos.

Convenciones y cuotas: data/cases/hard_test/README.md.
"""
from hard_common import (ANY, B, D, E, M, NO, NONE_, P, R, both, case, hc, kg, only,  # noqa: F401
                         rent_uf)

CASES = [

    # ------------------------------------------------------------------ 21 --
    case("ht_21", 39_150, hc(150_000_000, "gato", 4, 900, 2), ["Ñuñoa", "Macul"],
         "Mensajes de corredor y precios actualizados.", [
        P("HT-2101", """Hola, te comparto: Ñuñoa, 2 dorm 2 baños, 3.700 uf, metro Ñuble a 500 mts,
           gatos bienvenidos, 1 estac propio, arrienda en 18 uf""",
          tags=["estilo", "arriendo_uf"],
          note="WhatsApp; 'uf' en minúsculas; arriendo 18 UF",
          expect=[], loc="Ñuñoa", beds=2, dist=500, pets=only("gato"), parking="propio",
          uf=3700, rent=rent_uf(18, 39_150)),
        P("HT-2102", """Macul, sector Quilín. 3D 1B. $148.000.000. Metro Quilín a 900 m. Se aceptan
           perros y gatos. Estacionamiento asignado.""",
          tags=["dorm_notacion", "casi_cumple"],
          note="900 m == máximo",
          expect=[], loc="Macul", beds=3, dist=900, pets=both(), parking="asignado",
          clp=148_000_000),
        P("HT-2103", """San Joaquín, 2D/2B, UF 3.500, paradero troncal a 300 m y metro a 1 km, admite
           gatos, estacionamiento propio, arriendo $900.000.""",
          tags=["dist_multiple"],
          note="vale el paradero; no preferida, mayor ROI",
          expect=[], loc="San Joaquín", beds=2, dist=300, pets=only("gato"), parking="propio",
          uf=3500, rent=900_000),
        P("HT-2104", """Ñuñoa, 2D. ACTUALIZADO 12/10: el precio baja de UF 4.000 a UF 3.800. Metro
           Villa Frei a 600 m. Gatos permitidos. Estacionamiento propio.""",
          tags=["correccion"],
          note="vale UF 3.800 = $148.770.000",
          expect=[], loc="Ñuñoa", beds=2, dist=600, pets=only("gato"), parking="propio", uf=3800),
        P("HT-2105", """Ñuñoa 2D. UF 3.500. Metro a 400 m. Con estacionamiento propio. Mascotas:
           preguntar.""",
          tags=["mascota_silencio"],
          note="'preguntar' no es aceptación -> convención E3: sin política de mascotas no se descarta (va al final del orden)",
          expect=[], loc="Ñuñoa", beds=2, dist=400, pets=NONE_, parking="propio", uf=3500),
        P("HT-2106", """Macul 3D, 152 palos, metro a 300 m, gatos sí, estac propio""",
          tags=["jerga_monto", "casi_cumple"],
          note="'152 palos' = $152.000.000 > $150.000.000",
          expect=[B], loc="Macul", beds=3, dist=300, pets=only("gato"), parking="propio",
          clp=152_000_000),
        P("HT-2107", """Ñuñoa, 1D+1E (escritorio). UF 3.100. Metro a 300 m. Gatos sí. Con
           estacionamiento propio.""",
          tags=["dorm_notacion", "dorm_no_cuenta"],
          note="'1D+1E' = 1 dormitorio + escritorio",
          expect=[R], loc="Ñuñoa", beds=1, dist=300, pets=only("gato"), parking="propio", uf=3100),
        P("HT-2108", """Ñuñoa, 2D. UF 3.300. Muy bien conectado: a 5 minutos en auto del metro (2,5
           km). Gatos sí. Con estacionamiento propio.""",
          tags=["dist_formato", "distractor"],
          note="2,5 km > 900 m, pese a 'muy bien conectado'",
          expect=[D], loc="Ñuñoa", beds=2, dist=2500, pets=only("gato"), parking="propio",
          uf=3300),
    ]),

    # ------------------------------------------------------------------ 22 --
    case("ht_22", 40_650, hc(160_000_000, "perro", 9, 600, 2), ["San Joaquín"],
         "Distancia máxima estricta (600 m).", [
        P("HT-2201", """San Joaquín, 2D/1B. UF 3.700. Metro San Joaquín a 550 m. Admite perros
           pequeños de hasta 10 kg. Estacionamiento propio. Arriendo $700.000.""",
          tags=["mascota_condicion"],
          note="perros <= 10 kg; el del comprador pesa 9",
          expect=[], loc="San Joaquín", beds=2, dist=550, pets=only("perro", 10),
          parking="propio", uf=3700, rent=700_000),
        P("HT-2202", """La Granja – 3 dorm – $140.000.000 – paradero troncal Santa Rosa 200 m –
           mascotas permitidas – estacionamiento asignado – arriendo $850.000""",
          tags=["estilo"],
          note="no preferida, mayor ROI",
          expect=[], loc="La Granja", beds=3, dist=200, pets=ANY, parking="asignado",
          clp=140_000_000, rent=850_000),
        P("HT-2203", """Pasaje en San Joaquín, a seiscientos metros del metro Rodrigo de Araya. Casa
           2D. Precio 3.850 UF. Pet friendly. Estacionamiento propio.""",
          tags=["cifra_palabras", "casi_cumple"],
          note="600 m en palabras == máximo; UF 3.850 = $156.502.500",
          expect=[], loc="San Joaquín", beds=2, dist=600, pets=ANY, parking="propio", uf=3850),
        P("HT-2204", """San Joaquín, 2D. UF 3.500. Metro a 650 m. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["casi_cumple"],
          note="650 m > 600",
          expect=[D], loc="San Joaquín", beds=2, dist=650, pets=ANY, parking="propio", uf=3500),
        P("HT-2205", """San Joaquín 2D. UF 3.400. Metro a 400 m. Mascotas de hasta 8 kg. Con
           estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="8 kg contra perro de 9",
          expect=[M], loc="San Joaquín", beds=2, dist=400, pets=kg(8), parking="propio", uf=3400),
        P("HT-2206", """San Joaquín, 3D. Precio: UF 4.100; contribuciones $90.000 trimestrales. Metro
           a 300 m. Admite mascotas. Con estacionamiento propio.""",
          tags=["multi_monto"],
          note="UF 4.100 = $166.665.000 > tope",
          expect=[B], loc="San Joaquín", beds=3, dist=300, pets=ANY, parking="propio", uf=4100),
        P("HT-2207", """San Joaquín 2D. UF 3.300. Metro a 300 m. Admite mascotas. Estacionamiento
           opcional (+UF 200).""",
          tags=["estac_ambiguo", "multi_monto"],
          note="opcional con precio aparte = no incluido",
          expect=[E], loc="San Joaquín", beds=2, dist=300, pets=ANY, parking="ninguno", uf=3300),
        P("HT-2208", """San Joaquín. Depto 1D (el 3D del piso 4 ya se vendió). UF 2.900. Metro a 200
           m. Admite mascotas. Con estacionamiento propio.""",
          tags=["distractor"],
          note="el 3D es otra unidad",
          expect=[R], loc="San Joaquín", beds=1, dist=200, pets=ANY, parking="propio", uf=2900),
    ]),

    # ------------------------------------------------------------------ 23 --
    case("ht_23", 38_600, hc(138_000_000, "perro", 30, 1000, 3), ["Puente Alto"],
         "Casas para perro grande; abreviaturas de comuna.", [
        P("HT-2301", """Puente Alto, casa 3D/2B. $129.000.000. Metro Hospital Sótero del Río a 800 m.
           Perros grandes bienvenidos. Estacionamiento propio. Arriendo $650.000.""",
          tags=[],
          note="control",
          expect=[], loc="Puente Alto", beds=3, dist=800, pets=only("perro"), parking="propio",
          clp=129_000_000, rent=650_000),
        P("HT-2302", """Casa en La Florida de 4 dormitorios, valor $135.000.000, paradero troncal a 450
           m, se aceptan mascotas sin restricción, estacionamiento para 2 autos, renta 800
           lucas.""",
          tags=["jerga_monto"],
          note="'800 lucas'; no preferida, mayor ROI",
          expect=[], loc="La Florida", beds=4, dist=450, pets=ANY, parking="propio",
          clp=135_000_000, rent=800_000),
        P("HT-2303", """PTE ALTO / Puente Alto centro: casa de 3 dorm + estar, UF 3.500, metro Plaza
           de Puente Alto a 1 km, mascotas ok, estac. propio""",
          tags=["estilo", "dist_formato", "casi_cumple", "dorm_notacion"],
          note="1 km == máximo; el estar no suma; UF 3.500 = $135.100.000",
          expect=[], loc="Puente Alto", beds=3, dist=1000, pets=ANY, parking="propio", uf=3500),
        P("HT-2304", """Puente Alto, 3D. $120.000.000. Metro a 500 m. Perros de hasta veinticinco
           kilos. Con estacionamiento propio.""",
          tags=["cifra_palabras", "mascota_condicion"],
          note="25 kg (en palabras) contra perro de 30",
          expect=[M], loc="Puente Alto", beds=3, dist=500, pets=only("perro", 25),
          parking="propio", clp=120_000_000),
        P("HT-2305", """Puente Alto, 2 dormitorios y altillo. $110.000.000. Metro a 600 m. Admite
           mascotas. Con estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="el altillo no es dormitorio",
          expect=[R], loc="Puente Alto", beds=2, dist=600, pets=ANY, parking="propio",
          clp=110_000_000),
        P("HT-2306", """Puente Alto 4D. UF 3.590. Metro a 700 m. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["casi_cumple"],
          note="near miss: UF 3.590 = $138.574.000",
          expect=[B], loc="Puente Alto", beds=4, dist=700, pets=ANY, parking="propio", uf=3590),
        P("HT-2307", """Puente Alto 3D. $125.000.000. Metro Las Mercedes a 1,8 km; paradero troncal a
           1.100 m. Admite mascotas. Con estacionamiento propio.""",
          tags=["dist_multiple"],
          note="la menor (1.100 m) supera 1.000",
          expect=[D], loc="Puente Alto", beds=3, dist=1100, pets=ANY, parking="propio",
          clp=125_000_000),
        P("HT-2308", """Puente Alto 3D. $115.000.000. Metro a 600 m. Con estacionamiento propio.
           Consultar condiciones para mascotas.""",
          tags=["mascota_silencio"],
          note="'consultar condiciones' no es aceptación -> convención E3: sin política de mascotas no se descarta (va al final del orden)",
          expect=[], loc="Puente Alto", beds=3, dist=600, pets=NONE_, parking="propio",
          clp=115_000_000),
    ]),

    # ------------------------------------------------------------------ 24 --
    case("ht_24", 41_350, hc(205_000_000, "gato", 8, 1000, 2), ["Ñuñoa"],
         "Ñuñoa: barrios entre paréntesis y gastos mezclados.", [
        P("HT-2401", """Ñuñoa, 3D/2B, 95 m². UF 4.900. Metro Plaza Egaña a 700 m. Gatos permitidos sin
           límite. Estacionamiento propio. Arriendo 1,1 millones.""",
          tags=["jerga_monto"],
          note="'1,1 millones' = $1.100.000; UF 4.900 = $202.615.000",
          expect=[], loc="Ñuñoa", beds=3, dist=700, pets=only("gato"), parking="propio",
          uf=4900, rent=1_100_000),
        P("HT-2402", """Ñuñoa (Villa Olímpica). Dos dormitorios. Valor: 4.300 UF. Metro Estadio
           Nacional a 450 m. Acepta mascotas de hasta 10 kg. Estacionamiento asignado.""",
          tags=["comuna_posicion", "cifra_palabras", "mascota_condicion"],
          note="'Dos dormitorios'; 8 <= 10 kg",
          expect=[], loc="Ñuñoa", beds=2, dist=450, pets=kg(10), parking="asignado", uf=4300),
        P("HT-2403", """Providencia, 2D/2B, $195.000.000, metro Salvador a 350 m, admite mascotas,
           estacionamiento propio, arriendo $1.300.000.""",
          tags=[],
          note="no preferida, mayor ROI",
          expect=[], loc="Providencia", beds=2, dist=350, pets=ANY, parking="propio",
          clp=195_000_000, rent=1_300_000),
        P("HT-2404", """Ñuñoa, 2D. Precio venta $199.000.000; GC $95.000; contribuciones $60.000
           trimestrales. Paradero troncal a 200 m. Gatos sí. Estacionamiento propio.""",
          tags=["multi_monto"],
          note="tres montos; solo el primero es el precio",
          expect=[], loc="Ñuñoa", beds=2, dist=200, pets=only("gato"), parking="propio",
          clp=199_000_000),
        P("HT-2405", """Ñuñoa 2D. UF 4.200. Metro a 400 m. Solo mascotas de hasta 5 kg. Con
           estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="5 kg contra gato de 8",
          expect=[M], loc="Ñuñoa", beds=2, dist=400, pets=kg(5), parking="propio", uf=4200),
        P("HT-2406", """Ñuñoa 3D. UF 4.960. Metro a 500 m. Gatos sí. Con estacionamiento propio.""",
          tags=["casi_cumple"],
          note="near miss: UF 4.960 = $205.096.000",
          expect=[B], loc="Ñuñoa", beds=3, dist=500, pets=only("gato"), parking="propio", uf=4960),
        P("HT-2407", """Ñuñoa 2D. UF 4.000. Metro a 500 m. Gatos sí. Opción de comprar
           estacionamiento en el subterráneo.""",
          tags=["estac_ambiguo"],
          note="'opción de comprar' = no incluido",
          expect=[E], loc="Ñuñoa", beds=2, dist=500, pets=only("gato"), parking="ninguno",
          uf=4000),
        P("HT-2408", """Ñuñoa 3D. UF 4.500. Metro a 1,15 km. Gatos sí. Con estacionamiento propio.""",
          tags=["dist_formato"],
          note="1,15 km = 1.150 m > 1.000",
          expect=[D], loc="Ñuñoa", beds=3, dist=1150, pets=only("gato"), parking="propio",
          uf=4500),
    ]),

    # ------------------------------------------------------------------ 25 --
    case("ht_25", 39_500, hc(170_000_000, "perro", 14, 800, 2), ["Providencia"],
         "Unidades del mismo edificio y excepciones de especie.", [
        P("HT-2501", """Providencia, 2D/2B. UF 4.250. Metro Los Leones a 600 m. Mascotas de hasta 15
           kg. Estacionamiento propio. Arriendo 21 UF.""",
          tags=["arriendo_uf", "mascota_condicion"],
          note="14 <= 15 kg; arriendo 21 UF; UF 4.250 = $167.875.000",
          expect=[], loc="Providencia", beds=2, dist=600, pets=kg(15), parking="propio",
          uf=4250, rent=rent_uf(21, 39_500)),
        P("HT-2502", """Ñuñoa: 3D, $160.000.000, metro Irarrázaval a 500 m, perros permitidos,
           estacionamiento asignado, arriendo $1.000.000.""",
          tags=[],
          note="no preferida, mayor ROI",
          expect=[], loc="Ñuñoa", beds=3, dist=500, pets=only("perro"), parking="asignado",
          clp=160_000_000, rent=1_000_000),
        P("HT-2503", """Providencia. Unidad 802: 2 dormitorios, UF 4.100, metro Manuel Montt a 750 m,
           pet friendly, estacionamiento propio. (La unidad 1102, de 3 dormitorios, se vende en
           UF 4.800.)""",
          tags=["distractor"],
          note="los datos entre paréntesis son de otra unidad",
          expect=[], loc="Providencia", beds=2, dist=750, pets=ANY, parking="propio", uf=4100),
        P("HT-2504", """Providencia 2D, 172 millones, metro a 300 m, admite mascotas, con
           estacionamiento propio.""",
          tags=["jerga_monto", "casi_cumple"],
          note="'172 millones' > $170.000.000",
          expect=[B], loc="Providencia", beds=2, dist=300, pets=ANY, parking="propio",
          clp=172_000_000),
        P("HT-2505", """Providencia 2D. UF 4.000. Metro a 400 m. Se aceptan mascotas, excepto perros.
           Con estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="'excepto perros' = solo gatos",
          expect=[M], loc="Providencia", beds=2, dist=400, pets=only("gato"), parking="propio",
          uf=4000),
        P("HT-2506", """Providencia 3D. UF 4.200. Metro a 900 m; paradero troncal a 850 m. Admite
           mascotas. Con estacionamiento propio.""",
          tags=["dist_multiple"],
          note="la menor (850 m) supera 800",
          expect=[D], loc="Providencia", beds=3, dist=850, pets=ANY, parking="propio", uf=4200),
        P("HT-2507", """Providencia, 1D/1B + estar. UF 3.600. Metro a 300 m. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["dorm_notacion", "dorm_no_cuenta"],
          note="el estar no cuenta: 1 < 2",
          expect=[R], loc="Providencia", beds=1, dist=300, pets=ANY, parking="propio", uf=3600),
        P("HT-2508", """Providencia 2D. UF 3.900. Metro a 500 m. Con estacionamiento propio. Edificio
           familiar y tranquilo.""",
          tags=["mascota_silencio"],
          note="no habla de mascotas -> convención E3: sin política de mascotas no se descarta (va al final del orden)",
          expect=[], loc="Providencia", beds=2, dist=500, pets=NONE_, parking="propio", uf=3900),
    ]),

    # ------------------------------------------------------------------ 26 --
    case("ht_26", 40_000, hc(120_000_000, "gato", 5, 1100, 2), ["Independencia", "Recoleta"],
         "Sector norte; estacionamiento vendido.", [
        P("HT-2601", """Independencia, 2D/1B. UF 2.950. Metro Hospitales a 1.100 m. Gatos OK.
           Estacionamiento propio. Arriendo 13 UF.""",
          tags=["casi_cumple", "arriendo_uf"],
          note="1.100 m == máximo; UF 2.950 = $118.000.000",
          expect=[], loc="Independencia", beds=2, dist=1100, pets=only("gato"), parking="propio",
          uf=2950, rent=rent_uf(13, 40_000)),
        P("HT-2602", """Recoleta: 2 dormitorios, $115.000.000, metro Cerro Blanco a 600 m, acepta
           mascotas, estac. asignado, arriendo $560.000.""",
          tags=[],
          note="control",
          expect=[], loc="Recoleta", beds=2, dist=600, pets=ANY, parking="asignado",
          clp=115_000_000, rent=560_000),
        P("HT-2603", """Conchalí, 3D, $105.000.000, paradero troncal a 300 m, gatos permitidos,
           estacionamiento propio, arriendo $650.000.""",
          tags=[],
          note="no preferida, mayor ROI",
          expect=[], loc="Conchalí", beds=3, dist=300, pets=only("gato"), parking="propio",
          clp=105_000_000, rent=650_000),
        P("HT-2604", """independencia 2 dorm 110 palos metro plaza chacabuco 500 mts gatos si estac
           propio""",
          tags=["estilo", "jerga_monto"],
          note="minúsculas, sin puntuación; '110 palos'",
          expect=[], loc="Independencia", beds=2, dist=500, pets=only("gato"), parking="propio",
          clp=110_000_000),
        P("HT-2605", """Independencia 2D. $100.000.000. Metro a 400 m. Gatos hasta 4 kg. Con
           estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="4 kg contra gato de 5",
          expect=[M], loc="Independencia", beds=2, dist=400, pets=only("gato", 4),
          parking="propio", clp=100_000_000),
        P("HT-2606", """Recoleta 2D. Ciento veintiún millones. Metro a 500 m. Gatos sí. Con
           estacionamiento propio.""",
          tags=["cifra_palabras", "casi_cumple"],
          note="$121.000.000 en palabras > $120.000.000",
          expect=[B], loc="Recoleta", beds=2, dist=500, pets=only("gato"), parking="propio",
          clp=121_000_000),
        P("HT-2607", """Recoleta 2D. $112.000.000. Metro a 300 m. Gatos sí. Incluye estacionamiento.
           Corrección: el estacionamiento ya fue vendido por separado.""",
          tags=["correccion", "estac_ambiguo"],
          note="vale la corrección: ya no incluye estacionamiento",
          expect=[E], loc="Recoleta", beds=2, dist=300, pets=only("gato"), parking="ninguno",
          clp=112_000_000),
        P("HT-2608", """Independencia, 1 dormitorio. $90.000.000. Metro a 200 m. Gatos sí. Con
           estacionamiento propio.""",
          tags=[],
          note="1 < 2",
          expect=[R], loc="Independencia", beds=1, dist=200, pets=only("gato"), parking="propio",
          clp=90_000_000),
    ]),

    # ------------------------------------------------------------------ 27 --
    case("ht_27", 38_850, hc(155_000_000, "perro", 20, 900, 2), ["La Florida"],
         "Erratas corregidas en el propio aviso.", [
        P("HT-2701", """La Florida, 3D/2B. UF 3.950. Metro Rojas Magallanes a 400 m. Perros de hasta
           20 kg. Estacionamiento propio. Arriendo $720.000.""",
          tags=["casi_cumple", "mascota_condicion"],
          note="20 kg == 20 kg: cumple; UF 3.950 = $153.457.500",
          expect=[], loc="La Florida", beds=3, dist=400, pets=only("perro", 20),
          parking="propio", uf=3950, rent=720_000),
        P("HT-2702", """Macul | 2D/2B | $140.000.000 | metro Las Torres 500 m | mascotas sí |
           estacionamiento propio | arriendo $850.000""",
          tags=["estilo"],
          note="no preferida, mayor ROI",
          expect=[], loc="Macul", beds=2, dist=500, pets=ANY, parking="propio",
          clp=140_000_000, rent=850_000),
        P("HT-2703", """La Florida, 2D. $150.000.000. Metro Vicente Valdés a 1.400 m; paradero
           troncal de Vicuña Mackenna a 300 m. Admite mascotas. Estacionamiento asignado.""",
          tags=["dist_multiple"],
          note="vale el paradero",
          expect=[], loc="La Florida", beds=2, dist=300, pets=ANY, parking="asignado",
          clp=150_000_000),
        P("HT-2704", """La Florida 3D. Precio: $149.000.000 (error de tipeo: el valor real es
           $159.000.000). Metro a 500 m. Admite mascotas. Con estacionamiento propio.""",
          tags=["correccion"],
          note="vale el valor corregido, sobre el tope",
          expect=[B], loc="La Florida", beds=3, dist=500, pets=ANY, parking="propio",
          clp=159_000_000),
        P("HT-2705", """La Florida 2D. UF 3.600. Metro a 500 m. Solo gatos. Con estacionamiento
           propio.""",
          tags=["mascota_condicion"],
          note="solo gatos; comprador con perro",
          expect=[M], loc="La Florida", beds=2, dist=500, pets=only("gato"), parking="propio",
          uf=3600),
        P("HT-2706", """La Florida, 1D + escritorio + sala de juegos. UF 3.200. Metro a 400 m. Admite
           mascotas. Con estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="ni el escritorio ni la sala de juegos cuentan",
          expect=[R], loc="La Florida", beds=1, dist=400, pets=ANY, parking="propio", uf=3200),
        P("HT-2707", """La Florida 3D. UF 3.700. A 950 m del metro. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["casi_cumple"],
          note="950 m > 900",
          expect=[D], loc="La Florida", beds=3, dist=950, pets=ANY, parking="propio", uf=3700),
        P("HT-2708", """La Florida, 3D. $145.000.000. Metro a 600 m. Admite mascotas. Estacionamiento
           en la vía pública frente a la casa.""",
          tags=["estac_ambiguo"],
          note="vía pública = calle",
          expect=[E], loc="La Florida", beds=3, dist=600, pets=ANY, parking="calle",
          clp=145_000_000),
    ]),

    # ------------------------------------------------------------------ 28 --
    case("ht_28", 41_150, hc(190_000_000, "gato", 6, 700, 3), ["Ñuñoa"],
         "Familias en Ñuñoa; notación con escritorio.", [
        P("HT-2801", """Ñuñoa, 3D/2B. UF 4.550. Metro Ñuñoa a 350 m. Gatos sí. Estacionamiento propio.
           Arriendo 23 UF.""",
          tags=["arriendo_uf"],
          note="arriendo 23 UF; UF 4.550 = $187.232.500",
          expect=[], loc="Ñuñoa", beds=3, dist=350, pets=only("gato"), parking="propio",
          uf=4550, rent=rent_uf(23, 41_150)),
        P("HT-2802", """Casa en pasaje de Ñuñoa: 4 dormitorios, $188.000.000, metro Chile España a 700
           m, admite mascotas, estacionamiento para 2 autos.""",
          tags=["casi_cumple"],
          note="700 m == máximo",
          expect=[], loc="Ñuñoa", beds=4, dist=700, pets=ANY, parking="propio", clp=188_000_000),
        P("HT-2803", """Macul, 3D/2B, $170.000.000, metro Macul a 500 m, gatos OK, estacionamiento
           propio, arriendo $1.150.000.""",
          tags=[],
          note="no preferida, mayor ROI",
          expect=[], loc="Macul", beds=3, dist=500, pets=only("gato"), parking="propio",
          clp=170_000_000, rent=1_150_000),
        P("HT-2804", """Ñuñoa. 3 dorms (el aviso anterior decía 2 por error). UF 4.400. Metro Monseñor
           Eyzaguirre a 600 m. Gatos permitidos. Estac. propio.""",
          tags=["correccion", "dorm_notacion"],
          note="vale 3 dormitorios; UF 4.400 = $181.060.000",
          expect=[], loc="Ñuñoa", beds=3, dist=600, pets=only("gato"), parking="propio", uf=4400),
        P("HT-2805", """Ñuñoa, 2D/2B + E. UF 4.000. Metro a 300 m. Gatos sí. Con estacionamiento
           propio.""",
          tags=["dorm_notacion", "dorm_no_cuenta"],
          note="'+ E' = escritorio: 2 < 3",
          expect=[R], loc="Ñuñoa", beds=2, dist=300, pets=only("gato"), parking="propio", uf=4000),
        P("HT-2806", """Ñuñoa 3D. UF 4.300. Metro a 300 m. Con estacionamiento propio. Mascotas:
           depende del reglamento.""",
          tags=["mascota_silencio"],
          note="'depende del reglamento' no es aceptación -> convención E3: sin política de mascotas no se descarta (va al final del orden)",
          expect=[], loc="Ñuñoa", beds=3, dist=300, pets=NONE_, parking="propio", uf=4300),
        P("HT-2807", """Ñuñoa 3D. $185.000.000 + estacionamiento $8.000.000. Metro a 500 m. Gatos
           sí.""",
          tags=["multi_monto", "estac_ambiguo"],
          note="el estacionamiento tiene precio aparte: no incluido; el precio sí cumple",
          expect=[E], loc="Ñuñoa", beds=3, dist=500, pets=only("gato"), parking="ninguno",
          clp=185_000_000),
        P("HT-2808", """Ñuñoa 3D. UF 4.100. Metro a 800 metros. Gatos sí. Con estacionamiento
           propio.""",
          tags=[],
          note="800 m > 700",
          expect=[D], loc="Ñuñoa", beds=3, dist=800, pets=only("gato"), parking="propio", uf=4100),
    ]),

    # ------------------------------------------------------------------ 29 --
    case("ht_29", 39_800, hc(145_000_000, "perro", 10, 1000, 2), ["Santiago"],
         "Centro de Santiago: ciclovías y avisos en mayúsculas.", [
        P("HT-2901", """Santiago, barrio Brasil. 2D/1B. UF 3.500. Metro Los Héroes a 500 m. Perros de
           hasta 12 kg. Estacionamiento propio. Arriendo $650.000.""",
          tags=["mascota_condicion"],
          note="10 <= 12 kg; UF 3.500 = $139.300.000",
          expect=[], loc="Santiago", beds=2, dist=500, pets=only("perro", 12), parking="propio",
          uf=3500, rent=650_000),
        P("HT-2902", """Estación Central: 2D, $120.000.000, metro Unión Latinoamericana a 400 m, pet
           friendly, estacionamiento asignado, arriendo $700.000.""",
          tags=[],
          note="no preferida, mayor ROI",
          expect=[], loc="Estación Central", beds=2, dist=400, pets=ANY, parking="asignado",
          clp=120_000_000, rent=700_000),
        P("HT-2903", """SANTIAGO. DEPTO 2D 2B. 140 MILLONES. METRO SANTA LUCÍA 300 MTS. ACEPTA
           MASCOTAS. ESTAC. ASIGNADO.""",
          tags=["estilo", "jerga_monto", "dorm_notacion"],
          note="mayúsculas; '140 MILLONES' sin $",
          expect=[], loc="Santiago", beds=2, dist=300, pets=ANY, parking="asignado",
          clp=140_000_000),
        P("HT-2904", """Santiago, 2D. UF 3.650. Metro a 400 m. Admite mascotas. Con estacionamiento
           propio.""",
          tags=["casi_cumple"],
          note="near miss: UF 3.650 = $145.270.000",
          expect=[B], loc="Santiago", beds=2, dist=400, pets=ANY, parking="propio", uf=3650),
        P("HT-2905", """Santiago 2D. $130.000.000. Metro a 400 m. Perros hasta 8 kg. Con
           estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="8 kg contra perro de 10",
          expect=[M], loc="Santiago", beds=2, dist=400, pets=only("perro", 8), parking="propio",
          clp=130_000_000),
        P("HT-2906", """Santiago, 2D. $120.000.000. El metro más cercano está a 1.100 m, pero hay
           ciclovía en la puerta. Admite mascotas. Con estacionamiento propio.""",
          tags=["distractor"],
          note="la ciclovía no cambia la distancia: 1.100 > 1.000",
          expect=[D], loc="Santiago", beds=2, dist=1100, pets=ANY, parking="propio",
          clp=120_000_000),
        P("HT-2907", """Santiago 2D. $125.000.000. Metro a 300 m. Admite mascotas. Sin
           estacionamiento.""",
          tags=[],
          note="sin estacionamiento",
          expect=[E], loc="Santiago", beds=2, dist=300, pets=ANY, parking="ninguno",
          clp=125_000_000),
        P("HT-2908", """Santiago, departamento de un ambiente (studio). $85.000.000. Metro a 200 m.
           Admite mascotas. Con estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="un ambiente = 0 dormitorios",
          expect=[R], loc="Santiago", beds=0, dist=200, pets=ANY, parking="propio",
          clp=85_000_000),
    ]),

    # ------------------------------------------------------------------ 30 --
    case("ht_30", 40_550, hc(210_000_000, "perro", 16, 1200, 2), ["Las Condes", "Vitacura"],
         "Sector oriente: bodegas opcionales y límites justos.", [
        P("HT-3001", """Las Condes, 2D/2B. UF 5.100. Metro Hernando de Magallanes a 1.150 m. Perros
           hasta 20 kg. Estacionamiento propio. Arriendo 40 UF.""",
          tags=["arriendo_uf"],
          note="arriendo 40 UF; UF 5.100 = $206.805.000",
          expect=[], loc="Las Condes", beds=2, dist=1150, pets=only("perro", 20),
          parking="propio", uf=5100, rent=rent_uf(40, 40_550)),
        P("HT-3002", """Vitacura: tres dormitorios, valor $205.000.000, paradero troncal a 900 m,
           mascotas permitidas, estacionamiento asignado.""",
          tags=["cifra_palabras", "comuna_posicion"],
          note="'tres dormitorios'; sin arriendo",
          expect=[], loc="Vitacura", beds=3, dist=900, pets=ANY, parking="asignado",
          clp=205_000_000),
        P("HT-3003", """Providencia, 3D/2B, $190.000.000, metro Tobalaba a 500 m, perros permitidos,
           estacionamiento propio, arriendo $1.400.000.""",
          tags=[],
          note="no preferida: va después de las preferidas aunque tenga ROI",
          expect=[], loc="Providencia", beds=3, dist=500, pets=only("perro"), parking="propio",
          clp=190_000_000, rent=1_400_000),
        P("HT-3004", """Las Condes. Valor UF 5.150. Bodega UF 100 opcional. GC $180.000. 2
           dormitorios. Metro a 1,2 km. Admite perros medianos (hasta 18 kg). Estacionamiento
           propio.""",
          tags=["multi_monto", "casi_cumple", "dist_formato"],
          note="1,2 km == máximo; UF 5.150 = $208.832.500; la bodega no suma",
          expect=[], loc="Las Condes", beds=2, dist=1200, pets=only("perro", 18),
          parking="propio", uf=5150),
        P("HT-3005", """Vitacura 3D. UF 5.000. Metro a 400 m. No se aceptan perros de más de 15 kg.
           Con estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="límite 15 kg contra perro de 16",
          expect=[M], loc="Vitacura", beds=3, dist=400, pets=kg(15), parking="propio", uf=5000),
        P("HT-3006", """Vitacura 3D. UF 5.200. Metro a 600 m. Admite mascotas. Con estacionamiento
           propio.""",
          tags=["casi_cumple"],
          note="near miss: UF 5.200 = $210.860.000",
          expect=[B], loc="Vitacura", beds=3, dist=600, pets=ANY, parking="propio", uf=5200),
        P("HT-3007", """Las Condes 2D. UF 4.800. Metro a 600 m. Admite mascotas. Estacionamiento de
           visita reservable.""",
          tags=["estac_ambiguo"],
          note="visita reservable sigue siendo de visitas",
          expect=[E], loc="Las Condes", beds=2, dist=600, pets=ANY, parking="visitas", uf=4800),
        P("HT-3008", """Las Condes 3D. UF 4.900. A 15 minutos del metro en bus. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["dist_formato"],
          note="minutos en bus: no verificable",
          expect=[D], loc="Las Condes", beds=3, dist=None, pets=ANY, parking="propio", uf=4900),
    ]),
]
