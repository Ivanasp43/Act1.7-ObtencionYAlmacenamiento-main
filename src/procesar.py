from config.constantes import (
    IPC,
    IPV,
    ETCL,
    EAES_OCUPACION,
    EAES_PERCENTILES,
    TASA_PARO,
    TEMPORALIDAD,
)
from src.db import get_cursor


def procesar_datos(codigo, datos):
    """
    Función principal de transformación. Despacha el procesamiento
    a las funciones especializadas según el código INE.
    """
    # 1. SEGREGACIÓN POR GRUPO DE TABLA DE HECHOS

    if not datos:
        return []

    elif codigo in [IPC, IPV]:
        # T1: Precios (Mensual y Trimestral)
        return _procesar_precios(codigo, datos)

    elif codigo in [ETCL, EAES_OCUPACION, EAES_PERCENTILES]:
        # T2: Ingresos/Salarios (Trimestral y Anual)
        return _procesar_salarios(codigo, datos)

    elif codigo in [TASA_PARO, TEMPORALIDAD]:
        # T3: Empleo/Calidad Laboral (Trimestral)
        return _procesar_empleo(codigo, datos)

    else:
        print(f"[Procesar] ERROR: Código {codigo} no mapeado a una tabla de hechos.")
        return []


def _aplanar_nombre_serie(codigo, nombre_serie):
    """
    Parsea el string 'Nombre' del INE.
    Se usa split('.') y se limpian los espacios
    """

    metadata = {}
    # Separa por punto y limpia los espacios en blanco
    partes = [p.strip() for p in nombre_serie.split(".") if p.strip()]

    # ---------------------------------------------------------
    # TASA DE PARO (65334)
    # Ejemplo: "Tasa de paro de la población. Ambos sexos. Total Nacional. Todas las edades."
    # Índices: [0: Indicador, 1: Sexo, 2: Geo, 3: Edad]
    # ---------------------------------------------------------
    if codigo == TASA_PARO:
        metadata["Sexo"] = partes[1]
        metadata["Geografia"] = partes[2]
        metadata["Grupo_Edad"] = partes[3]

    # ---------------------------------------------------------
    # TEMPORALIDAD / OCUPADOS (65132)
    # Ejemplo: "Total Nacional. Ocupados. Ambos sexos. No asalariados. Jornada a tiempo completo. Personas."
    # Índices: [0: Geo, 1: Unidad/Tipo, 2: Sexo, 3: Contrato, 4: Jornada, 5: Unidad]
    # ---------------------------------------------------------
    elif codigo == TEMPORALIDAD:
        metadata["Geografia"] = partes[0]
        metadata["Sexo"] = partes[2]
        metadata["Tipo_Contrato"] = partes[3]
        metadata["Tipo_Jornada"] = partes[4]

    # ---------------------------------------------------------
    # IPC (50913) e IPV (25171)
    # Ejemplo: "Total Nacional. Índice general. Índice."
    # Índices: [0: Geo, 1: Categoria, 2: Tipo dato]
    # ---------------------------------------------------------
    elif codigo in [IPC, IPV]:
        metadata["Geografia"] = partes[0]
        metadata["Categoria"] = partes[
            1
        ]  # Grupos ECOICOP para IPC y Tipo de Vivienda para
        metadata["Tipo_Dato"] = partes[2]  # Indice, Variacion anual, etc

    # ---------------------------------------------------------
    # ETCL (6061)
    # Ejemplo: "Total Nacional. Industria... . Coste laboral total. Costes laborales. Euros."
    # Índices: [0: Geo, 1: Sector, 2: Componente_Coste]
    # ---------------------------------------------------------
    elif codigo == ETCL:
        metadata["Geografia"] = partes[0]
        metadata["Sector"] = partes[1]
        metadata["Indicador"] = partes[2]

    # ---------------------------------------------------------
    # EAES PERCENTILES (28191)
    # Ejemplo: "Total. Total Nacional. Dato base. Media."
    # Índices: [0: Sexo/Total, 1: Geo, 2: Dato base, 3: Estadística]
    # ---------------------------------------------------------
    elif codigo == EAES_PERCENTILES:
        metadata["Sexo"] = partes[0]
        metadata["Geografia"] = partes[1]
        metadata["Indicador"] = partes[3]  # Media, Mediana, Percentil 10...

    # ---------------------------------------------------------
    # EAES OCUPACION (28186)
    # Ejemplo: "Total. Total. Salario medio bruto. Total Nacional. Dato base."
    # Índices: [0: Ocupacion, 1: ...]
    # ---------------------------------------------------------
    elif codigo == EAES_OCUPACION:
        metadata["Sexo"] = partes[1]
        metadata["Ocupacion"] = partes[0]
        metadata["Geografia"] = partes[3]

    return metadata


def _procesar_precios(codigo, data):
    filas_insertar = []

    for serie in data:
        nombre_serie = serie.get("Nombre", "")
        meta = _aplanar_nombre_serie(codigo, nombre_serie)
        if not meta: 
            continue

        # --- Filtro 1: TIPO DE DATO ---
        tipo_dato = meta.get("Tipo_Dato", "")
        es_indice = "Índice" in tipo_dato and "Variación" not in tipo_dato
        es_var_anual = "Variación anual" in tipo_dato

        if not (es_indice or es_var_anual):
            continue

        # --- Filtro 2: CATEGORÍA ---
        cat = meta.get("Categoria", "").strip()
        categoria_limpia = ""

        if codigo == IPV:
            # Solo aceptamos "General"
            if cat != "General":
                continue
            categoria_limpia = "Vivienda Total"
        
        elif codigo == IPC:
            # Si es el general, normalizamos el nombre
            if "Índice general" == cat:
                categoria_limpia = "IPC General"
            else:
                # Si es una categoría específica (Alimentos, etc.), la dejamos tal cual
                categoria_limpia = cat

        # --- DIMENSIONES ---
        geo_nombre = meta.get("Geografia", "Total Nacional")
        id_geografia = _obtener_o_crear("geografia", "nombre", geo_nombre)

        nombre_base = "IPC" if codigo == IPC else "IPV"
        
        if es_var_anual:
            nombre_indicador = f"{nombre_base}_Variacion_Anual_INE"
            unidad = "%"
        else:
            nombre_indicador = f"{nombre_base}_Indice_Base_2021_INE"
            unidad = "Base 2021=100"

        id_indicador = _obtener_o_crear("indicador", "nombre", nombre_indicador, unidad=unidad)

        # --- DATOS TEMPORALES ---
        for dato in serie.get("Data", []):
            # Lectura segura del periodo (Mayúsculas/Minúsculas)
            periodo_ine = dato.get("FK_Periodo") or dato.get("Fk_Periodo")

            mes = periodo_ine if codigo == IPC else None
            trimestre = periodo_ine if codigo == IPV else None

            id_periodo = _obtener_o_crear_periodo(
                anio=dato.get("Anyo"), 
                trimestre_fk=trimestre, 
                mes=mes
            )
            
            valor = dato.get("Valor")
            if valor is None: 
                continue

            filas_insertar.append(
                (id_periodo, id_indicador, id_geografia, categoria_limpia, valor)
            )
            
    return filas_insertar


def _procesar_empleo(codigo, data):
    filas_insertar = []

    for serie in data:
        # 1. Obtener los metadatos del nombre
        nombre_serie = serie.get("Nombre", "")
        metadata_dims = _aplanar_nombre_serie(codigo, nombre_serie)

        nombre_indicador = ""
        unidad = ""

        if codigo == TASA_PARO:
            nombre_indicador = "Tasa_Paro"
            unidad = "%"

        elif codigo == TEMPORALIDAD:
            contrato = metadata_dims.get("Tipo_Contrato", "")
            jornada = metadata_dims.get("Tipo_Jornada", "")

            # 1. Si NO es la jornada total (es parcial o completa), pasamos a la siguiente.
            if "Total" not in jornada:
                continue

            # 2. Filtramos contrato: Solo queremos saber el TOTAL de asalariados y los TEMPORALES y El total de jornada.
            # Los indefinidos se pueden deducir (Total - Temporal)

            if "Total asalariados" in contrato:
                nombre_indicador = "Asalariados_Total"
            elif "Asalariados con contrato temporal" in contrato:
                nombre_indicador = "Asalariados_Temporal"
            else:
                continue

            unidad = "Miles de personas"

        else:
            raise ValueError

        # Obtener IDs de los FK (indicador y geografia)
        id_geografia = _obtener_o_crear(
            "geografia", "nombre", metadata_dims.get("Geografia")
        )
        id_indicador = _obtener_o_crear(
            "indicador", "nombre", nombre_indicador, unidad=unidad
        )

        for dato in serie.get("Data"):
            # Obtener ID del periodo
            id_periodo = _obtener_o_crear_periodo(
                anio=dato.get("Anyo"), trimestre_fk=dato.get("FK_Periodo")
            )
            sexo = metadata_dims.get("Sexo")
            grupo_edad = metadata_dims.get("Grupo_Edad", None)
            tipo_jornada = metadata_dims.get("Tipo_Jornada", None)
            tipo_contrato = metadata_dims.get("Tipo_Contrato", None)
            valor = dato.get("Valor")

            filas_insertar.append(
                (
                    id_periodo,
                    id_indicador,
                    id_geografia,
                    sexo,
                    grupo_edad,
                    tipo_jornada,
                    tipo_contrato,
                    valor,
                )
            )

    return filas_insertar


def _procesar_salarios(codigo, data):

    filas_insertar = []

    for serie in data:
        nombre_serie = serie.get("Nombre", "")
        meta = _aplanar_nombre_serie(codigo, nombre_serie)

        nombre_indicador = ""
        unidad = ""

        # Logica de filtrado
        indicador = meta.get("Indicador", "")

        if codigo == ETCL:
            # Solo queremos el sueldo bruto (Coste salarial total)
            if "Coste salarial total" not in indicador:
                continue
            nombre_indicador = "Salario_Coste_Trimestral"

        elif codigo == EAES_PERCENTILES:
            PERCENTILES_INTERES = [
                "Media",
                "Mediana",
                "Percentil 10",
                "Cuartil inferior",
            ]

            es_interes = any(
                p.lower() in indicador.lower() for p in PERCENTILES_INTERES
            )
            if not es_interes:
                continue
            nombre_indicador = f"Salario Anual {indicador}"

        elif codigo == EAES_OCUPACION:
            nombre_indicador = "Salario Anual Ocupacion"

        else:
            continue

        # Gestionar dimensiones
        id_geografia = _obtener_o_crear(
            "geografia", "nombre", meta.get("Geografia", "Total Nacional")
        )
        id_indicador = _obtener_o_crear(
            "indicador", "nombre", nombre_indicador, unidad="Euros"
        )

        # Iterar datos temporales
        for dato in serie.get("Data", []):
            id_periodo = _obtener_o_crear_periodo(
                anio=dato.get("Anyo"), trimestre_fk=dato.get("FK_Periodo")
            )

            valor = dato.get("Valor")

            # Extraemos metadatos específicos de cada tabla para llenar las columnas de T_salarios
            sexo = meta.get("Sexo", "Total")

            # Sector solo existe en ETCL, si no, es NULL (N/A)
            sector = meta.get("Sector", "N/A")

            # Ocupación solo existe en EAES_OCUPACION, si no, es NULL (N/A)
            ocupacion = meta.get("Ocupacion", "N/A")

            # Estructura T_salarios:
            # id_periodo, id_indicador, id_geografia, sexo, sector_cnae, ocupacion_cno11, valor
            filas_insertar.append(
                (id_periodo, id_indicador, id_geografia, sexo, sector, ocupacion, valor)
            )

    return filas_insertar


def _obtener_o_crear_periodo(anio, mes=None, trimestre_fk=None):
    mes_calculado = mes
    fecha_iso = ""

    # 1. Caso Mensual (IPC)
    if mes is not None:
        fecha_iso = f"{anio}-{str(mes).zfill(2)}-01"
    
    # 2. Caso Trimestral o Anual
    elif trimestre_fk is not None:
        if trimestre_fk == 28: # ANUAL
            mes_calculado = None 
            fecha_iso = f"{anio}-01-01" # Forzamos Enero para el dato anual
        
        elif trimestre_fk == 19: # T1
            mes_calculado = 1
            fecha_iso = f"{anio}-01-01"
        elif trimestre_fk == 20: # T2
            mes_calculado = 4
            fecha_iso = f"{anio}-04-01"
        elif trimestre_fk == 21: # T3
            mes_calculado = 7
            fecha_iso = f"{anio}-07-01"
        elif trimestre_fk == 22: # T4
            mes_calculado = 10
            fecha_iso = f"{anio}-10-01"
        else: raise ValueError(f"Código trimestre {trimestre_fk} error")

    # 3. Caso Defecto
    else:
        fecha_iso = f"{anio}-01-01"

    return _obtener_o_crear(
        tabla="periodo",
        columna_busqueda="fecha_iso",
        valor_busqueda=fecha_iso,
        anio=anio,
        trimestre=trimestre_fk if (trimestre_fk != 28) else None,
        mes=mes_calculado,
    )


def _obtener_o_crear(tabla, columna_busqueda, valor_busqueda, **kwargs):
    """
    Función centralizada para buscar o crear una dimensión (Periodo, Geografía, Indicador).
    """
    id_columna = f"id_{tabla}"
    tabla_nombre = f"tbl_{tabla}"

    with get_cursor() as cursor:
        # 1. Intentar buscar el ID
        sql_select = f"SELECT {id_columna} FROM {tabla_nombre} WHERE {columna_busqueda} = ?"
        cursor.execute(sql_select, (valor_busqueda,))

        resultado = cursor.fetchone()

        if resultado:
            # El periodo ya existe. Devolvemos su ID.
            return resultado[0]

        # 2. El registro no existe. Lo insertamos.

        sql_insert = ""
        parametros = ()

        if tabla == "periodo":
            sql_insert = "INSERT INTO tbl_periodo (anio, mes, trimestre, fecha_iso) VALUES (?, ?, ?, ?)"
            parametros = (kwargs.get("anio"), kwargs.get("mes"), kwargs.get("trimestre"), valor_busqueda)

        elif tabla == "geografia":
            sql_insert = "INSERT INTO tbl_geografia (nombre) VALUES (?)"
            parametros = (valor_busqueda,)

        elif tabla == "indicador":
            sql_insert = "INSERT INTO tbl_indicador (nombre, unidad) VALUES (?, ?)"
            parametros = (valor_busqueda, kwargs.get("unidad"))
        else:
            raise ValueError(f"Tabla '{tabla}' no soportada.")

        cursor.execute(sql_insert, parametros)
        return cursor.lastrowid
