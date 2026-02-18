from config.constantes import (
    IPC,
    IPV,
    TASA_PARO,
    TEMPORALIDAD,
    EAES_OCUPACION,
    EAES_PERCENTILES,
    ETCL,
)
from src.inedata import INEDataExtractor
from src.procesar import procesar_datos
from src.almacenar import insertar_datos
from src.db import DatabaseConnection, crear_base_datos


def main():

    db = DatabaseConnection().get_connection()
    crear_base_datos()

    tablas = [IPC, IPV, TASA_PARO, TEMPORALIDAD, EAES_OCUPACION, EAES_PERCENTILES, ETCL]
    for codigo in tablas:
        extractor = INEDataExtractor(codigo)
        if extractor.obtener_datos():
            datos_procesados = procesar_datos(codigo, extractor.raw_data)
            
            print("Procesando datos de tabla (Mostrando la primera fila)", codigo)
            print(datos_procesados[0])

            print("Número de filas a insertar", len(datos_procesados))

            tabla_destino = ""

            if codigo in [IPC, IPV]:
                tabla_destino = "T_precios"
            elif codigo in [ETCL, EAES_OCUPACION, EAES_PERCENTILES]:
                tabla_destino = "T_salarios"
            elif codigo in [TASA_PARO, TEMPORALIDAD]:
                tabla_destino = "T_empleo"

            # Llamamos a almacenar pasándole el nombre
            if tabla_destino and datos_procesados:
                insertar_datos(tabla_destino, datos_procesados)
                pass
            # ---------------------------------------------------------
        else:
            print(f"No se pudieron obtener los datos de la tabla {codigo}")

    DatabaseConnection().close()


if __name__ == "__main__":
    main()
