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

    if not datos:
        return []

    elif codigo in [IPC, IPV]:
        return _procesar_precios(codigo, datos)

    elif codigo in [ETCL, EAES_OCUPACION, EAES_PERCENTILES]:
        return _procesar_salarios(codigo, datos)

    elif codigo in [TASA_PARO, TEMPORALIDAD]:
        return _procesar_empleo(codigo, datos)

    else:
        print(f"[Procesar] ERROR: Código {codigo} no mapeado.")
        return []


# ==========================================================
# APLANADO DE METADATOS
# ==========================================================

def _aplanar_nombre_serie(codigo, nombre_serie):

    metadata = {}
    partes = [p.strip() for p in nombre_serie.split(".") if p.strip()]

    if codigo == TASA_PARO:
        metadata["Sexo"] = partes[1]
        metadata["Geografia"] = partes[2]
        metadata["Grupo_Edad"] = partes[3]

    elif codigo == TEMPORALIDAD:
        metadata["Geografia"] = partes[0]
        metadata["Sexo"] = partes[2]
        metadata["Tipo_Contrato"] = partes[3]
        metadata["Tipo_Jornada"] = partes[4]

    elif codigo in [IPC, IPV]:
        metadata["Geografia"] = partes[0]
        metadata["Categoria"] = partes[1]
        metadata["Tipo_Dato"] = partes[2]

    elif codigo == ETCL:
        metadata["Geografia"] = partes[0]
        metadata["Sector"] = partes[1]
        metadata["Indicador"] = partes[2]

    #  BLOQUE CORRECTO PARA EAES
    elif codigo == EAES_OCUPACION:
        metadata["Ocupacion"] = partes[0]
        metadata["Sexo"] = partes[1]
        metadata["Geografia"] = partes[2]

    elif codigo == EAES_PERCENTILES:
        metadata["Sexo"] = partes[0]
        metadata["Geografia"] = partes[1]
        metadata["Indicador"] = partes[3]

    return metadata


# ==========================================================
# PROCESAR PRECIOS (IPC / IPV)
# ==========================================================

def _procesar_precios(codigo, data):

    filas_insertar = []

    for serie in data:
        nombre_serie = serie.get("Nombre", "")
        meta = _aplanar_nombre_serie(codigo, nombre_serie)

        categoria = meta.get("Categoria")
        geo = meta.get("Geografia")

        id_geografia = _obtener_o_crear("geografia", "nombre", geo)

        nombre_indicador = "IPC" if codigo == IPC else "IPV"

        id_indicador = _obtener_o_crear(
            "indicador", "nombre", nombre_indicador, unidad="Índice"
        )

        for dato in serie.get("Data", []):
            id_periodo = _obtener_o_crear_periodo(
                anio=dato.get("Anyo"),
                trimestre_fk=dato.get("FK_Periodo"),
            )

            valor = dato.get("Valor")

            filas_insertar.append(
                (id_periodo, id_indicador, id_geografia, categoria, valor)
            )

    return filas_insertar


# ==========================================================
# PROCESAR EMPLEO
# ==========================================================

def _procesar_empleo(codigo, data):

    filas_insertar = []

    for serie in data:
        meta = _aplanar_nombre_serie(codigo, serie.get("Nombre", ""))

        nombre_indicador = "Tasa_Paro" if codigo == TASA_PARO else "Temporalidad"

        id_geografia = _obtener_o_crear(
            "geografia", "nombre", meta.get("Geografia")
        )

        id_indicador = _obtener_o_crear(
            "indicador", "nombre", nombre_indicador, unidad="%"
        )

        for dato in serie.get("Data", []):
            id_periodo = _obtener_o_crear_periodo(
                anio=dato.get("Anyo"),
                trimestre_fk=dato.get("FK_Periodo"),
            )

            filas_insertar.append(
                (
                    id_periodo,
                    id_indicador,
                    id_geografia,
                    meta.get("Sexo"),
                    meta.get("Grupo_Edad"),
                    meta.get("Tipo_Jornada"),
                    meta.get("Tipo_Contrato"),
                    dato.get("Valor"),
                )
            )

    return filas_insertar


# ==========================================================
# PROCESAR SALARIOS (EAES)
# ==========================================================

def _procesar_salarios(codigo, data):

    filas_insertar = []

    for serie in data:
        meta = _aplanar_nombre_serie(codigo, serie.get("Nombre", ""))

        id_geografia = _obtener_o_crear(
            "geografia", "nombre", meta.get("Geografia", "Total Nacional")
        )

        id_indicador = _obtener_o_crear(
            "indicador",
            "nombre",
            "Salario_Anual_Ocupacion",
            unidad="Euros",
        )

        for dato in serie.get("Data", []):
            id_periodo = _obtener_o_crear_periodo(
                anio=dato.get("Anyo"),
                trimestre_fk=dato.get("FK_Periodo"),
            )

            filas_insertar.append(
                (
                    id_periodo,
                    id_indicador,
                    id_geografia,
                    meta.get("Sexo"),
                    None,  # sector_cnae no aplica en EAES
                    meta.get("Ocupacion"),
                    dato.get("Valor"),
                )
            )

    return filas_insertar


# ==========================================================
# FUNCIONES AUXILIARES (NO TOCAR)
# ==========================================================

def _obtener_o_crear_periodo(anio, mes=None, trimestre_fk=None):

    if trimestre_fk in [19, 20, 21, 22]:
        mes = {19: 1, 20: 4, 21: 7, 22: 10}[trimestre_fk]
    else:
        mes = 1

    fecha_iso = f"{anio}-{str(mes).zfill(2)}-01"

    return _obtener_o_crear(
        "periodo",
        "fecha_iso",
        fecha_iso,
        anio=anio,
        mes=mes,
        trimestre=trimestre_fk,
    )


def _obtener_o_crear(tabla, columna_busqueda, valor_busqueda, **kwargs):

    id_col = f"id_{tabla}"
    tabla_nombre = f"tbl_{tabla}"

    with get_cursor() as cursor:
        cursor.execute(
            f"SELECT {id_col} FROM {tabla_nombre} WHERE {columna_busqueda} = ?",
            (valor_busqueda,),
        )
        res = cursor.fetchone()

        if res:
            return res[0]

        if tabla == "periodo":
            cursor.execute(
                "INSERT INTO tbl_periodo (anio, mes, trimestre, fecha_iso) VALUES (?, ?, ?, ?)",
                (
                    kwargs.get("anio"),
                    kwargs.get("mes"),
                    kwargs.get("trimestre"),
                    valor_busqueda,
                ),
            )

        elif tabla == "geografia":
            cursor.execute(
                "INSERT INTO tbl_geografia (nombre) VALUES (?)",
                (valor_busqueda,),
            )

        elif tabla == "indicador":
            cursor.execute(
                "INSERT INTO tbl_indicador (nombre, unidad) VALUES (?, ?)",
                (valor_busqueda, kwargs.get("unidad")),
            )

        return cursor.lastrowid
