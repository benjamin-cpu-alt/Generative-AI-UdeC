"""hard_test, casos 01-10 (8 avisos cada uno). SOLO para medir: no se ajusta nada mirándolos.

Convenciones y cuotas: data/cases/hard_test/README.md.
"""
from hard_common import (ANY, B, D, E, M, NO, NONE_, P, R, both, case, hc, kg, only,  # noqa: F401
                         rent_uf)

CASES = [

    # ------------------------------------------------------------------ 01 --
    case("ht_01", 39_250, hc(155_000_000, "perro", 10, 800, 2), ["Ñuñoa"],
         "Fichas de portal con descripción libre.", [
        P("HT-0101", """Se vende departamento luminoso, piso 9, comuna de Ñuñoa. Tiene 2
           dormitorios y 2 baños completos. Valor de venta 3.880 UF (gastos comunes aprox.
           $110.000). Estación Ñuble de la Línea 5 a 550 metros. Reglamento: se permiten perros y
           gatos de hasta 12 kilos. Un estacionamiento en el subsuelo, propio. Rentabiliza en
           $830.000 al mes.""",
          tags=["multi_monto", "comuna_posicion"],
          note="'comuna de Ñuñoa' (no sigue a 'en'); UF 3.880 = $152.290.000; GC no es precio",
          expect=[], loc="Ñuñoa", beds=2, dist=550, pets=both(12), parking="propio",
          uf=3880, rent=830_000),
        P("HT-0102", """Macul | 3 dorm | UF 3.600 | 2 baños | metro Macul 400 m | perros OK |
           estacionamiento asignado | renta 900 lucas""",
          tags=["estilo", "jerga_monto"],
          note="ficha con barras; '900 lucas'; mayor ROI que HT-0101 pero no preferida",
          expect=[], loc="Macul", beds=3, dist=400, pets=only("perro"), parking="asignado",
          uf=3600, rent=900_000),
        P("HT-0103", """Ñuñoa, 2D/1B de 56 m². UF 3.950. Metro Monseñor Eyzaguirre a 300 metros.
           Acepta mascotas. Estacionamiento propio.""",
          tags=["casi_cumple"],
          note="near miss: UF 3.950 = $155.037.500, sobre el tope por $37.500",
          expect=[B], loc="Ñuñoa", beds=2, dist=300, pets=ANY, parking="propio", uf=3950),
        P("HT-0104", """Departamento de 3 dormitorios en Ñuñoa. UF 3.500. Metro a 600 m. Se admiten
           mascotas que no superen los 8 kilos. Estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="límite 8 kg contra perro de 10",
          expect=[M], loc="Ñuñoa", beds=3, dist=600, pets=kg(8), parking="propio", uf=3500),
        P("HT-0105", """Ñuñoa: 1 dormitorio y un home office con ventana. UF 3.200. Metro a 400 m. Admite mascotas. Estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="el home office no es dormitorio",
          expect=[R], loc="Ñuñoa", beds=1, dist=400, pets=ANY, parking="propio", uf=3200),
        P("HT-0106", """Departamento de 2 dormitorios, 1 baño, con estacionamiento asignado y bodega;
           acepta mascotas de cualquier tamaño; queda a ochocientos metros del Metro Grecia;
           valor UF 3.750. Peñalolén.""",
          tags=["cifra_palabras", "comuna_posicion", "casi_cumple"],
          note="distancia en palabras, justo en el máximo (800 <= 800); la comuna cierra el aviso",
          expect=[], loc="Peñalolén", beds=2, dist=800, pets=ANY, parking="asignado", uf=3750),
        P("HT-0107", """Ñuñoa, 2D/2B. UF 3.400. Paradero troncal a 200 m. Pet friendly.
           Estacionamiento: se puede arrendar uno en el edificio por $45.000.""",
          tags=["estac_ambiguo", "multi_monto"],
          note="el estacionamiento se arrienda aparte: la unidad no lo incluye",
          expect=[E], loc="Ñuñoa", beds=2, dist=200, pets=ANY, parking="ninguno", uf=3400),
        P("HT-0108", """Ñuñoa, depto 3D. UF 3.300. A 1,05 km del Metro Villa Frei. Acepta mascotas.
           Estacionamiento propio.""",
          tags=["dist_formato"],
          note="1,05 km = 1.050 m > 800",
          expect=[D], loc="Ñuñoa", beds=3, dist=1050, pets=ANY, parking="propio", uf=3300),
    ]),

    # ------------------------------------------------------------------ 02 --
    case("ht_02", 40_300, hc(185_000_000, None, None, 1000, 3), ["Providencia", "Las Condes"],
         "Comprador sin mascota.", [
        P("HT-0201", """Las Condes, depto 3D/2B, 102 m². UF 4.550. Metro Hernando de Magallanes a
           700 m. El edificio no admite mascotas de ningún tipo. Dos estacionamientos propios.
           Renta mensual 1,2 millones.""",
          tags=["mascota_condicion", "jerga_monto"],
          note="prohíbe mascotas pero el comprador no tiene; '1,2 millones' = $1.200.000",
          expect=[], loc="Las Condes", beds=3, dist=700, pets=NO, parking="propio",
          uf=4550, rent=1_200_000),
        P("HT-0202", """Providencia. Tres dormitorios (principal en suite), dos baños. $179.900.000.
           A 450 metros del metro Tobalaba. Estacionamiento asignado.""",
          tags=["cifra_palabras"],
          note="dormitorios en palabras; la suite cuenta",
          expect=[], loc="Providencia", beds=3, dist=450, pets=NONE_, parking="asignado",
          clp=179_900_000),
        P("HT-0203", """Providencia 2D+S (servicio). UF 4.300, metro a 300 m. Con estacionamiento
           propio.""",
          tags=["dorm_notacion", "dorm_no_cuenta"],
          note="'2D+S' = 2 dormitorios + servicio: 2 < 3",
          expect=[R], loc="Providencia", beds=2, dist=300, pets=NONE_, parking="propio", uf=4300),
        P("HT-0204", """Las Condes, 3 dormitorios. Ciento noventa millones de pesos. A 600 m del
           metro. Estacionamiento propio.""",
          tags=["cifra_palabras"],
          note="precio en palabras ($190.000.000) sobre el tope",
          expect=[B], loc="Las Condes", beds=3, dist=600, pets=NONE_, parking="propio",
          clp=190_000_000),
        P("HT-0205", """3D/2B en Ñuñoa. El vendedor menciona una tasación de UF 5.000, pero el precio
           de venta es $170.000.000. A 900 m del metro. Estacionamiento propio. Arriendo
           $1.300.000.""",
          tags=["distractor", "multi_monto"],
          note="la tasación no es el precio; mayor ROI y no preferida",
          expect=[], loc="Ñuñoa", beds=3, dist=900, pets=NONE_, parking="propio",
          clp=170_000_000, rent=1_300_000),
        P("HT-0206", """Las Condes, 4 dormitorios. UF 4.400. A 5 minutos del metro Escuela Militar.
           Estacionamiento propio.""",
          tags=["dist_formato"],
          note="minutos, sin metros",
          expect=[D], loc="Las Condes", beds=4, dist=None, pets=NONE_, parking="propio", uf=4400),
        P("HT-0207", """Providencia, 3D. UF 4.200. A 500 m del metro. Estacionamiento no incluido
           (hay disponibilidad para arriendo en el edificio).""",
          tags=["estac_ambiguo"],
          note="no incluido = ninguno",
          expect=[E], loc="Providencia", beds=3, dist=500, pets=NONE_, parking="ninguno", uf=4200),
        P("HT-0208", """Providencia, 3D/2B. UF 4.592. A 350 m del metro. Estacionamiento asignado.""",
          tags=["casi_cumple"],
          note="near miss: UF 4.592 = $185.057.600",
          expect=[B], loc="Providencia", beds=3, dist=350, pets=NONE_, parking="asignado",
          uf=4592),
    ]),

    # ------------------------------------------------------------------ 03 --
    case("ht_03", 38_700, hc(118_000_000, "gato", 5, 900, 1, estacionamiento=False), ["Santiago"],
         "Estacionamiento no requerido; unidades pequeñas.", [
        P("HT-0301", """Santiago centro. 1 dormitorio independiente, 35 m². $109.000.000. Metro
           Bellas Artes a 300 m. Se aceptan gatos. No tiene estacionamiento. Arriendo
           $430.000.""",
          tags=["estac_ambiguo"],
          note="sin estacionamiento, pero no se requiere",
          expect=[], loc="Santiago", beds=1, dist=300, pets=only("gato"), parking="ninguno",
          clp=109_000_000, rent=430_000),
        P("HT-0302", """Barrio Yungay, Santiago. Depto 2D/1B. UF 2.950. A 650 metros de metro
           Cumming. Mascotas bienvenidas (gatos y perros). Estacionamiento en la calle.
           Arriendo 13,5 UF.""",
          tags=["arriendo_uf", "estac_ambiguo"],
          note="arriendo 13,5 UF; calle no importa a este comprador",
          expect=[], loc="Santiago", beds=2, dist=650, pets=both(), parking="calle",
          uf=2950, rent=rent_uf(13.5, 38_700)),
        P("HT-0303", """Loft de 40 m² en Santiago, ambiente único con altillo. UF 2.600. Metro a 200
           m. Pet friendly.""",
          tags=["dorm_no_cuenta"],
          note="loft de ambiente único = 0 dormitorios",
          expect=[R], loc="Santiago", beds=0, dist=200, pets=ANY, parking="ninguno", uf=2600),
        P("HT-0304", """Santiago, 1D/1B. $105.000.000. A 400 m del metro. La comunidad solo autoriza
           perros.""",
          tags=["mascota_condicion"],
          note="solo perros; comprador con gato",
          expect=[M], loc="Santiago", beds=1, dist=400, pets=only("perro"), parking="ninguno",
          clp=105_000_000),
        P("HT-0305", """Independencia, 1D 1B, 98 palos, metro a 500 m, acepta gatos hasta 6 kg,
           arriendo 520 lucas""",
          tags=["jerga_monto", "dorm_notacion", "mascota_condicion"],
          note="'98 palos'/'520 lucas'; 5 <= 6 kg; no preferida y con más ROI",
          expect=[], loc="Independencia", beds=1, dist=500, pets=only("gato", 6),
          parking="ninguno", clp=98_000_000, rent=520_000),
        P("HT-0306", """Santiago, 2D. UF 2.800. A 1,3 km del metro. Acepta gatos.""",
          tags=["dist_formato"],
          note="1,3 km > 900 m",
          expect=[D], loc="Santiago", beds=2, dist=1300, pets=only("gato"), parking="ninguno",
          uf=2800),
        P("HT-0307", """Santiago, 2D/1B. UF 3.060. A 400 m del metro. Gatos permitidos.""",
          tags=["casi_cumple"],
          note="near miss: UF 3.060 = $118.422.000",
          expect=[B], loc="Santiago", beds=2, dist=400, pets=only("gato"), parking="ninguno",
          uf=3060),
        P("HT-0308", """Santiago, 1 dormitorio. $99.000.000. A 300 m del metro. Mascotas a convenir
           con el propietario.""",
          tags=["mascota_silencio"],
          note="'a convenir' no es aceptación explícita",
          expect=[M], loc="Santiago", beds=1, dist=300, pets=NONE_, parking="ninguno",
          clp=99_000_000),
    ]),

    # ------------------------------------------------------------------ 04 --
    case("ht_04", 41_100, hc(200_000_000, "perro", 25, 1200, 3), ["La Florida"],
         "Casas familiares; distancias dobles.", [
        P("HT-0401", """Casa en La Florida, 3 dormitorios + escritorio, 2 baños. 4.700 UF. Paradero
           troncal de Vicuña Mackenna a 900 m; el metro queda a 1,6 km. Perros sin límite de
           tamaño. Estacionamiento para 2 vehículos. Arriendo 25 UF.""",
          tags=["dist_multiple", "arriendo_uf", "dorm_notacion"],
          note="vale el paradero (900 m); 3 dormitorios (el escritorio no suma); arriendo 25 UF",
          expect=[], loc="La Florida", beds=3, dist=900, pets=only("perro"), parking="propio",
          uf=4700, rent=rent_uf(25, 41_100)),
        P("HT-0402", """La Florida, 2 dormitorios + mansarda de uso flexible. UF 4.000. Metro a 600 m. Admite mascotas. Estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="la mansarda no es dormitorio",
          expect=[R], loc="La Florida", beds=2, dist=600, pets=ANY, parking="propio", uf=4000),
        P("HT-0403", """PUENTE ALTO!! CASA 4D 2B, $165.000.000, METRO LAS MERCEDES 800 MTS, MASCOTAS
           SI, 2 ESTACIONAMIENTOS, ARRIENDO $1.050.000""",
          tags=["estilo"],
          note="mayúsculas; no preferida, mayor ROI",
          expect=[], loc="Puente Alto", beds=4, dist=800, pets=ANY, parking="propio",
          clp=165_000_000, rent=1_050_000),
        P("HT-0404", """La Florida, 3D. UF 4.500. A 700 m del metro. Se aceptan perros de hasta veinte
           kilos. Estacionamiento propio.""",
          tags=["cifra_palabras", "mascota_condicion"],
          note="límite en palabras (20 kg) contra perro de 25",
          expect=[M], loc="La Florida", beds=3, dist=700, pets=only("perro", 20),
          parking="propio", uf=4500),
        P("HT-0405", """Av. La Florida 9500, La Florida. 3D/2B. UF 4.850. A 1.200 m del Metro Elisa
           Correa. Mascotas OK. Estac. propio.""",
          tags=["comuna_posicion", "casi_cumple"],
          note="UF 4.850 = $199.335.000 y 1.200 m: ambos justo dentro del límite",
          expect=[], loc="La Florida", beds=3, dist=1200, pets=ANY, parking="propio", uf=4850),
        P("HT-0406", """La Florida, casa 3D. Valor $205.000.000 (acepta crédito; pie 20 %:
           $41.000.000). Metro a 500 m. Admite mascotas. Estacionamiento propio.""",
          tags=["multi_monto"],
          note="el precio es $205.000.000, no el pie",
          expect=[B], loc="La Florida", beds=3, dist=500, pets=ANY, parking="propio",
          clp=205_000_000),
        P("HT-0407", """La Florida, 3D. UF 4.300. Metro a 400 m. Admite mascotas. Acceso a
           estacionamientos de visita.""",
          tags=["estac_ambiguo"],
          note="visitas no sirve",
          expect=[E], loc="La Florida", beds=3, dist=400, pets=ANY, parking="visitas", uf=4300),
        P("HT-0408", """La Florida, 4D. UF 4.600. A seis cuadras del metro. Pet friendly.
           Estacionamiento propio.""",
          tags=["dist_formato"],
          note="cuadras: no verificable",
          expect=[D], loc="La Florida", beds=4, dist=None, pets=ANY, parking="propio", uf=4600),
    ]),

    # ------------------------------------------------------------------ 05 --
    case("ht_05", 39_900, hc(145_000_000, "gato", 4, 700, 2), ["San Miguel", "La Cisterna"],
         "Correcciones de precio y estacionamientos de cortesía.", [
        P("HT-0501", """San Miguel – depto 2D2B – UF 3.600 – metro Ciudad del Niño a 350 m – gatos
           permitidos – est. asignado – arriendo $700.000""",
          tags=["dorm_notacion"],
          note="'2D2B' sin separador; UF 3.600 = $143.640.000",
          expect=[], loc="San Miguel", beds=2, dist=350, pets=only("gato"), parking="asignado",
          uf=3600, rent=700_000),
        P("HT-0502", """La Cisterna: dos dormitorios, un baño; $138.000.000; paradero troncal a
           seiscientos cincuenta metros; mascotas: sí; estacionamiento propio.""",
          tags=["cifra_palabras"],
          note="distancia en palabras (650 m)",
          expect=[], loc="La Cisterna", beds=2, dist=650, pets=ANY, parking="propio",
          clp=138_000_000),
        P("HT-0503", """San Miguel, 2D. UF 3.300. A 500 m del metro. Perros sí, gatos no.
           Estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="solo perros; comprador con gato",
          expect=[M], loc="San Miguel", beds=2, dist=500, pets=only("perro"), parking="propio",
          uf=3300),
        P("HT-0504", """San Joaquín, 3D/2B. UF 3.400. Metro Rodrigo de Araya a 600 m. Pet friendly.
           Estacionamiento propio. Arriendo 21 UF.""",
          tags=["arriendo_uf"],
          note="arriendo 21 UF; no preferida, mayor ROI",
          expect=[], loc="San Joaquín", beds=3, dist=600, pets=ANY, parking="propio",
          uf=3400, rent=rent_uf(21, 39_900)),
        P("HT-0505", """San Miguel, 2D. $140.000.000. A 720 m del metro. Gatos aceptados.
           Estacionamiento propio.""",
          tags=["casi_cumple"],
          note="near miss: 720 m contra 700",
          expect=[D], loc="San Miguel", beds=2, dist=720, pets=only("gato"), parking="propio",
          clp=140_000_000),
        P("HT-0506", """San Miguel 2D/2B. Precio: UF 3.550. *Corrección: el precio correcto es UF
           3.690*. Metro a 400 m. Admite mascotas. Estacionamiento propio.""",
          tags=["correccion"],
          note="vale la corrección: UF 3.690 = $147.231.000 > tope",
          expect=[B], loc="San Miguel", beds=2, dist=400, pets=ANY, parking="propio", uf=3690),
        P("HT-0507", """La Cisterna, 1 dormitorio más sala de estar. UF 2.900. Metro a 300 m. Admite mascotas. Estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="la sala de estar no es dormitorio",
          expect=[R], loc="La Cisterna", beds=1, dist=300, pets=ANY, parking="propio", uf=2900),
        P("HT-0508", """San Miguel, 2D. UF 3.200. A 400 m del metro. Gatos sí. Estacionamiento de
           cortesía para visitas.""",
          tags=["estac_ambiguo"],
          note="cortesía para visitas no sirve",
          expect=[E], loc="San Miguel", beds=2, dist=400, pets=only("gato"), parking="visitas",
          uf=3200),
    ]),

    # ------------------------------------------------------------------ 06 --
    case("ht_06", 40_050, hc(135_000_000, None, None, 900, 2, estacionamiento=False),
         ["Independencia"], "Comprador sin mascota ni auto.", [
        P("HT-0601", """Independencia, 2D/1B. $129.000.000. Metro Plaza Chacabuco a 450 m. No se
           aceptan mascotas. Sin estacionamiento.""",
          tags=["mascota_condicion", "estac_ambiguo"],
          note="ni mascotas ni estacionamiento aplican: se aprueba",
          expect=[], loc="Independencia", beds=2, dist=450, pets=NO, parking="ninguno",
          clp=129_000_000),
        P("HT-0602", """recoleta 2 dorm 1 baño 3.250 uf metro cerro blanco 300 mts arriendo 650
           lucas""",
          tags=["estilo", "jerga_monto"],
          note="minúsculas, sin puntuación; no preferida, mayor ROI",
          expect=[], loc="Recoleta", beds=2, dist=300, pets=NONE_, parking="ninguno",
          uf=3250, rent=650_000),
        P("HT-0603", """Departamento (Independencia) de 3 habitaciones, UF 3.200; metro Hospitales a
           850 m; estacionamiento opcional. Arriendo $500.000.""",
          tags=["comuna_posicion", "dorm_notacion"],
          note="comuna entre paréntesis; 'habitaciones'",
          expect=[], loc="Independencia", beds=3, dist=850, pets=NONE_, parking="ninguno",
          uf=3200, rent=500_000),
        P("HT-0604", """Independencia, 2D. UF 3.380. A 300 m del metro.""",
          tags=["casi_cumple"],
          note="near miss: UF 3.380 = $135.369.000",
          expect=[B], loc="Independencia", beds=2, dist=300, pets=NONE_, parking="ninguno",
          uf=3380),
        P("HT-0605", """Monoambiente de 30 m² en Independencia. $70.000.000. A 200 m del metro.""",
          tags=["dorm_no_cuenta"],
          note="monoambiente = 0 dormitorios",
          expect=[R], loc="Independencia", beds=0, dist=200, pets=NONE_, parking="ninguno",
          clp=70_000_000),
        P("HT-0606", """Independencia, 2D. $120.000.000. Metro a 1 km.""",
          tags=["dist_formato"],
          note="1 km > 900 m",
          expect=[D], loc="Independencia", beds=2, dist=1000, pets=NONE_, parking="ninguno",
          clp=120_000_000),
        P("HT-0607", """Conchalí, 2 dormitorios, ciento veinte millones, paradero troncal a 400 m;
           metro Vespucio Norte a 1,2 km.""",
          tags=["cifra_palabras", "dist_multiple"],
          note="precio en palabras; vale el paradero",
          expect=[], loc="Conchalí", beds=2, dist=400, pets=NONE_, parking="ninguno",
          clp=120_000_000),
        P("HT-0608", """Independencia, 2D/2B. Precio $142.000.000 (GC $60.000; contribuciones
           exentas). A 500 m del metro.""",
          tags=["multi_monto"],
          note="el precio supera el tope; GC no es el precio",
          expect=[B], loc="Independencia", beds=2, dist=500, pets=NONE_, parking="ninguno",
          clp=142_000_000),
    ]),

    # ------------------------------------------------------------------ 07 --
    case("ht_07", 38_550, hc(150_000_000, "perro", 18, 1000, 2), ["Providencia", "Ñuñoa"],
         "El comprador de la E1 con avisos nuevos.", [
        P("HT-0701", """Providencia, calle Marchant Pereira. 2 dormitorios, 2 baños, UF 3.850. Metro
           Los Leones: 950 m. Mascotas sin restricciones. Estacionamiento asignado. Arriendo de
           referencia $980.000.""",
          tags=[],
          note="control: cumple todo",
          expect=[], loc="Providencia", beds=2, dist=950, pets=ANY, parking="asignado",
          uf=3850, rent=980_000),
        P("HT-0702", """Ñuñoa, 1D + living convertible en segundo dormitorio. UF 3.200. Metro a 400 m. Admite mascotas. Estacionamiento propio. Arriendo $720.000.""",
          tags=["dorm_no_cuenta"],
          note="el living convertible no es dormitorio",
          expect=[R], loc="Ñuñoa", beds=1, dist=400, pets=ANY, parking="propio",
          uf=3200, rent=720_000),
        P("HT-0703", """¡Precio bajo tasación! Providencia, 3D/2B. UF 4.050. Metro a 500 m. Admite mascotas. Estacionamiento propio.""",
          tags=["distractor"],
          note="UF 4.050 = $156.127.500 > tope, pese al marketing",
          expect=[B], loc="Providencia", beds=3, dist=500, pets=ANY, parking="propio", uf=4050),
        P("HT-0704", """Depto Ñuñoa 2 dorm, 145 millones, metro Ñuñoa a 600 m, perros hasta 20 kg,
           estacionamiento propio, arriendo 820 mil""",
          tags=["jerga_monto", "mascota_condicion"],
          note="'145 millones' sin $; 18 <= 20 kg",
          expect=[], loc="Ñuñoa", beds=2, dist=600, pets=only("perro", 20), parking="propio",
          clp=145_000_000, rent=820_000),
        P("HT-0705", """Santiago, 2D/1B. $132.000.000. Metro Santa Isabel a 300 m. Pet friendly.
           Estacionamiento propio. Arriendo $950.000.""",
          tags=[],
          note="no preferida y con el mayor ROI: va después de las preferidas",
          expect=[], loc="Santiago", beds=2, dist=300, pets=ANY, parking="propio",
          clp=132_000_000, rent=950_000),
        P("HT-0706", """Providencia, 2D. UF 3.700. A 500 m del metro. Mascotas: solo gatos.
           Estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="solo gatos; comprador con perro",
          expect=[M], loc="Providencia", beds=2, dist=500, pets=only("gato"), parking="propio",
          uf=3700),
        P("HT-0707", """Ñuñoa, 2D/1B. UF 3.600. Metro a 350 m. Admite mascotas. Estacionamiento: se
           arrienda aparte en $40.000 al mes.""",
          tags=["estac_ambiguo", "multi_monto"],
          note="se arrienda aparte: no incluido",
          expect=[E], loc="Ñuñoa", beds=2, dist=350, pets=ANY, parking="ninguno", uf=3600),
        P("HT-0708", """Providencia, 2D. UF 3.500. A 12 cuadras del metro. Pet friendly.
           Estacionamiento propio.""",
          tags=["dist_formato"],
          note="cuadras: no verificable",
          expect=[D], loc="Providencia", beds=2, dist=None, pets=ANY, parking="propio", uf=3500),
    ]),

    # ------------------------------------------------------------------ 08 --
    case("ht_08", 41_400, hc(220_000_000, "perro", 6, 1100, 3), ["Vitacura"],
         "Sector oriente: precios altos y extras con precio aparte.", [
        P("HT-0801", """Vitacura, casa 4 dormitorios, 3 baños. UF 5.250. Paradero troncal de Av.
           Vitacura a 1,1 km. Mascotas permitidas. Estacionamiento para 3 autos.""",
          tags=["dist_formato", "casi_cumple"],
          note="1,1 km == máximo de 1.100: cumple; UF 5.250 = $217.350.000",
          expect=[], loc="Vitacura", beds=4, dist=1100, pets=ANY, parking="propio", uf=5250),
        P("HT-0802", """Las Condes, 3D/3B. $205.000.000. Metro Colón a 800 m. Se aceptan perros de
           hasta 10 kg y gatos. Estacionamiento propio. Arriendo 40 UF.""",
          tags=["arriendo_uf", "mascota_condicion"],
          note="perros <= 10 kg y gatos; arriendo 40 UF; no preferida, mayor ROI",
          expect=[], loc="Las Condes", beds=3, dist=800, pets=both(10), parking="propio",
          clp=205_000_000, rent=rent_uf(40, 41_400)),
        P("HT-0803", """VITACURA — depto tres dormitorios + estudio, UF 5.100, metro Manquehue a 900
           m, se aceptan mascotas, estacionamiento asignado, renta 1.500.000""",
          tags=["dorm_notacion", "cifra_palabras"],
          note="'tres dormitorios + estudio' = 3",
          expect=[], loc="Vitacura", beds=3, dist=900, pets=ANY, parking="asignado",
          uf=5100, rent=1_500_000),
        P("HT-0804", """Vitacura, 3D. UF 5.320. Metro a 600 m. Admite mascotas. Estacionamiento
           propio.""",
          tags=["casi_cumple"],
          note="near miss: UF 5.320 = $220.248.000",
          expect=[B], loc="Vitacura", beds=3, dist=600, pets=ANY, parking="propio", uf=5320),
        P("HT-0805", """Vitacura, 4D. UF 5.000. A 700 m del metro. No se aceptan perros.
           Estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="prohíbe perros",
          expect=[M], loc="Vitacura", beds=4, dist=700, pets=NO, parking="propio", uf=5000),
        P("HT-0806", """Lo Barnechea, 2 dormitorios + sala de juegos. UF 4.900. A 600 m del
           paradero troncal. Pet friendly. Estacionamiento propio.""",
          tags=["dorm_no_cuenta"],
          note="la sala de juegos no es dormitorio",
          expect=[R], loc="Lo Barnechea", beds=2, dist=600, pets=ANY, parking="propio", uf=4900),
        P("HT-0807", """Vitacura, 3D. UF 4.800, GC $250.000. Metro a 1.400 m. Admite mascotas.
           Estacionamiento propio.""",
          tags=["multi_monto"],
          note="1.400 m > 1.100",
          expect=[D], loc="Vitacura", beds=3, dist=1400, pets=ANY, parking="propio", uf=4800),
        P("HT-0808", """Vitacura, 3D. UF 4.950. Metro a 500 m. Admite mascotas. Estacionamiento en
           venta por separado (UF 450).""",
          tags=["estac_ambiguo", "multi_monto"],
          note="se vende aparte: no incluido",
          expect=[E], loc="Vitacura", beds=3, dist=500, pets=ANY, parking="ninguno", uf=4950),
    ]),

    # ------------------------------------------------------------------ 09 --
    case("ht_09", 39_600, hc(128_000_000, "gato", 7, 800, 2), ["Macul"],
         "Avisos de Macul con cifras en palabras.", [
        P("HT-0901", """Macul. 2D/1B. Valor 3.150 UF. Metro Las Torres 500 m. Gatos y perros sin
           restricción. Estac. propio. Arr. $560.000.""",
          tags=[],
          note="control; UF 3.150 = $124.740.000",
          expect=[], loc="Macul", beds=2, dist=500, pets=both(), parking="propio",
          uf=3150, rent=560_000),
        P("HT-0902", """Depto en Macul de dos dormitorios y un baño, ciento veinticinco millones de
           pesos, a setecientos metros del metro Quilín, acepta mascotas, estacionamiento
           asignado.""",
          tags=["cifra_palabras"],
          note="precio y distancia en palabras",
          expect=[], loc="Macul", beds=2, dist=700, pets=ANY, parking="asignado",
          clp=125_000_000),
        P("HT-0903", """2D 2B Ñuñoa; UF 3.200; metro Rodrigo de Araya 300 m; gatos OK; est. propio;
           arriendo 18 UF""",
          tags=["dorm_notacion", "arriendo_uf"],
          note="arriendo 18 UF; no preferida, mayor ROI",
          expect=[], loc="Ñuñoa", beds=2, dist=300, pets=only("gato"), parking="propio",
          uf=3200, rent=rent_uf(18, 39_600)),
        P("HT-0904", """Macul, 2D. UF 3.000. A 400 m del metro. Mascotas hasta 5 kilos.
           Estacionamiento propio.""",
          tags=["mascota_condicion"],
          note="5 kg contra gato de 7",
          expect=[M], loc="Macul", beds=2, dist=400, pets=kg(5), parking="propio", uf=3000),
        P("HT-0905", """Macul, 3 dormitorios. Ciento treinta millones. Metro a 600 m. Admite mascotas. Estacionamiento propio.""",
          tags=["cifra_palabras"],
          note="$130.000.000 en palabras, sobre el tope",
          expect=[B], loc="Macul", beds=3, dist=600, pets=ANY, parking="propio", clp=130_000_000),
        P("HT-0906", """Macul, 2D. UF 2.900. A 300 m del metro. Gatos sí. Estacionamiento: no; hay
           estacionamiento en calle.""",
          tags=["estac_ambiguo"],
          note="calle no sirve",
          expect=[E], loc="Macul", beds=2, dist=300, pets=only("gato"), parking="calle", uf=2900),
        P("HT-0907", """Macul, 2D. UF 3.000. El metro está a 15 minutos a pie. Gatos OK.
           Estacionamiento propio.""",
          tags=["dist_formato"],
          note="solo minutos",
          expect=[D], loc="Macul", beds=2, dist=None, pets=only("gato"), parking="propio",
          uf=3000),
        P("HT-0908", """Macul, 1D + escritorio. UF 2.800. Metro a 500 m. Admite mascotas.
           Estacionamiento propio.""",
          tags=["dorm_no_cuenta", "dorm_notacion"],
          note="'1D + escritorio' = 1",
          expect=[R], loc="Macul", beds=1, dist=500, pets=ANY, parking="propio", uf=2800),
    ]),

    # ------------------------------------------------------------------ 10 --
    case("ht_10", 40_750, hc(170_000_000, "perro", 35, 1500, 3, estacionamiento=False),
         ["Puente Alto", "La Florida"], "Perro grande; estacionamiento no requerido.", [
        P("HT-1001", """Puente Alto, casa 3D/2B. $119.000.000. Metro Plaza de Puente Alto a 1,5 km.
           Mascotas sin límite de peso. Sin estacionamiento (pasaje).""",
          tags=["dist_formato", "casi_cumple", "estac_ambiguo"],
          note="1,5 km == máximo; sin estacionamiento pero no se requiere",
          expect=[], loc="Puente Alto", beds=3, dist=1500, pets=ANY, parking="ninguno",
          clp=119_000_000),
        P("HT-1002", """La Florida, 4 habitaciones. UF 3.950. A 1.200 m del Metro Trinidad. Se
           aceptan perros grandes. Arriendo $900.000.""",
          tags=["dorm_notacion"],
          note="'habitaciones'; perros sin límite",
          expect=[], loc="La Florida", beds=4, dist=1200, pets=only("perro"), parking="ninguno",
          uf=3950, rent=900_000),
        P("HT-1003", """Puente Alto, 3D. $110.000.000. A 700 m del metro. Perros de hasta 30 kg.""",
          tags=["mascota_condicion"],
          note="30 kg contra perro de 35",
          expect=[M], loc="Puente Alto", beds=3, dist=700, pets=only("perro", 30),
          parking="ninguno", clp=110_000_000),
        P("HT-1004", """San Bernardo — 3D — $105.000.000 — paradero troncal 600 m — mascotas
           bienvenidas — arriendo $780.000 (la casa vecina, de 4D, se arrienda en $950.000)""",
          tags=["distractor"],
          note="el arriendo de $950.000 es de la vecina; no preferida, mayor ROI",
          expect=[], loc="San Bernardo", beds=3, dist=600, pets=ANY, parking="ninguno",
          clp=105_000_000, rent=780_000),
        P("HT-1005", """Puente Alto, 2D+1B. $95.000.000. Metro a 500 m. Admite mascotas.""",
          tags=["dorm_notacion"],
          note="'2D+1B' = 2 dormitorios y 1 baño: 2 < 3",
          expect=[R], loc="Puente Alto", beds=2, dist=500, pets=ANY, parking="ninguno",
          clp=95_000_000),
        P("HT-1006", """La Florida, 3D. $140.000.000. A 2 km del metro. Pet friendly.""",
          tags=["dist_formato"],
          note="2 km > 1.500",
          expect=[D], loc="La Florida", beds=3, dist=2000, pets=ANY, parking="ninguno",
          clp=140_000_000),
        P("HT-1007", """Puente Alto, 3D. $100.000.000. A 800 m del metro. Patio amplio.""",
          tags=["mascota_silencio"],
          note="no habla de mascotas ('patio amplio' no es permiso)",
          expect=[M], loc="Puente Alto", beds=3, dist=800, pets=NONE_, parking="ninguno",
          clp=100_000_000),
        P("HT-1008", """La Florida, 4D. UF 4.180. Metro a 900 m. Admite mascotas.""",
          tags=["casi_cumple"],
          note="near miss: UF 4.180 = $170.335.000",
          expect=[B], loc="La Florida", beds=4, dist=900, pets=ANY, parking="ninguno", uf=4180),
    ]),
]
