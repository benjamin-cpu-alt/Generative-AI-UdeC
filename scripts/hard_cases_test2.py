"""hard_test, casos 11-20 (8 avisos cada uno). SOLO para medir: no se ajusta nada mirándolos.

Convenciones y cuotas: data/cases/hard_test/README.md.
"""
from hard_common import (ANY, B, D, E, M, NO, NONE_, P, R, both, case, hc, kg, only,  # noqa: F401
                         rent_uf)

CASES = [

    # ------------------------------------------------------------------ 11 --
    case("ht_11", 39_050, hc(160_000_000, None, None, 800, 2), ["Ñuñoa"],
         "Comprador sin mascota; comunas en direcciones.", [
        P("HT-1101", """Calle Suecia con Irarrázaval (Ñuñoa). Depto 2D/2B, 64 m². UF 3.990. Metro
           Irarrázaval a 250 m. Prohibidas las mascotas. Estacionamiento subterráneo propio.
           Arriendo 19 UF.""",
          tags=["comuna_posicion", "mascota_condicion", "arriendo_uf"],
          note="comuna entre paréntesis; prohíbe mascotas pero el comprador no tiene",
          expect=[], loc="Ñuñoa", beds=2, dist=250, pets=NO, parking="propio",
          uf=3990, rent=rent_uf(19, 39_050)),
        P("HT-1102", """Ñuñoa: depto de tres dormitorios a cuatrocientos metros del metro Ñuble;
           valor $158.000.000; estacionamiento asignado; arriendo $700.000.""",
          tags=["cifra_palabras", "comuna_posicion"],
          note="dormitorios y distancia en palabras",
          expect=[], loc="Ñuñoa", beds=3, dist=400, pets=NONE_, parking="asignado",
          clp=158_000_000, rent=700_000),
        P("HT-1103", """Macul. 2D/1B. UF 3.400. Paradero troncal a 150 m y metro a 900 m.
           Estacionamiento propio. Renta $950.000.""",
          tags=["dist_multiple"],
          note="vale el paradero; no preferida, mayor ROI",
          expect=[], loc="Macul", beds=2, dist=150, pets=NONE_, parking="propio",
          uf=3400, rent=950_000),
        P("HT-1104", """ÑUÑOA – 2 DORMITORIOS – UF 4.050 – METRO CHILE ESPAÑA 780 M – ESTACIONAMIENTO
           PROPIO""",
          tags=["estilo", "casi_cumple"],
          note="mayúsculas; 780 m justo bajo 800; UF 4.050 = $158.152.500",
          expect=[], loc="Ñuñoa", beds=2, dist=780, pets=NONE_, parking="propio", uf=4050),
        P("HT-1105", """Ñuñoa, 3D. $162.000.000; GC $130.000. Metro a 300 m. Con estacionamiento
           propio.""",
          tags=["multi_monto", "casi_cumple"],
          note="$162.000.000 > tope por $2.000.000",
          expect=[B], loc="Ñuñoa", beds=3, dist=300, pets=NONE_, parking="propio",
          clp=162_000_000),
        P("HT-1106", """Ñuñoa, 2D/2B. UF 3.700. Metro a 500 m. Estacionamiento: el edificio cuenta
           con estacionamientos para visitas.""",
          tags=["estac_ambiguo"],
          note="solo visitas",
          expect=[E], loc="Ñuñoa", beds=2, dist=500, pets=NONE_, parking="visitas", uf=3700),
        P("HT-1107", """Ñuñoa 2D. UF 3.500. Paradero troncal a 950 m y metro Plaza Egaña a 1,3 km.
           Con estacionamiento propio.""",
          tags=["dist_multiple", "dist_formato"],
          note="la menor es 950 m, igual > 800",
          expect=[D], loc="Ñuñoa", beds=2, dist=950, pets=NONE_, parking="propio", uf=3500),
        P("HT-1108", """Ñuñoa, 1 dormitorio + estudio sin ventana. UF 3.000. Metro a 400 m. Con
           estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="el estudio no es dormitorio",
          expect=[R], loc="Ñuñoa", beds=1, dist=400, pets=NONE_, parking="propio", uf=3000),
    ]),

    # ------------------------------------------------------------------ 12 --
    case("ht_12", 40_450, hc(175_000_000, "gato", 3, 1000, 2), ["Las Condes"],
         "Excepciones de mascotas y marketing de conectividad.", [
        P("HT-1201", """Las Condes, Av. Apoquindo. 2D/2B. UF 4.250. Metro Alcántara a 300 m. Gatos
           permitidos. Incluye estacionamiento y bodega. Arriendo 24 UF.""",
          tags=["arriendo_uf"],
          note="arriendo 24 UF; UF 4.250 = $171.912.500",
          expect=[], loc="Las Condes", beds=2, dist=300, pets=only("gato"), parking="propio",
          uf=4250, rent=rent_uf(24, 40_450)),
        P("HT-1202", """Providencia: 3D, $160.000.000, a 600 metros de metro Pedro de Valdivia, se
           aceptan gatos y perros pequeños (hasta 8 kg), estacionamiento propio, arriendo
           $1.100.000.""",
          tags=["mascota_condicion"],
          note="gatos y perros <= 8 kg; no preferida, mayor ROI",
          expect=[], loc="Providencia", beds=3, dist=600, pets=both(8), parking="propio",
          clp=160_000_000, rent=1_100_000),
        P("HT-1203", """Las Condes, 2D. UF 4.000. Metro a 500 m. Mascotas no permitidas (excepto
           peces). Con estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="'excepto peces' no permite gatos",
          expect=[M], loc="Las Condes", beds=2, dist=500, pets=NO, parking="propio", uf=4000),
        P("HT-1204", """Departamento 2 dormitorios / 2 baños, UF 4.300, a 1 km del metro Los
           Dominicos, acepta mascotas, estacionamiento propio. Ubicado en Las Condes.""",
          tags=["comuna_posicion", "casi_cumple", "dist_formato"],
          note="1 km == máximo; comuna al final",
          expect=[], loc="Las Condes", beds=2, dist=1000, pets=ANY, parking="propio", uf=4300),
        P("HT-1205", """Las Condes, 3D. UF 4.330. Metro a 400 m. Gatos sí. Con estacionamiento
           propio.""",
          tags=["casi_cumple"],
          note="near miss: UF 4.330 = $175.148.500",
          expect=[B], loc="Las Condes", beds=3, dist=400, pets=only("gato"), parking="propio",
          uf=4330),
        P("HT-1206", """Las Condes, 2D. UF 3.900. Metro a 600 m. Con estacionamiento propio. Edificio
           con piscina y quincho.""",
          tags=["mascota_silencio"],
          note="no habla de mascotas",
          expect=[M], loc="Las Condes", beds=2, dist=600, pets=NONE_, parking="propio", uf=3900),
        P("HT-1207", """Las Condes 2D. UF 3.800. ¡Excelente conectividad! El metro está a 20 minutos
           caminando. Gatos OK. Con estacionamiento propio.""",
          tags=["dist_formato", "distractor"],
          note="'excelente conectividad' con solo minutos",
          expect=[D], loc="Las Condes", beds=2, dist=None, pets=only("gato"), parking="propio",
          uf=3800),
        P("HT-1208", """Las Condes, 1D/1B + terraza techada habilitada como dormitorio. UF 3.700.
           Metro a 300 m. Gatos sí. Con estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="la terraza habilitada no es dormitorio",
          expect=[R], loc="Las Condes", beds=1, dist=300, pets=only("gato"), parking="propio",
          uf=3700),
    ]),

    # ------------------------------------------------------------------ 13 --
    case("ht_13", 38_800, hc(112_000_000, "perro", 12, 700, 1), ["Estación Central"],
         "Departamentos de 1 dormitorio; montos escritos con palabras.", [
        P("HT-1301", """Estación Central / 1 dorm / 1 baño / 2.750 UF / metro San Alberto Hurtado 300 m
           / acepta perros medianos hasta 15 kg / estacionamiento asignado / arriendo 420.000""",
          tags=["estilo", "mascota_condicion"],
          note="ficha con barras; perros <= 15 kg",
          expect=[], loc="Estación Central", beds=1, dist=300, pets=only("perro", 15),
          parking="asignado", uf=2750, rent=420_000),
        P("HT-1302", """Depto 1D en Estación Central, valor $109.500.000, metro Pila del Ganso a 650 m
           (también paradero troncal a 900 m), mascotas permitidas, estac. propio.""",
          tags=["dist_multiple"],
          note="vale el metro (650 m), la menor",
          expect=[], loc="Estación Central", beds=1, dist=650, pets=ANY, parking="propio",
          clp=109_500_000),
        P("HT-1303", """Estación Central: 2 dormitorios, ciento diez millones, a 200 m del metro,
           admite mascotas, con estacionamiento propio, se arrienda en cuatrocientos ochenta mil
           pesos.""",
          tags=["cifra_palabras"],
          note="precio y arriendo en palabras",
          expect=[], loc="Estación Central", beds=2, dist=200, pets=ANY, parking="propio",
          clp=110_000_000, rent=480_000),
        P("HT-1304", """Quinta Normal (Av. Matucana): 1D/1B, UF 2.600, metro Quinta Normal a 400 m,
           mascotas OK, estacionamiento propio, arriendo $560.000.""",
          tags=["comuna_posicion"],
          note="no preferida, mayor ROI",
          expect=[], loc="Quinta Normal", beds=1, dist=400, pets=ANY, parking="propio",
          uf=2600, rent=560_000),
        P("HT-1305", """Estación Central, 1D. UF 2.500. Metro a 300 m. Solo mascotas de hasta 10 kg.
           Con estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="10 kg contra perro de 12",
          expect=[M], loc="Estación Central", beds=1, dist=300, pets=kg(10), parking="propio",
          uf=2500),
        P("HT-1306", """Estación Central, 1D. UF 2.890. Metro a 250 m. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["casi_cumple"],
          note="near miss: UF 2.890 = $112.132.000",
          expect=[B], loc="Estación Central", beds=1, dist=250, pets=ANY, parking="propio",
          uf=2890),
        P("HT-1307", """Estación Central, 1D. UF 2.700. Metro a 300 m. Admite mascotas. Sin
           estacionamiento: hay un parking público al frente.""",
          tags=["estac_ambiguo", "distractor"],
          note="un parking público no es estacionamiento de la unidad",
          expect=[E], loc="Estación Central", beds=1, dist=300, pets=ANY, parking="ninguno",
          uf=2700),
        P("HT-1308", """Estación Central, 1D. UF 2.400. El metro queda a 2 cuadras. Admite mascotas.
           Con estacionamiento propio.""",
          tags=["dist_formato"],
          note="cuadras: no verificable",
          expect=[D], loc="Estación Central", beds=1, dist=None, pets=ANY, parking="propio",
          uf=2400),
    ]),

    # ------------------------------------------------------------------ 14 --
    case("ht_14", 41_250, hc(195_000_000, "perro", 20, 900, 2), ["La Reina"],
         "Casas con patio; precio corregido por el dueño.", [
        P("HT-1401", """La Reina, casa 3D/2B con patio. UF 4.700. Paradero troncal en Av. Larraín a
           500 m. Se aceptan perros. Estacionamiento para un auto. Arriendo $1.000.000.""",
          tags=["casi_cumple"],
          note="UF 4.700 = $193.875.000, justo bajo el tope",
          expect=[], loc="La Reina", beds=3, dist=500, pets=only("perro"), parking="propio",
          uf=4700, rent=1_000_000),
        P("HT-1402", """Peñalolén — 3 dormitorios — $170.000.000 — metro Grecia 700 m — mascotas sin
           restricción — estacionamiento propio — arriendo $1.150.000""",
          tags=["estilo"],
          note="no preferida, mayor ROI",
          expect=[], loc="Peñalolén", beds=3, dist=700, pets=ANY, parking="propio",
          clp=170_000_000, rent=1_150_000),
        P("HT-1403", """La Reina, 2D. UF 4.300. Metro a 400 m. Se aceptan mascotas pequeñas de máximo
           10 kg. Con estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="10 kg contra perro de 20",
          expect=[M], loc="La Reina", beds=2, dist=400, pets=kg(10), parking="propio", uf=4300),
        P("HT-1404", """La Reina, 2D/2B. Publicado en UF 4.900; el propietario lo bajó a UF 4.600.
           Metro Plaza Egaña a 850 m. Mascotas permitidas. Estac. propio.""",
          tags=["correccion"],
          note="vale UF 4.600 = $189.750.000",
          expect=[], loc="La Reina", beds=2, dist=850, pets=ANY, parking="propio", uf=4600),
        P("HT-1405", """La Reina, casa 4D. Doscientos millones. Metro a 600 m. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["cifra_palabras"],
          note="$200.000.000 en palabras > tope",
          expect=[B], loc="La Reina", beds=4, dist=600, pets=ANY, parking="propio",
          clp=200_000_000),
        P("HT-1406", """La Reina, 3D. UF 4.400. A 1,2 km del metro. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["dist_formato"],
          note="1,2 km > 900",
          expect=[D], loc="La Reina", beds=3, dist=1200, pets=ANY, parking="propio", uf=4400),
        P("HT-1407", """La Reina 2D. UF 4.200. Metro a 500 m. Admite mascotas. Estacionamiento
           comunitario sin asignar, por orden de llegada.""",
          tags=["estac_ambiguo"],
          note="sin asignar = no es propio ni asignado",
          expect=[E], loc="La Reina", beds=2, dist=500, pets=ANY, parking="ninguno", uf=4200),
        P("HT-1408", """La Reina, 3D. UF 4.500. Metro a 300 m. Con estacionamiento propio. Ideal para
           familias con niños.""",
          tags=["mascota_silencio"],
          note="no habla de mascotas",
          expect=[M], loc="La Reina", beds=3, dist=300, pets=NONE_, parking="propio", uf=4500),
    ]),

    # ------------------------------------------------------------------ 15 --
    case("ht_15", 39_350, hc(140_000_000, "gato", 6, 1200, 2, estacionamiento=False),
         ["Recoleta"], "Estacionamiento no requerido; gatos con condiciones.", [
        P("HT-1501", """Recoleta, 2D/1B. $128.000.000. Metro Patronato a 700 m. Se aceptan gatos.
           Sin estacionamiento. Arriendo $600.000.""",
          tags=["estac_ambiguo"],
          note="sin estacionamiento pero no se requiere",
          expect=[], loc="Recoleta", beds=2, dist=700, pets=only("gato"), parking="ninguno",
          clp=128_000_000, rent=600_000),
        P("HT-1502", """Barrio Bellavista (Recoleta): 2 dormitorios, UF 3.400, metro Baquedano a
           1.100 m, mascotas permitidas, arriendo 17 UF.""",
          tags=["comuna_posicion", "arriendo_uf"],
          note="comuna entre paréntesis; arriendo 17 UF",
          expect=[], loc="Recoleta", beds=2, dist=1100, pets=ANY, parking="ninguno",
          uf=3400, rent=rent_uf(17, 39_350)),
        P("HT-1503", """Independencia | 3D | $125.000.000 | metro Cementerios 600 m | gatos OK |
           arriendo $750.000""",
          tags=["estilo"],
          note="no preferida, mayor ROI",
          expect=[], loc="Independencia", beds=3, dist=600, pets=only("gato"), parking="ninguno",
          clp=125_000_000, rent=750_000),
        P("HT-1504", """Recoleta. Departamento de dos dormitorios. Valor 3.500 UF. A 1,2 km del metro
           Einstein. Admite gatos de hasta 6 kg.""",
          tags=["casi_cumple", "dist_formato", "mascota_condicion"],
          note="6 kg == 6 kg y 1,2 km == máximo: cumple; UF 3.500 = $137.725.000",
          expect=[], loc="Recoleta", beds=2, dist=1200, pets=only("gato", 6), parking="ninguno",
          uf=3500),
        P("HT-1505", """Recoleta, 2D. $115.000.000. Metro a 400 m. Perros sí; gatos, consultar.""",
          tags=["mascota_condicion", "mascota_silencio"],
          note="para gatos solo 'consultar': no hay aceptación explícita",
          expect=[M], loc="Recoleta", beds=2, dist=400, pets=only("perro"), parking="ninguno",
          clp=115_000_000),
        P("HT-1506", """Estudio de 28 m² en Recoleta. $80.000.000. Metro a 300 m. Gatos sí.""",
          tags=["dorm_no_cuenta"],
          note="estudio = 0 dormitorios",
          expect=[R], loc="Recoleta", beds=0, dist=300, pets=only("gato"), parking="ninguno",
          clp=80_000_000),
        P("HT-1507", """Recoleta 3D. Precio: 3.580 UF. Metro a 500 m. Gatos sí.""",
          tags=["casi_cumple"],
          note="near miss: 3.580 UF = $140.873.000",
          expect=[B], loc="Recoleta", beds=3, dist=500, pets=only("gato"), parking="ninguno",
          uf=3580),
        P("HT-1508", """Recoleta 2D. $110.000.000. El metro está 'a la vuelta' (2 cuadras). Gatos
           sí.""",
          tags=["dist_formato", "distractor"],
          note="'a la vuelta' / cuadras: no verificable",
          expect=[D], loc="Recoleta", beds=2, dist=None, pets=only("gato"), parking="ninguno",
          clp=110_000_000),
    ]),

    # ------------------------------------------------------------------ 16 --
    case("ht_16", 40_900, hc(240_000_000, None, None, 1000, 3), ["Lo Barnechea", "Vitacura"],
         "Comprador sin mascota; casas grandes.", [
        P("HT-1601", """Lo Barnechea, casa 4D/3B, 180 m². UF 5.800. Paradero troncal a 600 m. No se
           permiten mascotas. 2 estacionamientos.""",
          tags=["mascota_condicion", "casi_cumple"],
          note="UF 5.800 = $237.220.000; la prohibición no afecta",
          expect=[], loc="Lo Barnechea", beds=4, dist=600, pets=NO, parking="propio", uf=5800),
        P("HT-1602", """Vitacura: 3 dormitorios, 2 baños, UF 5.600, metro Escuela Militar a 950 m,
           estacionamiento propio, arriendo 45 UF.""",
          tags=["arriendo_uf", "comuna_posicion"],
          note="arriendo 45 UF",
          expect=[], loc="Vitacura", beds=3, dist=950, pets=NONE_, parking="propio",
          uf=5600, rent=rent_uf(45, 40_900)),
        P("HT-1603", """Las Condes, 3D/2B, $210.000.000, metro Manquehue a 400 m, estacionamiento
           asignado, renta 1,6 millones.""",
          tags=["jerga_monto"],
          note="'1,6 millones' = $1.600.000; no preferida",
          expect=[], loc="Las Condes", beds=3, dist=400, pets=NONE_, parking="asignado",
          clp=210_000_000, rent=1_600_000),
        P("HT-1604", """En La Dehesa, Lo Barnechea: casa de cuatro dormitorios, doscientos treinta y
           cinco millones, a ochocientos metros del paradero troncal, estacionamiento propio para
           dos autos.""",
          tags=["cifra_palabras", "comuna_posicion"],
          note="'en La Dehesa' (barrio) antes de la comuna; todo en palabras",
          expect=[], loc="Lo Barnechea", beds=4, dist=800, pets=NONE_, parking="propio",
          clp=235_000_000),
        P("HT-1605", """Vitacura, 4D. UF 5.900. Metro a 500 m. Con estacionamiento propio.""",
          tags=["casi_cumple"],
          note="near miss: UF 5.900 = $241.310.000",
          expect=[B], loc="Vitacura", beds=4, dist=500, pets=NONE_, parking="propio", uf=5900),
        P("HT-1606", """Vitacura, 2D + sala de estar familiar. UF 5.000. Metro a 300 m. Con
           estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="la sala de estar no es dormitorio",
          expect=[R], loc="Vitacura", beds=2, dist=300, pets=NONE_, parking="propio", uf=5000),
        P("HT-1607", """Vitacura, 3D. UF 5.200. Metro a 700 m. Estacionamiento: el edificio tiene 4
           para visitas.""",
          tags=["estac_ambiguo"],
          note="solo visitas",
          expect=[E], loc="Vitacura", beds=3, dist=700, pets=NONE_, parking="visitas", uf=5200),
        P("HT-1608", """Lo Barnechea, 3D. UF 5.400. Metro más cercano a 4,5 km. Con estacionamiento
           propio.""",
          tags=["dist_formato"],
          note="4,5 km > 1.000 m",
          expect=[D], loc="Lo Barnechea", beds=3, dist=4500, pets=NONE_, parking="propio",
          uf=5400),
    ]),

    # ------------------------------------------------------------------ 17 --
    case("ht_17", 38_950, hc(132_000_000, "perro", 15, 900, 2), ["Quinta Normal"],
         "Política de mascotas corregida; unidades del mismo edificio.", [
        P("HT-1701", """Quinta Normal, 2D/1B, UF 3.300, metro Gruta de Lourdes a 450 m, se aceptan
           perros de hasta 15 kilos, estacionamiento propio, arriendo $580.000.""",
          tags=["casi_cumple", "mascota_condicion"],
          note="15 kg == 15 kg: cumple; UF 3.300 = $128.535.000",
          expect=[], loc="Quinta Normal", beds=2, dist=450, pets=only("perro", 15),
          parking="propio", uf=3300, rent=580_000),
        P("HT-1702", """Lo Prado: 3 dormitorios; $120.000.000; metro Blanqueado 300 m; mascotas
           permitidas; estacionamiento asignado; arriendo $700.000.""",
          tags=[],
          note="no preferida, mayor ROI",
          expect=[], loc="Lo Prado", beds=3, dist=300, pets=ANY, parking="asignado",
          clp=120_000_000, rent=700_000),
        P("HT-1703", """Quinta Normal, 2D. $125.000.000. Metro a 600 m. Con estacionamiento propio.
           Nota: la publicación anterior decía "no mascotas"; el reglamento vigente sí las
           permite.""",
          tags=["correccion"],
          note="vale el reglamento vigente: acepta mascotas",
          expect=[], loc="Quinta Normal", beds=2, dist=600, pets=ANY, parking="propio",
          clp=125_000_000),
        P("HT-1704", """Quinta Normal, 3D. UF 3.100. Metro a 300 m. Gatos sí; perros, no. Con
           estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="solo gatos; comprador con perro",
          expect=[M], loc="Quinta Normal", beds=3, dist=300, pets=only("gato"), parking="propio",
          uf=3100),
        P("HT-1705", """Quinta Normal 2D, 135 palos, metro a 500 m, admite mascotas, con
           estacionamiento propio.""",
          tags=["jerga_monto", "casi_cumple"],
          note="'135 palos' = $135.000.000 > $132.000.000",
          expect=[B], loc="Quinta Normal", beds=2, dist=500, pets=ANY, parking="propio",
          clp=135_000_000),
        P("HT-1706", """Quinta Normal 2D. UF 3.000. Metro a 1.200 m y paradero troncal a 1.000 m.
           Admite mascotas. Con estacionamiento propio.""",
          tags=["dist_multiple"],
          note="la menor (1.000 m) igual supera 900",
          expect=[D], loc="Quinta Normal", beds=2, dist=1000, pets=ANY, parking="propio",
          uf=3000),
        P("HT-1707", """Quinta Normal 2D. UF 3.200. Metro a 400 m. Admite mascotas. Estacionamiento
           de uso común (no asignado).""",
          tags=["estac_ambiguo"],
          note="de uso común no asignado = no sirve",
          expect=[E], loc="Quinta Normal", beds=2, dist=400, pets=ANY, parking="ninguno",
          uf=3200),
        P("HT-1708", """Quinta Normal. El edificio ofrece unidades de 1, 2 y 3 dormitorios; la que se
           vende es de 1 dormitorio. UF 2.700. Metro a 500 m. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["distractor"],
          note="los 2 y 3 dormitorios son de otras unidades",
          expect=[R], loc="Quinta Normal", beds=1, dist=500, pets=ANY, parking="propio",
          uf=2700),
    ]),

    # ------------------------------------------------------------------ 18 --
    case("ht_18", 41_000, hc(165_000_000, "gato", 5, 800, 2), ["Providencia"],
         "Providencia: barrios, bodegas y gastos comunes.", [
        P("HT-1801", """Providencia, barrio Italia. 2D/2B. UF 3.950. Metro Santa Isabel a 650 m.
           Gatos permitidos. Con estacionamiento propio. Arriendo 20 UF.""",
          tags=["arriendo_uf"],
          note="arriendo 20 UF; UF 3.950 = $161.950.000",
          expect=[], loc="Providencia", beds=2, dist=650, pets=only("gato"), parking="propio",
          uf=3950, rent=rent_uf(20, 41_000)),
        P("HT-1802", """Depto en calle Condell, comuna de Providencia, 2 dormitorios, $164.000.000,
           metro Parque Bustamante a 300 m, acepta mascotas, estac. asignado.""",
          tags=["comuna_posicion", "casi_cumple"],
          note="'en calle Condell' antes de la comuna; $1.000.000 bajo el tope",
          expect=[], loc="Providencia", beds=2, dist=300, pets=ANY, parking="asignado",
          clp=164_000_000),
        P("HT-1803", """Santiago (barrio Lastarria): 2D/1B, UF 3.600, metro Bellas Artes a 200 m,
           admite mascotas, estacionamiento propio, arriendo $900.000.""",
          tags=["comuna_posicion"],
          note="no preferida, mayor ROI",
          expect=[], loc="Santiago", beds=2, dist=200, pets=ANY, parking="propio",
          uf=3600, rent=900_000),
        P("HT-1804", """Providencia, 3D. Precio de venta UF 3.990; bodega opcional UF 80; GC
           $140.000. Metro Manuel Montt a 700 m. Mascotas permitidas. Con estacionamiento
           propio.""",
          tags=["multi_monto"],
          note="la bodega opcional y los GC no son el precio",
          expect=[], loc="Providencia", beds=3, dist=700, pets=ANY, parking="propio", uf=3990),
        P("HT-1805", """Providencia, 2D. UF 3.800. Metro a 400 m. Solo perros. Con estacionamiento
           propio.""",
          tags=["mascota_condicion"],
          note="solo perros; comprador con gato",
          expect=[M], loc="Providencia", beds=2, dist=400, pets=only("perro"), parking="propio",
          uf=3800),
        P("HT-1806", """Providencia, 2D. Ciento setenta millones. Metro a 500 m. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["cifra_palabras"],
          note="$170.000.000 en palabras > tope",
          expect=[B], loc="Providencia", beds=2, dist=500, pets=ANY, parking="propio",
          clp=170_000_000),
        P("HT-1807", """Providencia 2D. UF 3.700. A 850 m del metro. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["casi_cumple"],
          note="850 m > 800",
          expect=[D], loc="Providencia", beds=2, dist=850, pets=ANY, parking="propio", uf=3700),
        P("HT-1808", """Providencia, 2D. UF 3.600. Metro a 300 m. Gatos OK. Estacionamiento: no (se
           puede arrendar en el edificio de al lado).""",
          tags=["estac_ambiguo", "distractor"],
          note="no incluye estacionamiento",
          expect=[E], loc="Providencia", beds=2, dist=300, pets=only("gato"), parking="ninguno",
          uf=3600),
    ]),

    # ------------------------------------------------------------------ 19 --
    case("ht_19", 39_700, hc(180_000_000, "perro", 28, 1300, 3), ["Maipú"],
         "Perro grande; casas del sector poniente.", [
        P("HT-1901", """Maipú, casa 3D/2B. UF 4.300. Paradero troncal en Pajaritos a 1.300 m. Perros
           de cualquier tamaño. Estacionamiento para dos autos. Arriendo 22 UF.""",
          tags=["casi_cumple", "arriendo_uf"],
          note="1.300 m == máximo; arriendo 22 UF",
          expect=[], loc="Maipú", beds=3, dist=1300, pets=only("perro"), parking="propio",
          uf=4300, rent=rent_uf(22, 39_700)),
        P("HT-1902", """Cerrillos — 4 dorm — $165.000.000 — metro Cerrillos 900 m — mascotas OK —
           estac. propio — arriendo $1.000.000""",
          tags=["estilo"],
          note="no preferida, mayor ROI",
          expect=[], loc="Cerrillos", beds=4, dist=900, pets=ANY, parking="propio",
          clp=165_000_000, rent=1_000_000),
        P("HT-1903", """Ciudad Satélite, Maipú. Casa de tres dormitorios y patio; valor 4.400 UF; a
           1,2 km del metro; se aceptan perros grandes; estacionamiento propio.""",
          tags=["comuna_posicion", "cifra_palabras", "dist_formato"],
          note="el barrio va antes de la comuna; UF 4.400 = $174.680.000",
          expect=[], loc="Maipú", beds=3, dist=1200, pets=only("perro"), parking="propio",
          uf=4400),
        P("HT-1904", """Maipú, 3D. UF 4.000. Metro a 600 m. Perros hasta 25 kg. Con estacionamiento
           propio.""",
          tags=["mascota_condicion"],
          note="25 kg contra perro de 28",
          expect=[M], loc="Maipú", beds=3, dist=600, pets=only("perro", 25), parking="propio",
          uf=4000),
        P("HT-1905", """Maipú, 4D. $183.000.000 (gastos operacionales aparte). Metro a 500 m. Admite
           mascotas. Con estacionamiento propio.""",
          tags=["multi_monto"],
          note="el precio solo ya supera el tope",
          expect=[B], loc="Maipú", beds=4, dist=500, pets=ANY, parking="propio",
          clp=183_000_000),
        P("HT-1906", """Maipú, 2D + pieza de servicio. UF 3.800. Metro a 700 m. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="servicio no cuenta: 2 < 3",
          expect=[R], loc="Maipú", beds=2, dist=700, pets=ANY, parking="propio", uf=3800),
        P("HT-1907", """Maipú 3D. UF 4.100. A 20 cuadras del metro. Admite mascotas. Con
           estacionamiento propio.""",
          tags=["dist_formato"],
          note="cuadras: no verificable",
          expect=[D], loc="Maipú", beds=3, dist=None, pets=ANY, parking="propio", uf=4100),
        P("HT-1908", """Maipú, 3D. UF 4.200. Metro a 500 m. Con estacionamiento propio. Antejardín y
           patio trasero.""",
          tags=["mascota_silencio"],
          note="un patio no es permiso de mascotas",
          expect=[M], loc="Maipú", beds=3, dist=500, pets=NONE_, parking="propio", uf=4200),
    ]),

    # ------------------------------------------------------------------ 20 --
    case("ht_20", 40_200, hc(125_000_000, None, None, 1000, 1, estacionamiento=False),
         ["Santiago"], "Comprador sin mascota ni auto; centro.", [
        P("HT-2001", """Santiago, 1D/1B, 33 m², UF 2.900, metro La Moneda a 150 m, no se aceptan
           mascotas, sin estacionamiento, arriendo 12 UF.""",
          tags=["arriendo_uf", "mascota_condicion"],
          note="prohíbe mascotas y no tiene estacionamiento: nada de eso aplica",
          expect=[], loc="Santiago", beds=1, dist=150, pets=NO, parking="ninguno",
          uf=2900, rent=rent_uf(12, 40_200)),
        P("HT-2002", """SANTIAGO CENTRO — 2 DORMITORIOS — 118 MILLONES — METRO SANTA ANA 400 M —
           ARRIENDO 520 MIL""",
          tags=["estilo", "jerga_monto"],
          note="mayúsculas; '118 MILLONES', '520 MIL'",
          expect=[], loc="Santiago", beds=2, dist=400, pets=NONE_, parking="ninguno",
          clp=118_000_000, rent=520_000),
        P("HT-2003", """Estación Central: 1D, $95.000.000, metro Estación Central 500 m, arriendo
           $500.000.""",
          tags=[],
          note="no preferida, mayor ROI",
          expect=[], loc="Estación Central", beds=1, dist=500, pets=NONE_, parking="ninguno",
          clp=95_000_000, rent=500_000),
        P("HT-2004", """Depto 1 dormitorio, calle San Diego, Santiago; precio rebajado de $130.000.000
           a $123.000.000; metro Franklin a 900 m.""",
          tags=["correccion", "comuna_posicion"],
          note="vale el precio rebajado",
          expect=[], loc="Santiago", beds=1, dist=900, pets=NONE_, parking="ninguno",
          clp=123_000_000),
        P("HT-2005", """Santiago, 2D. UF 3.120. Metro a 300 m.""",
          tags=["casi_cumple"],
          note="near miss: UF 3.120 = $125.424.000",
          expect=[B], loc="Santiago", beds=2, dist=300, pets=NONE_, parking="ninguno", uf=3120),
        P("HT-2006", """Santiago, estudio de 26 m². $70.000.000. Metro a 200 m.""",
          tags=["dorm_no_cuenta"],
          note="estudio = 0 < 1",
          expect=[R], loc="Santiago", beds=0, dist=200, pets=NONE_, parking="ninguno",
          clp=70_000_000),
        P("HT-2007", """Santiago, 1D. $100.000.000. Metro a 1,4 km.""",
          tags=["dist_formato"],
          note="1,4 km > 1.000",
          expect=[D], loc="Santiago", beds=1, dist=1400, pets=NONE_, parking="ninguno",
          clp=100_000_000),
        P("HT-2008", """Santiago, 2D. Ciento treinta y dos millones. Metro a 400 m.""",
          tags=["cifra_palabras"],
          note="$132.000.000 en palabras > tope",
          expect=[B], loc="Santiago", beds=2, dist=400, pets=NONE_, parking="ninguno",
          clp=132_000_000),
    ]),
]
