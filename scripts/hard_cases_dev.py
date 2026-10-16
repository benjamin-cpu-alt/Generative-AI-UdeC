"""hard_dev: 10 casos x 7 avisos escritos a mano. Se usa para AJUSTAR la E3.

Mismos fenómenos que hard_test con otras redacciones (build_hard.py comprueba que no
compartan fragmentos de 8 palabras). Convenciones: data/cases/hard_test/README.md.
"""
from hard_common import (ANY, B, D, E, M, NO, NONE_, P, R, both, case, hc, kg, only,  # noqa: F401
                         rent_uf)

CASES = [

    # ------------------------------------------------------------------ 01 --
    case("hd_01", 39_800, hc(160_000_000, "perro", 15, 900, 2), ["Ñuñoa"],
         "Mezcla de fichas de portal y mensajes de corredor.", [
        P("HD-0101", """Ñuñoa, sector Plaza Egaña. Depto 2D 2B de 71 m2. Valor UF 3.950. El
           Metro Plaza Egaña queda a 600 metros. Mascotas bienvenidas. Incluye 1
           estacionamiento y bodega. Arriendo estimado: 22 UF mensuales.""",
          tags=["dorm_notacion", "arriendo_uf", "comuna_posicion"],
          note="'2D 2B' sin barra; arriendo en UF (22 x 39.800); la comuna abre el aviso sin 'en'",
          expect=[], loc="Ñuñoa", beds=2, dist=600, pets=ANY, parking="propio",
          uf=3950, rent=rent_uf(22, 39_800)),
        P("HD-0102", """Departamento en Macul con 1 dormitorio y un escritorio habilitable como
           segundo dormitorio. UF 3.400. A 300 m del Metro Camino Agrícola. Se aceptan perros.
           Estacionamiento asignado.""",
          tags=["dorm_no_cuenta"],
          note="el escritorio 'habilitable' no es dormitorio: 1 < 2",
          expect=[R], loc="Macul", beds=1, dist=300, pets=only("perro"), parking="asignado",
          uf=3400),
        P("HD-0103", """Ñuñoa. Departamento 3D/2B, 84 m². Precio UF 4.025, gastos comunes
           $95.000. A 500 metros del Metro Irarrázaval. Pet friendly. Estacionamiento propio.""",
          tags=["casi_cumple", "multi_monto"],
          note="near miss: UF 4.025 = $160.195.000, sobre el tope por $195.000; GC no es el precio",
          expect=[B], loc="Ñuñoa", beds=3, dist=500, pets=ANY, parking="propio", uf=4025),
        P("HD-0104", """Providencia — 2 dormitorios, 1 baño — $149.000.000 — metro Inés de Suárez a
           1,2 km, pero paradero troncal a 250 m — mascotas hasta 15 kg — estacionamiento propio —
           arriendo $760.000.""",
          tags=["dist_multiple", "dist_formato", "casi_cumple", "mascota_condicion"],
          note="vale el paradero (250 m), no el metro en km; límite 15 kg == perro de 15 kg: cumple",
          expect=[], loc="Providencia", beds=2, dist=250, pets=kg(15), parking="propio",
          clp=149_000_000, rent=760_000),
        P("HD-0105", """Depto en Ñuñoa 2D/1B, 58 m². UF 3.600. A 450 m del Metro Ñuble. Acepta
           perros. Estacionamiento opcional, en venta aparte por UF 250. Arriendo actual: 680
           lucas.""",
          tags=["estac_ambiguo", "jerga_monto", "multi_monto"],
          note="el estacionamiento se vende aparte: la unidad no lo incluye; '680 lucas' = $680.000",
          expect=[E], loc="Ñuñoa", beds=2, dist=450, pets=only("perro"), parking="ninguno",
          uf=3600, rent=680_000),
        P("HD-0106", """wena! te paso uno en san miguel, 3 dorm 2 baños, 135 palos, a 700 mts del
           metro el llano, aceptan mascotas sin drama, tiene estacionamiento propio. lo
           arriendan en 720 lucas""",
          tags=["estilo", "jerga_monto"],
          note="WhatsApp: '135 palos' = $135.000.000 y '720 lucas' = $720.000; sin mayúsculas",
          expect=[], loc="San Miguel", beds=3, dist=700, pets=ANY, parking="propio",
          clp=135_000_000, rent=720_000),
        P("HD-0107", """Departamento en Ñuñoa, 2D/2B, 66 m². Valor UF 3.700. A 350 metros del Metro
           Villa Frei. Estacionamiento propio. Consultar reglamento por mascotas.""",
          tags=["mascota_silencio"],
          note="'consultar reglamento' no es una aceptación explícita",
          expect=[M], loc="Ñuñoa", beds=2, dist=350, pets=NONE_, parking="propio", uf=3700),
    ]),

    # ------------------------------------------------------------------ 02 --
    case("hd_02", 40_150, hc(210_000_000, None, None, 1000, 3), ["Las Condes", "Vitacura"],
         "Comprador SIN mascota: una prohibición de mascotas no lo descalifica.", [
        P("HD-0201", """Casa 3D+E en Vitacura, 140 m² construidos. Valor 5.150 UF. Paradero
           troncal a 800 m. Estacionamiento para 2 autos.""",
          tags=["dorm_notacion"],
          note="'3D+E' = 3 dormitorios + escritorio: 3 cumple; sin arriendo (ROI null)",
          expect=[], loc="Vitacura", beds=3, dist=800, pets=NONE_, parking="propio", uf=5150),
        P("HD-0202", """Departamento en Las Condes, 3 dormitorios y 2 baños. $198.000.000. A 650 m
           del Metro Manquehue. No se aceptan mascotas. Estacionamiento asignado. Arriendo
           $1.150.000.""",
          tags=["mascota_condicion"],
          note="prohíbe mascotas, pero el comprador no tiene: se aprueba",
          expect=[], loc="Las Condes", beds=3, dist=650, pets=NO, parking="asignado",
          clp=198_000_000, rent=1_150_000),
        P("HD-0203", """Las Condes, depto de 2 dormitorios más pieza de servicio con baño. UF 4.900.
           A 500 m del metro. Estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="la pieza de servicio no cuenta: 2 < 3",
          expect=[R], loc="Las Condes", beds=2, dist=500, pets=NONE_, parking="propio", uf=4900),
        P("HD-0204", """Departamento 4D/3B en Las Condes, 120 m². UF 5.000. A 10 minutos caminando
           del Metro Los Dominicos. Estacionamiento propio.""",
          tags=["dist_formato"],
          note="distancia solo en minutos: no verificable",
          expect=[D], loc="Las Condes", beds=4, dist=None, pets=NONE_, parking="propio", uf=5000),
        P("HD-0205", """Departamento en Ñuñoa de 3 dormitorios. Precio: doscientos cinco millones de
           pesos. A 900 metros del metro. Estacionamiento propio.""",
          tags=["cifra_palabras"],
          note="precio solo en palabras ($205.000.000)",
          expect=[], loc="Ñuñoa", beds=3, dist=900, pets=NONE_, parking="propio",
          clp=205_000_000),
        P("HD-0206", """Providencia, 3D/2B, 95 m². Precio rebajado: antes UF 5.600, ahora UF 5.200.
           A 400 m del Metro Los Leones. Estacionamiento asignado. Arriendo $1.050.000.""",
          tags=["correccion"],
          note="vale el precio final (UF 5.200 = $208.780.000), no el anterior",
          expect=[], loc="Providencia", beds=3, dist=400, pets=NONE_, parking="asignado",
          uf=5200, rent=1_050_000),
        P("HD-0207", """Vitacura. Depto 3D/2B, 98 m². Valor $215 millones. Contribuciones $180.000
           trimestrales. A 700 metros del paradero troncal. Estacionamiento propio.""",
          tags=["jerga_monto", "multi_monto"],
          note="'$215 millones' sobre el tope; las contribuciones no son el precio",
          expect=[B], loc="Vitacura", beds=3, dist=700, pets=NONE_, parking="propio",
          clp=215_000_000),
    ]),

    # ------------------------------------------------------------------ 03 --
    case("hd_03", 38_900, hc(140_000_000, "gato", 4, 800, 2, estacionamiento=False), ["Santiago"],
         "Estacionamiento NO requerido: su ausencia no descalifica.", [
        P("HD-0301", """Santiago Centro, depto 2D/1B de 54 m². UF 3.300. A 200 m del Metro Santa
           Lucía. Se aceptan gatos. Sin estacionamiento. Arriendo $560.000.""",
          tags=["estac_ambiguo"],
          note="sin estacionamiento, pero el comprador no lo requiere: se aprueba",
          expect=[], loc="Santiago", beds=2, dist=200, pets=only("gato"), parking="ninguno",
          uf=3300, rent=560_000),
        P("HD-0302", """Departamento en Santiago, 2 dormitorios. $129.000.000. A 300 metros del
           metro. Solo se permiten perros pequeños. Estacionamiento de visitas.""",
          tags=["mascota_condicion"],
          note="solo perros; el comprador tiene gato",
          expect=[M], loc="Santiago", beds=2, dist=300, pets=only("perro"), parking="visitas",
          clp=129_000_000),
        P("HD-0303", """Independencia: 2 habitaciones, 1 baño. UF 3.450. A 0,7 km del Metro
           Hospitales. Gatos sí, perros no. Arriendo 15 UF.""",
          tags=["mascota_condicion", "dist_formato", "dorm_notacion", "arriendo_uf"],
          note="'gatos sí, perros no' = solo gatos; 0,7 km = 700 m; arriendo 15 UF",
          expect=[], loc="Independencia", beds=2, dist=700, pets=only("gato"), parking="ninguno",
          uf=3450, rent=rent_uf(15, 38_900)),
        P("HD-0304", """Santiago, 3D/2B, 70 m². $138.500.000. A 820 metros del Metro Parque
           Almagro. Pet friendly.""",
          tags=["casi_cumple"],
          note="near miss: 820 m contra un máximo de 800",
          expect=[D], loc="Santiago", beds=3, dist=820, pets=ANY, parking="ninguno",
          clp=138_500_000),
        P("HD-0305", """Monoambiente tipo estudio de 32 m² en Santiago. UF 2.100. A 150 m del metro.
           Pet friendly.""",
          tags=["dorm_no_cuenta"],
          note="estudio = 0 dormitorios",
          expect=[R], loc="Santiago", beds=0, dist=150, pets=ANY, parking="ninguno", uf=2100),
        P("HD-0306", """Depto 2D/2B, 60 m², metro Cumming a 400 m, UF 3.550, acepta mascotas (máx.
           10 kg), est. asignado — Santiago.""",
          tags=["comuna_posicion"],
          note="la comuna va al final, tras un guion",
          expect=[], loc="Santiago", beds=2, dist=400, pets=kg(10), parking="asignado", uf=3550),
        P("HD-0307", """El depto del piso de arriba, de 3D, se vendió en UF 3.900. Este, en
           Santiago, es de 1 dormitorio: UF 2.950, a 500 m del metro, acepta gatos.""",
          tags=["distractor"],
          note="los 3D y el precio son de OTRA unidad; esta tiene 1 dormitorio",
          expect=[R], loc="Santiago", beds=1, dist=500, pets=only("gato"), parking="ninguno",
          uf=2950),
    ]),

    # ------------------------------------------------------------------ 04 --
    case("hd_04", 41_200, hc(175_000_000, "perro", 30, 1200, 2), ["La Florida", "Puente Alto"],
         "Mayúsculas, pie y saldo, kilos en palabras.", [
        P("HD-0401", """CASA LA FLORIDA 3D 2B, 4.200 UF, A 950 MTS METRO BELLAVISTA DE LA FLORIDA,
           ACEPTA MASCOTAS GRANDES, ESTACIONAMIENTO PARA 2 AUTOS. ARRIENDO $850.000""",
          tags=["estilo", "dorm_notacion"],
          note="todo en mayúsculas; 4.200 UF = $173.040.000",
          expect=[], loc="La Florida", beds=3, dist=950, pets=ANY, parking="propio",
          uf=4200, rent=850_000),
        P("HD-0402", """Casa en Puente Alto, 3 dormitorios. $120.000.000. Paradero troncal a 600
           m. Perros hasta 25 kilos. Estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="límite 25 kg contra perro de 30",
          expect=[M], loc="Puente Alto", beds=3, dist=600, pets=only("perro", 25),
          parking="propio", clp=120_000_000),
        P("HD-0403", """Puente Alto, 2D 1B. $110.000.000. A 4 cuadras del Metro Protectora de la
           Infancia. Acepta mascotas. Estacionamiento propio.""",
          tags=["dist_formato", "dorm_notacion"],
          note="'4 cuadras' no es una distancia verificable",
          expect=[D], loc="Puente Alto", beds=2, dist=None, pets=ANY, parking="propio",
          clp=110_000_000),
        P("HD-0404", """La Florida, 3D/2B, 80 m². UF 4.248. A 500 m del Metro Mirador. Pet
           friendly. Estacionamiento asignado.""",
          tags=["casi_cumple"],
          note="near miss: UF 4.248 = $175.017.600, sobre el tope por $17.600",
          expect=[B], loc="La Florida", beds=3, dist=500, pets=ANY, parking="asignado", uf=4248),
        P("HD-0405", """La Florida, depto 2D/2B. Precio total UF 3.900, con pie de UF 850 y saldo con
           crédito; GC $70.000. A 1,1 km del metro. Se aceptan perros. Estacionamiento propio.
           Arriendo 18 UF.""",
          tags=["multi_monto", "dist_formato", "arriendo_uf"],
          note="el pie y los GC no son el precio; 1,1 km = 1.100 m <= 1.200",
          expect=[], loc="La Florida", beds=2, dist=1100, pets=only("perro"), parking="propio",
          uf=3900, rent=rent_uf(18, 41_200)),
        P("HD-0406", """Casa en Macul de cuatro dormitorios. Precio: ciento sesenta y nueve millones.
           A 300 metros del metro. Mascotas sin restricción. Estacionamiento techado propio.""",
          tags=["cifra_palabras"],
          note="dormitorios y precio en palabras ($169.000.000)",
          expect=[], loc="Macul", beds=4, dist=300, pets=ANY, parking="propio", clp=169_000_000),
        P("HD-0407", """La Florida, 3 dormitorios. $150.000.000. A 400 m del metro. Acepta mascotas.
           Se estaciona en la calle sin problema.""",
          tags=["estac_ambiguo"],
          note="estacionamiento en la calle no sirve",
          expect=[E], loc="La Florida", beds=3, dist=400, pets=ANY, parking="calle",
          clp=150_000_000),
    ]),

    # ------------------------------------------------------------------ 05 --
    case("hd_05", 39_400, hc(125_000_000, "gato", 6, 700, 1), ["Estación Central"],
         "Departamentos chicos; política de mascotas corregida.", [
        P("HD-0501", """Estación Central, 1D/1B de 38 m². UF 3.050. A 250 m del Metro Universidad de
           Santiago. Se permiten gatos (máximo dos). Estac. asignado. Arriendo $420 mil.""",
          tags=["jerga_monto"],
          note="'$420 mil' = $420.000; 'máximo dos' es cantidad, no peso",
          expect=[], loc="Estación Central", beds=1, dist=250, pets=only("gato"),
          parking="asignado", uf=3050, rent=420_000),
        P("HD-0502", """Depto en Estación Central, 2 dormitorios. UF 2.900. A 400 metros del metro.
           Mascotas: consultar con administración. Estacionamiento propio.""",
          tags=["mascota_silencio"],
          note="'consultar con administración' no es una aceptación",
          expect=[M], loc="Estación Central", beds=2, dist=400, pets=NONE_, parking="propio",
          uf=2900),
        P("HD-0503", """Estación Central, departamento de 1 dormitorio. $118.000.000. Está a
           seiscientos metros del Metro Ecuador. Pet friendly. Estacionamiento propio. Arriendo
           $450.000.""",
          tags=["cifra_palabras"],
          note="distancia en palabras (600 m)",
          expect=[], loc="Estación Central", beds=1, dist=600, pets=ANY, parking="propio",
          clp=118_000_000, rent=450_000),
        P("HD-0504", """Santiago, 2D/1B. UF 3.150. Metro a 900 m y paradero troncal a 650 m. Acepta
           gatos hasta 5 kg. Estacionamiento propio.""",
          tags=["dist_multiple", "mascota_condicion"],
          note="distancia OK por el paradero; falla el peso (5 kg contra gato de 6)",
          expect=[M], loc="Santiago", beds=2, dist=650, pets=only("gato", 5), parking="propio",
          uf=3150),
        P("HD-0505", """Depto 1D/1B 40 m² (Quinta Normal). UF 2.800. A 500 m del Metro Gruta de
           Lourdes. Acepta mascotas. Estacionamiento: no tiene.""",
          tags=["comuna_posicion"],
          note="comuna entre paréntesis; no tiene estacionamiento",
          expect=[E], loc="Quinta Normal", beds=1, dist=500, pets=ANY, parking="ninguno", uf=2800),
        P("HD-0506", """Estación Central, 2D/2B. UF 3.100. A 300 m del Metro Las Rejas.
           Estacionamiento propio. ACTUALIZACIÓN: la comunidad ahora sí acepta mascotas. Se
           arrienda en 14 UF.""",
          tags=["correccion", "arriendo_uf"],
          note="la política final es la de la actualización; arriendo en UF",
          expect=[], loc="Estación Central", beds=2, dist=300, pets=ANY, parking="propio",
          uf=3100, rent=rent_uf(14, 39_400)),
        P("HD-0507", """Estación Central, 1 dormitorio. UF 2.700. ¡A pasos del metro! Pet friendly.
           Estacionamiento propio.""",
          tags=["dist_formato", "distractor"],
          note="'a pasos' no es una distancia",
          expect=[D], loc="Estación Central", beds=1, dist=None, pets=ANY, parking="propio",
          uf=2700),
    ]),

    # ------------------------------------------------------------------ 06 --
    case("hd_06", 40_600, hc(190_000_000, "perro", 12, 1000, 2), ["Providencia"],
         "La comuna preferida debe ganarle al ROI.", [
        P("HD-0601", """Providencia, depto 2+1 (2 dormitorios + escritorio). UF 4.600. A 550 m del
           Metro Pedro de Valdivia. Perros hasta 15 kg. Estacionamiento propio. Arriendo
           $900.000.""",
          tags=["dorm_notacion", "dorm_no_cuenta"],
          note="'2+1': el +1 es escritorio, 2 dormitorios cumplen",
          expect=[], loc="Providencia", beds=2, dist=550, pets=only("perro", 15),
          parking="propio", uf=4600, rent=900_000),
        P("HD-0602", """Comuna: Ñuñoa | Dormitorios: 3 | Baños: 2 | Precio: $175.000.000 | Metro: 700
           m | Mascotas: sí | Estacionamiento: asignado | Arriendo: $1.100.000""",
          tags=["estilo"],
          note="ficha con barras; mayor ROI pero NO preferida: va después de las de Providencia",
          expect=[], loc="Ñuñoa", beds=3, dist=700, pets=ANY, parking="asignado",
          clp=175_000_000, rent=1_100_000),
        P("HD-0603", """Providencia, 2D/1B. UF 4.700. GC 120 lucas. A 350 m del metro. Pet friendly.
           Estacionamiento propio.""",
          tags=["casi_cumple", "multi_monto"],
          note="near miss: UF 4.700 = $190.820.000; los GC en 'lucas' no son el precio",
          expect=[B], loc="Providencia", beds=2, dist=350, pets=ANY, parking="propio", uf=4700),
        P("HD-0604", """Providencia, 3 dormitorios. UF 4.300. A 300 m del Metro Salvador. No se
           aceptan perros. Gatos bienvenidos. Estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="solo gatos; comprador con perro",
          expect=[M], loc="Providencia", beds=3, dist=300, pets=only("gato"), parking="propio",
          uf=4300),
        P("HD-0605", """Depto de dos dormitorios en Providencia, $182 millones. A 1 km del metro.
           Acepta mascotas. Derecho a uso de estacionamiento asignado.""",
          tags=["estac_ambiguo", "jerga_monto", "casi_cumple", "dist_formato"],
          note="1 km == máximo de 1.000 m: cumple; 'derecho a uso asignado' = asignado",
          expect=[], loc="Providencia", beds=2, dist=1000, pets=ANY, parking="asignado",
          clp=182_000_000),
        P("HD-0606", """En el mismo edificio se vende otra unidad 3D con estacionamiento a UF 4.900.
           Esta unidad en Providencia: 1D/1B, UF 3.800, sin estacionamiento, a 400 m del metro,
           pet friendly.""",
          tags=["distractor"],
          note="los 3D y el estacionamiento son de la otra unidad",
          expect=[R, E], loc="Providencia", beds=1, dist=400, pets=ANY, parking="ninguno",
          uf=3800),
        P("HD-0607", """Las Condes, 3D/2B. UF 4.400. A 1,5 km del metro. Pet friendly.
           Estacionamiento propio.""",
          tags=["dist_formato"],
          note="1,5 km = 1.500 m > 1.000",
          expect=[D], loc="Las Condes", beds=3, dist=1500, pets=ANY, parking="propio", uf=4400),
    ]),

    # ------------------------------------------------------------------ 07 --
    case("hd_07", 39_100, hc(150_000_000, "perro", 8, 900, 2), ["Maipú"],
         "Avisos telegráficos y loggias.", [
        P("HD-0701", """MAIPU. Casa 3D/2B. 3.700UF. Paradero troncal 300m. Mascotas OK. 2 estac. Arr.
           650.000""",
          tags=["estilo"],
          note="telegráfico, sin tildes; 3.700 UF = $144.670.000",
          expect=[], loc="Maipú", beds=3, dist=300, pets=ANY, parking="propio",
          uf=3700, rent=650_000),
        P("HD-0702", """Maipú, casa de 3 dormitorios. $139.000.000. A 600 m del Metro Plaza de Maipú.
           Perros de hasta cinco kilos. Estacionamiento propio.""",
          tags=["cifra_palabras", "mascota_condicion"],
          note="límite en palabras (5 kg) contra perro de 8",
          expect=[M], loc="Maipú", beds=3, dist=600, pets=only("perro", 5), parking="propio",
          clp=139_000_000),
        P("HD-0703", """Depto 3D 2B en Cerrillos. UF 3.800. A 850 metros del Metro Cerrillos. Acepta
           mascotas pequeñas de hasta 10 kg. Estac. propio. Arriendo 16,5 UF.""",
          tags=["dorm_notacion", "arriendo_uf"],
          note="arriendo con decimal en UF (16,5 x 39.100); 8 kg <= 10",
          expect=[], loc="Cerrillos", beds=3, dist=850, pets=kg(10), parking="propio",
          uf=3800, rent=rent_uf(16.5, 39_100)),
        P("HD-0704", """Maipú, 2 dormitorios. $128.000.000. A 500 m del metro. Pet friendly.
           Estacionamiento de visitas disponible.""",
          tags=["estac_ambiguo"],
          note="estacionamiento de visitas no sirve",
          expect=[E], loc="Maipú", beds=2, dist=500, pets=ANY, parking="visitas",
          clp=128_000_000),
        P("HD-0705", """Maipú, 2D/2B. Valor: UF 3.890 (incluye estacionamiento y bodega). A 400 m del
           metro. Perros bienvenidos.""",
          tags=["casi_cumple"],
          note="near miss: UF 3.890 = $152.099.000",
          expect=[B], loc="Maipú", beds=2, dist=400, pets=only("perro"), parking="propio",
          uf=3890),
        P("HD-0706", """Maipú, 1 dormitorio y una loggia que hoy se usa como dormitorio. UF 3.000. A
           300 m del metro. Acepta mascotas. Estacionamiento asignado.""",
          tags=["dorm_no_cuenta"],
          note="la loggia no es dormitorio",
          expect=[R], loc="Maipú", beds=1, dist=300, pets=ANY, parking="asignado", uf=3000),
        P("HD-0707", """Av. Pajaritos 3200, Maipú. Depto 2D/2B. UF 3.500. Metro Las Parcelas a 450 m.
           Mascotas permitidas sin límite de peso. Estacionamiento propio. Arriendo $600.000.""",
          tags=["comuna_posicion"],
          note="la comuna va en la dirección",
          expect=[], loc="Maipú", beds=2, dist=450, pets=ANY, parking="propio",
          uf=3500, rent=600_000),
    ]),

    # ------------------------------------------------------------------ 08 --
    case("hd_08", 40_900, hc(230_000_000, "gato", 3, 1500, 3, estacionamiento=False),
         ["La Reina", "Peñalolén"], "Casas grandes; estacionamiento no requerido.", [
        P("HD-0801", """Casa en La Reina, 4D/3B. UF 5.500. A 1,4 km del Metro Príncipe de Gales.
           Acepta gatos. Sin estacionamiento.""",
          tags=["dist_formato", "estac_ambiguo"],
          note="1,4 km <= 1.500; sin estacionamiento pero no se requiere",
          expect=[], loc="La Reina", beds=4, dist=1400, pets=only("gato"), parking="ninguno",
          uf=5500),
        P("HD-0802", """Peñalolén, casa de 3 dormitorios (uno en suite). $219 millones. Paradero
           troncal a 900 m. Mascotas según reglamento de copropiedad.""",
          tags=["mascota_silencio", "jerga_monto"],
          note="'según reglamento' no dice si acepta",
          expect=[M], loc="Peñalolén", beds=3, dist=900, pets=NONE_, parking="ninguno",
          clp=219_000_000),
        P("HD-0803", """Peñalolén: casa de tres dormitorios, valor cinco mil cuatrocientas UF, a mil
           metros del paradero troncal. Pet friendly. Estacionamiento de visitas.""",
          tags=["cifra_palabras"],
          note="precio y distancia en palabras: UF 5.400 = $220.860.000; 1.000 m",
          expect=[], loc="Peñalolén", beds=3, dist=1000, pets=ANY, parking="visitas", uf=5400),
        P("HD-0804", """Ñuñoa, 3D/2B, 110 m². UF 5.630. A 800 m del metro. Acepta gatos.""",
          tags=["casi_cumple"],
          note="near miss: UF 5.630 = $230.267.000",
          expect=[B], loc="Ñuñoa", beds=3, dist=800, pets=only("gato"), parking="ninguno",
          uf=5630),
        P("HD-0805", """La Reina, 2D + estudio. UF 4.800. A 700 m del metro. Acepta mascotas.""",
          tags=["dorm_no_cuenta", "dorm_notacion"],
          note="el estudio no es dormitorio: 2 < 3",
          expect=[R], loc="La Reina", beds=2, dist=700, pets=ANY, parking="ninguno", uf=4800),
        P("HD-0806", """Macul, casa 3D/2B. UF 5.100. A 600 m del metro. Gatos bienvenidos, perros no.
           Estacionamiento propio. Arriendo actual 30 UF.""",
          tags=["arriendo_uf", "mascota_condicion"],
          note="mayor ROI pero NO preferida; arriendo 30 UF",
          expect=[], loc="Macul", beds=3, dist=600, pets=only("gato"), parking="propio",
          uf=5100, rent=rent_uf(30, 40_900)),
        P("HD-0807", """La Reina, casa 3D. UF 5.000. 15 min caminando al metro. Acepta gatos.""",
          tags=["dist_formato"],
          note="solo minutos",
          expect=[D], loc="La Reina", beds=3, dist=None, pets=only("gato"), parking="ninguno",
          uf=5000),
    ]),

    # ------------------------------------------------------------------ 09 --
    case("hd_09", 41_050, hc(165_000_000, "perro", 22, 800, 2), ["San Miguel"],
         "Marketing engañoso y excepciones de mascotas.", [
        P("HD-0901", """¡Bajo el presupuesto de cualquier comprador! San Miguel, 2D/2B. UF 4.100. A
           400 m del metro. Pet friendly. Estacionamiento propio.""",
          tags=["distractor"],
          note="UF 4.100 = $168.305.000 > tope, diga lo que diga el aviso",
          expect=[B], loc="San Miguel", beds=2, dist=400, pets=ANY, parking="propio", uf=4100),
        P("HD-0902", """San Miguel, 2D/1B. UF 3.950. A 750 m del Metro San Miguel. Se aceptan
           perros grandes. Estacionamiento asignado. Arriendo $780.000.""",
          tags=[],
          note="control: cumple todo sin dificultad",
          expect=[], loc="San Miguel", beds=2, dist=750, pets=only("perro"), parking="asignado",
          uf=3950, rent=780_000),
        P("HD-0903", """San Miguel, 3 dormitorios. $150.000.000. A 500 m del metro. Se aceptan
           mascotas, excepto perros de más de 20 kg. Estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="la excepción limita perros a 20 kg; el del comprador pesa 22",
          expect=[M], loc="San Miguel", beds=3, dist=500, pets=only("perro", 20),
          parking="propio", clp=150_000_000),
        P("HD-0904", """San Joaquín, 2 dorm. UF 3.700. Metro Lo Vial a 1.100 m; paradero troncal de
           Gran Avenida a 350 m. Acepta mascotas. Estac. propio. Arriendo 700 lucas.""",
          tags=["dist_multiple", "jerga_monto"],
          note="vale el paradero (350 m); '700 lucas' = $700.000",
          expect=[], loc="San Joaquín", beds=2, dist=350, pets=ANY, parking="propio",
          uf=3700, rent=700_000),
        P("HD-0905", """San Miguel, 2D/2B. UF 3.600. A 450 m del metro. Pet friendly. El
           estacionamiento se vende por separado en UF 300.""",
          tags=["estac_ambiguo", "multi_monto"],
          note="estacionamiento aparte = la unidad no lo incluye",
          expect=[E], loc="San Miguel", beds=2, dist=450, pets=ANY, parking="ninguno", uf=3600),
        P("HD-0906", """La Cisterna, 3D/2B. Precio publicado UF 4.300 → rebajado a UF 3.990. A 600 m
           del metro. Mascotas permitidas. Estacionamiento propio. Arriendo $820.000.""",
          tags=["correccion"],
          note="vale el precio rebajado (UF 3.990 = $163.789.500)",
          expect=[], loc="La Cisterna", beds=3, dist=600, pets=ANY, parking="propio",
          uf=3990, rent=820_000),
        P("HD-0907", """San Miguel, un dormitorio. UF 3.100. A 300 m del metro. Pet friendly.
           Estacionamiento propio.""",
          tags=["cifra_palabras"],
          note="'un dormitorio' en palabras: 1 < 2",
          expect=[R], loc="San Miguel", beds=1, dist=300, pets=ANY, parking="propio", uf=3100),
    ]),

    # ------------------------------------------------------------------ 10 --
    case("hd_10", 38_650, hc(120_000_000, None, None, 1000, 2, estacionamiento=False),
         ["Recoleta", "Independencia"], "Comprador sin mascota ni auto.", [
        P("HD-1001", """Recoleta, 2D/1B. $115.000.000. A 500 m del Metro Cerro Blanco. No se
           permiten mascotas. Sin estacionamiento.""",
          tags=["mascota_condicion", "estac_ambiguo"],
          note="ni mascotas ni estacionamiento importan a este comprador: se aprueba",
          expect=[], loc="Recoleta", beds=2, dist=500, pets=NO, parking="ninguno",
          clp=115_000_000),
        P("HD-1002", """Independencia, 3D. UF 3.150. A 300 m del metro.""",
          tags=["casi_cumple"],
          note="near miss: UF 3.150 = $121.747.500",
          expect=[B], loc="Independencia", beds=3, dist=300, pets=NONE_, parking="ninguno",
          uf=3150),
        P("HD-1003", """Conchalí, 2 D / 1 B, 112 palos, a 900 m del metro, se estaciona en la
           calle.""",
          tags=["jerga_monto", "dorm_notacion"],
          note="'112 palos' = $112.000.000; '2 D / 1 B' con espacios",
          expect=[], loc="Conchalí", beds=2, dist=900, pets=NONE_, parking="calle",
          clp=112_000_000),
        P("HD-1004", """Recoleta, 2 dormitorios. $100.000.000. A 3 cuadras del metro.""",
          tags=["dist_formato"],
          note="cuadras: no verificable",
          expect=[D], loc="Recoleta", beds=2, dist=None, pets=NONE_, parking="ninguno",
          clp=100_000_000),
        P("HD-1005", """Independencia, 1 dormitorio + escritorio convertible. $95.000.000. A 400 m
           del metro.""",
          tags=["dorm_no_cuenta"],
          note="el escritorio convertible no cuenta: 1 < 2",
          expect=[R], loc="Independencia", beds=1, dist=400, pets=NONE_, parking="ninguno",
          clp=95_000_000),
        P("HD-1006", """Depto 2D/2B, 55 m2, metro Hospitales a 200 m, UF 3.000, arriendo 13 UF —
           Independencia.""",
          tags=["comuna_posicion", "arriendo_uf"],
          note="comuna al final; arriendo 13 UF",
          expect=[], loc="Independencia", beds=2, dist=200, pets=NONE_, parking="ninguno",
          uf=3000, rent=rent_uf(13, 38_650)),
        P("HD-1007", """Recoleta, 2 dormitorios. Ciento treinta millones. A 600 m del metro.""",
          tags=["cifra_palabras"],
          note="precio en palabras ($130.000.000) sobre el tope",
          expect=[B], loc="Recoleta", beds=2, dist=600, pets=NONE_, parking="ninguno",
          clp=130_000_000),
    ]),
]
