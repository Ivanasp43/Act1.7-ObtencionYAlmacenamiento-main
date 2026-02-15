import polars as pl
import plotly.express as px
import os
import sqlite3

# colores
rojo = '\033[91m'
amarillo = '\033[93m'
turquesa = '\033[38;5;44m'
lima = '\33[38;5;46m'
reset = '\033[0m'

# CONFIGURACIÓN DE RUTAS 
DB_PATH = "proyecto_datos.db"
URI = f"sqlite:///{DB_PATH}"
OUTPUT_DIR = "data_output"
VIS_DIR = "visualizaciones"
os.makedirs(OUTPUT_DIR, exist_ok=True) #crea la carpeta de salida automáticamente si no existe
os.makedirs(VIS_DIR, exist_ok=True) #crea la carpeta de visualizaciones automáticamente si no existe

# CONEXIÓN Y EXTRACCIÓN 
def cargar_datos():
    print(f"\n{amarillo}1. Conectando a la base de datos con Polars...{reset}")
    
    # Creamos la conexión física con sqlite3 para evitar el error de URI
    conn = sqlite3.connect(DB_PATH)

    # Query para Precios (IPC/IPV)
    query_precios = """
    SELECT p.valor AS valor_ipc, p.categoria_gasto, t.fecha_iso, i.nombre as indicador
    FROM T_precios p
    JOIN tbl_periodo t ON p.id_periodo = t.id_periodo
    JOIN tbl_indicador i ON p.id_indicador = i.id_indicador
    """
    
    # Query para Salarios
    query_salarios = """
    SELECT s.valor AS valor_salario, s.sexo, s.sector_cnae, t.fecha_iso, i.nombre as indicador_salario
    FROM T_salarios s
    JOIN tbl_periodo t ON s.id_periodo = t.id_periodo
    JOIN tbl_indicador i ON s.id_indicador = i.id_indicador
    """

    # Query para Empleo
    query_empleo = """
    SELECT e.valor AS valor_empleo, e.sexo, t.fecha_iso, i.nombre as indicador_empleo
    FROM T_empleo e
    JOIN tbl_periodo t ON e.id_periodo = t.id_periodo
    JOIN tbl_indicador i ON i.id_indicador = e.id_indicador
    """
    
    df_precios = pl.read_database(query=query_precios, connection=conn)
    df_salarios = pl.read_database(query=query_salarios, connection=conn)
    df_empleo = pl.read_database(query=query_empleo, connection=conn)
    
    conn.close() # Cerramos conexión
    return df_precios, df_salarios, df_empleo

# LIMPIEZA Y ESTRUCTURACIÓN: Aplicamos la lógica de Big Data y columnas calculadas

def procesar_informacion(df_precios, df_salarios, df_empleo):
    print(f"{amarillo}2. Procesando y cruzando información...{reset}")

    # A) Limpieza: Convertir fechas a objeto Date y quitar nulos
    df_precios = df_precios.with_columns(pl.col("fecha_iso").str.to_date()).drop_nulls()
    df_salarios = df_salarios.with_columns(pl.col("fecha_iso").str.to_date()).drop_nulls()
    df_empleo = df_empleo.with_columns(pl.col("fecha_iso").str.to_date()).drop_nulls()

    # B) Filtrado para la Capa de Oro 1: IPC General
    df_ipc_general = df_precios.filter(
        (pl.col("categoria_gasto") == "IPC General") & 
        (pl.col("indicador").str.contains("Indice"))
    ).sort("fecha_iso")

    # C) UNIÓN (Join): Cruzamos salarios con el IPC General por fecha
    df_unido = df_salarios.join(df_ipc_general, on="fecha_iso", how="inner")

    # D) COLUMNA CALCULADA: Ratio Poder Adquisitivo 
    df_analisis = df_unido.with_columns(
        (pl.col("valor_salario") / pl.col("valor_ipc")).alias("ratio_poder_adquisitivo")
    )

    # F) RELACIÓN EMPLEO-SALARIOS: Cruzamos datos para el informe de Paro y Salarios
    df_paro = df_empleo.filter(pl.col("indicador_empleo") == "Tasa_Paro")
    df_relacion_paro = df_analisis.join(df_paro, on=["fecha_iso", "sexo"], how="inner")

    return df_ipc_general, df_relacion_paro

# GENERACIÓN DE DATASETS (CAPA ORO)
def generar_informes_csv(df_ipc, df_relacion):
    print(f"{amarillo}3. Exportando datasets a data_output/...{reset}")
    # Archivos CSV requeridos
    df_ipc.write_csv(f"{OUTPUT_DIR}/Evolucion_IPC_Nacional.csv")
    df_relacion.write_csv(f"{OUTPUT_DIR}/Relacion_Paro_Salarios.csv")
    
    # Ampliación Opcional: Parquet (Formato Big Data)
    df_ipc.write_parquet(f"{OUTPUT_DIR}/Evolucion_IPC_Nacional.parquet")

# ANÁLISIS VISUAL
def crear_visualizaciones(df_ipc, df_relacion):
    print(f"{amarillo}4. Generando gráficos con Plotly...{reset}")
    
    # Usamos la columna 'valor_ipc' que definimos en la query AS
    fig_linea = px.line(
        df_ipc.to_pandas(), 
        x="fecha_iso", 
        y="valor_ipc", 
        title="Impacto de la Inflación: Evolución del IPC General",
        labels={"valor_ipc": "Índice (Base 2021)", "fecha_iso": "Mes"}
    )
    fig_linea.write_html(f"{VIS_DIR}/graficos_interactivos_ipc.html")

    # Scatter Plot: Correlación entre Paro y Salario (Requisito de análisis de dos variables)
    fig_scatter = px.scatter(
        df_relacion.to_pandas(),
        x="valor_empleo",
        y="valor_salario",
        color="sector_cnae",
        title="Relación entre Tasa de Paro y Salarios Brutos",
        labels={"valor_empleo": "Tasa de Paro (%)", "valor_salario": "Salario (Euros)"}
    )
    fig_scatter.write_html(f"{VIS_DIR}/correlacion_paro_salario.html")

    # Gráfico Facetado: Comparativa de poder adquisitivo por sexo y sector
    fig_facetado = px.line(
        df_relacion.to_pandas(),
        x="fecha_iso",
        y="ratio_poder_adquisitivo",
        facet_col="sexo",
        color="sector_cnae",
        title="Evolución del Poder Adquisitivo: Comparativa por Sexo y Sector"
    )
    fig_facetado.write_html(f"{VIS_DIR}/poder_adquisitivo_facetado.html")

    print(f"\n{turquesa}Gráficos generados correctamente.{reset}")


def main():
    try:
        precios_raw, salarios_raw, empleo_raw = cargar_datos()
        ipc_oro, relacion_oro = procesar_informacion(precios_raw, salarios_raw, empleo_raw)
        
        generar_informes_csv(ipc_oro, relacion_oro)
        crear_visualizaciones(ipc_oro, relacion_oro)
        
        print(f"{lima}\n¡¡PROCESO COMPLETADO CON ÉXITO!!.{reset}")
    except Exception as e:
        print(f"{rojo}\nERROR: {e}{reset}")

if __name__ == "__main__":
    main()
