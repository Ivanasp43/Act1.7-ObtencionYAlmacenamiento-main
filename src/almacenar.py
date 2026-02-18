"""
Recibe los datos procesados de procesar.py y los inserta en la BD
"""
import sqlite3

from src.db import get_cursor

def insertar_datos( tabla, datos):
    
    if not datos:
        print(f"No existen datos para insertar en la tabla: {tabla}.")
        return

    
    sql = ""

    
    # CONSULTAS SQL SEGUN LA TABLA DE DESTINO:
    if tabla == "T_precios":
        sql = """
        INSERT OR IGNORE INTO T_precios 
        (id_periodo, id_indicador, id_geografia, categoria_gasto, valor) 
        VALUES (?, ?, ?, ?, ?)
        """
        #Ignore para evitar valores duplicados 

    elif tabla == "T_salarios":
        sql = """
        INSERT OR IGNORE INTO T_salarios 
        (id_periodo, id_indicador, id_geografia, sexo, sector_cnae, ocupacion_cno11, valor) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """

    elif tabla == "T_empleo":
        sql = """
        INSERT OR IGNORE INTO T_empleo 
        (id_periodo, id_indicador, id_geografia, sexo, grupo_edad, tipo_jornada, tipo_contrato, valor) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

    else:
        print(f"La tabla '{tabla}' no existe")
        return



# INSERCIÓN MASIVA DE DATOS 
    with get_cursor() as cursor:
        try:
            cursor.executemany(sql, datos)
        except sqlite3.Error as e:
            print(f"Se ha producido un error al insertar datos en la tabla {tabla}: {e}")
