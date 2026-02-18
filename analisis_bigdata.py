import polars as pl
import plotly.express as px
import os
import sqlite3
import time 
import pandas as pd

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
    SELECT s.valor AS valor_salario, s.sexo, s.sector_cnae, s.ocupacion_cno11, t.fecha_iso, 
           i.nombre as indicador_salario, g.nombre as comunidad
    FROM T_salarios s
    JOIN tbl_periodo t ON s.id_periodo = t.id_periodo
    JOIN tbl_indicador i ON s.id_indicador = i.id_indicador
    JOIN tbl_geografia g ON s.id_geografia = g.id_geografia
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
    df_salarios = df_salarios.with_columns([
        pl.col("fecha_iso").str.to_date(),
        pl.col("sector_cnae").str.strip_chars() # Limpiamos espacios para evitar N/A falsos
    ]).drop_nulls()
    df_empleo = df_empleo.with_columns(pl.col("fecha_iso").str.to_date()).drop_nulls()
    
    
    # Filtrar valores negativos o basura antes de calcular
    df_precios = df_precios.filter(pl.col("valor_ipc") > 0)
    df_salarios = df_salarios.filter(pl.col("valor_salario") > 0)

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

# GENERACIÓN DE DATASETS
def generar_informes_csv(df_ipc, df_relacion):
    print(f"{amarillo}3. Exportando datasets y comparando formatos...{reset}")
    
    # 1. Definimos las rutas para poder medirlas luego
    csv_path = f"{OUTPUT_DIR}/Relacion_Paro_Salarios.csv"
    parquet_path = f"{OUTPUT_DIR}/Relacion_Paro_Salarios.parquet"

    # 2. Exportamos (Guardamos los archivos)
    df_relacion.write_csv(csv_path)
    df_relacion.write_parquet(parquet_path)
    df_ipc.write_csv(f"{OUTPUT_DIR}/Evolucion_IPC_Nacional.csv")
    df_ipc.write_parquet(f"{OUTPUT_DIR}/Evolucion_IPC_Nacional.parquet")

    # 3. INVESTIGACIÓN: Medimos peso en disco (KB)
    peso_csv = os.path.getsize(csv_path) / 1024
    peso_parquet = os.path.getsize(parquet_path) / 1024

    # 4. INVESTIGACIÓN: Medimos velocidad de lectura (segundos)
    t0_csv = time.time()
    pl.read_csv(csv_path)
    tiempo_csv = time.time() - t0_csv

    t0_pq = time.time()
    pl.read_parquet(parquet_path)
    tiempo_pq = time.time() - t0_pq

    # 5. MOSTRAMOS RESULTADOS EN CONSOLA
    print(f"\n{turquesa}📊 COMPARATIVA BIG DATA (CSV vs PARQUET):{reset}")
    print(f"📁 Peso: CSV {peso_csv:.2f} KB | Parquet {peso_parquet:.2f} KB")
    print(f"⏱️ Lectura: CSV {tiempo_csv:.4f}s | Parquet {tiempo_pq:.4f}s")
    
    ahorro = (1 - (peso_parquet / peso_csv)) * 100
    print(f"{lima}🚀 Resultado: Parquet ocupa un {ahorro:.1f}% menos.{reset}\n")

# COMPARACIÓN DE RENDIMIENTO ENTRE POLARS Y PANDAS EN UNA OPERACIÓN COMPLEJA 

def realizar_benchmarking(df_relacion):
    print(f"{amarillo}5. Realizando Benchmarking: Polars vs Pandas...{reset}")
    
    # Convertimos el DataFrame de Polars a Pandas para la comparativa
    df_pandas = df_relacion.to_pandas()
    
    # Operación compleja: Agrupar por sector y sexo, calcular media, max y min del ratio
    
    # --- MEDIDOR POLARS ---
    t0_polars = time.time()
    # En Polars las operaciones son perezosas o multihilo por defecto
    res_polars = df_relacion.group_by(["sector_cnae", "sexo"]).agg([
        pl.col("ratio_poder_adquisitivo").mean().alias("media"),
        pl.col("ratio_poder_adquisitivo").max().alias("max"),
        pl.col("ratio_poder_adquisitivo").std().alias("std")
    ])
    tiempo_polars = time.time() - t0_polars

    # --- MEDIDOR PANDAS ---
    t0_pandas = time.time()
    res_pandas = df_pandas.groupby(["sector_cnae", "sexo"])["ratio_poder_adquisitivo"].agg(
        ["mean", "max", "std"]
    )
    tiempo_pandas = time.time() - t0_pandas

    # --- RESULTADOS ---
    print(f"\n{turquesa}⏱️ COMPARATIVA DE RENDIMIENTO (Agregación Compleja):{reset}")
    print(f"⚡ Polars: {tiempo_polars:.6f} segundos")
    print(f"🐼 Pandas: {tiempo_pandas:.6f} segundos")
    
    if tiempo_polars < tiempo_pandas:
        mejora = (tiempo_pandas / tiempo_polars)
        print(f"{lima}🚀 Resultado: Polars es {mejora:.1f} veces más rápido que Pandas en esta operación.{reset}\n")
    else:
        print(f"{amarillo}Nota: Con datasets pequeños las diferencias son milimétricas.{reset}\n")

# ANÁLISIS VISUAL
def crear_visualizaciones(df_ipc, df_final):
    print(f"{amarillo}4. Generando los 3 gráficos analíticos sincronizados con el Dashboard...{reset}")

    # --- GRÁFICO 1: IPC (Línea) ---
    df_ipc_plot = df_ipc.sort("fecha_iso").to_pandas()
    fig1 = px.line(
        df_ipc_plot, 
        x="fecha_iso", y="valor_ipc",
        markers=True, template="plotly_dark",
        title="1. Evolución Temporal del IPC General (Base 2021)",
        labels={"valor_ipc": "IPC", "fecha_iso": "FECHA"}
    )
    fig1.write_html(f"{VIS_DIR}/1_evolucion_ipc.html")

    # --- GRÁFICO 2: SALARIOS (Líneas con Marcadores - Como el Dashboard final) ---
    df_sal_plot = (
        df_final.filter(pl.col("comunidad") != "Total Nacional")
        .group_by(["fecha_iso", "comunidad"])
        .agg(pl.col("valor_salario").mean())
        .sort("fecha_iso")
        .to_pandas()
    )
    
    fig2 = px.line(
        df_sal_plot, 
        x="fecha_iso", y="valor_salario", color="comunidad",
        markers=True, template="plotly_dark",
        title="2. Tendencia del Salario Medio por Comunidad Autónoma",
        labels={"valor_salario": "SALARIO MEDIO (€)", "fecha_iso": "FECHA"}
    )
    fig2.update_layout(legend=dict(orientation="h", y=-0.3, font=dict(size=10)))
    fig2.write_html(f"{VIS_DIR}/2_salario_comunidades.html")

    # --- GRÁFICO 3: PODER ADQUISITIVO (Barras Horizontales - El cambio clave) ---
    # Aplicamos la misma lógica de "resumen" para evitar archivos pesados o bloqueos
    df_resumen = (
        df_final.filter((pl.col("sector_cnae") != "Total") & (pl.col("sector_cnae") != "N/A"))
        .group_by(["sector_cnae", "sexo"])
        .agg(pl.col("ratio_poder_adquisitivo").mean())
        .sort("ratio_poder_adquisitivo", descending=True)
        .to_pandas()
    )

    fig3 = px.bar(
        df_resumen, 
        y="sector_cnae", x="ratio_poder_adquisitivo",
        color="sexo", barmode="group",
        orientation='h', template="plotly_dark",
        title="3. Ranking de Poder Adquisitivo por Sector y Sexo",
        color_discrete_map={"Hombres": "#9B5DE5", "Mujeres": "#00F5D4"}, # Colores Morado y Turquesa
        labels={"ratio_poder_adquisitivo": "RATIO PODER ADQUISITIVO (Promedio)", "sector_cnae": "SECTOR"}
    )

    fig3.update_layout(
        legend=dict(orientation="h", y=-0.2),
        height=700, 
        margin=dict(l=200) 
    )
    fig3.write_html(f"{VIS_DIR}/3_poder_adquisitivo_barras.html")

    print(f"\n{turquesa}Gráficos del script sincronizados con el Dashboard.{reset}")


def main():
    try:
        precios_raw, salarios_raw, empleo_raw = cargar_datos()
        ipc_oro, relacion_oro = procesar_informacion(precios_raw, salarios_raw, empleo_raw)
        
        generar_informes_csv(ipc_oro, relacion_oro)
        crear_visualizaciones(ipc_oro, relacion_oro)

        realizar_benchmarking(relacion_oro)
        
        print(f"{lima}\n¡¡PROCESO COMPLETADO CON ÉXITO!!.{reset}")
    except Exception as e:
        print(f"{rojo}\nERROR: {e}{reset}")

if __name__ == "__main__":
    main()
