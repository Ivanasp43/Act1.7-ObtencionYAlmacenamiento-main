import streamlit as st
import polars as pl
import plotly.express as px
import sqlite3

# CONFIGURACIÓN INICIAL

st.set_page_config(
    page_title="Dashboard Socioeconómico",
    page_icon="📊",
    layout="wide"
)

# Estilo 
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        color: white;
    }

    /* Títulos Principales */
    .main-title {
        text-align: center;
        font-weight: 700;
        font-size: 3rem;
        color: #FFFFFF;
        margin-bottom: 0.1rem;
    }
    .sub-title {
        text-align: center;
        font-weight: 300;
        color: #E0E0E0;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }

    /* Tarjetas de KPI */
    [data-testid="stMetric"] {
        background-color: #000000 !important;
        border: 1px solid #333333;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }
    
    /* Textos de KPIs (Títulos y Valores) en Blanco */
    [data-testid="stMetricLabel"] div p, 
    [data-testid="stMetricLabel"] {
        color: #FFFFFF !important;
        font-size: 1.1rem !important;
    }

    div[data-testid="stMetricValue"] > div {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* Selectores (Inputs y Dropdowns) */
    div[data-baseweb="select"] > div {
        background-color: #1e1e1e !important;
        color: white !important;
        border-radius: 8px;
        border: 1px solid #555;
    }

    /* Etiquetas de los selectores en blanco */
    [data-testid="stWidgetLabel"] p {
        color: #FFFFFF !important;
        font-weight: 400;
    }
</style>
""", unsafe_allow_html=True)

DB_PATH = "proyecto_datos.db"


# CARGA Y PROCESAMIENTO 

@st.cache_data
def cargar_y_procesar():
    conn = sqlite3.connect(DB_PATH)

    # Queries 
    query_precios = """
    SELECT p.valor AS valor_ipc, p.categoria_gasto, t.fecha_iso, i.nombre as indicador
    FROM T_precios p
    JOIN tbl_periodo t ON p.id_periodo = t.id_periodo
    JOIN tbl_indicador i ON p.id_indicador = i.id_indicador
    """

    query_salarios = """
    SELECT s.valor AS valor_salario, s.sexo, s.sector_cnae, s.ocupacion_cno11,
           t.fecha_iso, i.nombre as indicador_salario, g.nombre as comunidad
    FROM T_salarios s
    JOIN tbl_periodo t ON s.id_periodo = t.id_periodo
    JOIN tbl_indicador i ON s.id_indicador = i.id_indicador
    JOIN tbl_geografia g ON s.id_geografia = g.id_geografia
    """

    query_empleo = """
    SELECT e.valor AS valor_empleo, e.sexo, t.fecha_iso, i.nombre as indicador_empleo
    FROM T_empleo e
    JOIN tbl_periodo t ON e.id_periodo = t.id_periodo
    JOIN tbl_indicador i ON i.id_indicador = e.id_indicador
    """

    df_precios = pl.read_database(query=query_precios, connection=conn)
    df_salarios = pl.read_database(query=query_salarios, connection=conn)
    df_empleo = pl.read_database(query=query_empleo, connection=conn)
    conn.close()

    # Limpieza 
    df_precios = df_precios.with_columns(pl.col("fecha_iso").str.to_date()).drop_nulls()
    df_salarios = df_salarios.with_columns(pl.col("fecha_iso").str.to_date()).drop_nulls()
    df_empleo = df_empleo.with_columns(pl.col("fecha_iso").str.to_date()).drop_nulls()

    df_precios = df_precios.filter(pl.col("valor_ipc") > 0)
    df_salarios = df_salarios.filter(pl.col("valor_salario") > 0)

    df_ipc_general = df_precios.filter(
        (pl.col("categoria_gasto") == "IPC General") &
        (pl.col("indicador").str.contains("Indice"))
    ).sort("fecha_iso")

    df_unido = df_salarios.join(df_ipc_general, on="fecha_iso", how="inner")
    df_analisis = df_unido.with_columns(
        (pl.col("valor_salario") / pl.col("valor_ipc")).alias("ratio_poder_adquisitivo")
    )

    df_paro = df_empleo.filter(pl.col("indicador_empleo") == "Tasa_Paro")
    df_relacion = df_analisis.join(df_paro, on=["fecha_iso", "sexo"], how="inner")

    return df_ipc_general, df_relacion

df_ipc, df_final = cargar_y_procesar()

# ===========================
# COORDENADAS PARA EL MAPA 
# ===========================
coords = {
    "Andalucía": [37.38, -5.98], "Aragón": [41.65, -0.88], "Asturias, Principado de": [43.36, -5.84],
    "Balears, Illes": [39.57, 2.65], "Canarias": [28.29, -16.62], "Cantabria": [43.46, -3.80],
    "Castilla y León": [41.65, -4.72], "Castilla - La Mancha": [39.86, -4.02], "Cataluña": [41.38, 2.17],
    "Comunitat Valenciana": [39.47, -0.37], "Extremadura": [38.92, -6.34], "Galicia": [42.87, -8.54],
    "Madrid, Comunidad de": [40.41, -3.70], "Murcia, Región de": [37.99, -1.13], "Navarra, Comunidad Foral de": [42.81, -1.64],
    "País Vasco": [42.84, -2.67], "Rioja, La": [42.46, -2.44], "Ceuta": [35.88, -5.31], "Melilla": [35.29, -2.93]
}

# Creamos un dataframe para el mapa
df_mapa = df_final.filter(pl.col("comunidad") != "Total Nacional").group_by("comunidad").agg([
    pl.col("valor_salario").mean().alias("Salario Medio"),
    pl.col("ratio_poder_adquisitivo").mean().alias("Poder Adquisitivo")
]).to_pandas()

df_mapa["lat"] = df_mapa["comunidad"].map(lambda x: coords.get(x, [None, None])[0])
df_mapa["lon"] = df_mapa["comunidad"].map(lambda x: coords.get(x, [None, None])[1])
df_mapa = df_mapa.dropna(subset=["lat"])


# TÍTULO Y KPIs 

st.markdown('<h1 class="main-title">Dashboard Socioeconómico Interactivo</h1>', unsafe_allow_html=True)
st.markdown('<h3 class="sub-title">Análisis de IPC, Salarios y Poder Adquisitivo en España</h3>', unsafe_allow_html=True)

# KPIs automáticos basados en tus datos
ultimo_ipc = df_ipc.sort("fecha_iso").tail(1)["valor_ipc"][0]
salario_avg = df_final["valor_salario"].mean()
paro_avg = df_final["valor_empleo"].mean()

k1, k2, k3 = st.columns(3)
k1.metric("IPC Actual", f"{ultimo_ipc:.2f}")
k2.metric("Salario Medio", f"{salario_avg:,.2f} €")
k3.metric("Tasa de Paro", f"{paro_avg:.2f} %")

st.markdown("---")

# ===============================
# SECCIÓN: MAPA DE DISTRIBUCIÓN
# ===============================
st.subheader("Distribución Geográfica de Salarios")

# Selector con etiquetas blancas
metrica_mapa = st.selectbox("Seleccionar métrica", ["Salario Medio", "Poder Adquisitivo"])

fig_mapa = px.scatter_mapbox(
    df_mapa,
    lat="lat",
    lon="lon",
    size="Salario Medio",
    color=metrica_mapa,
    hover_name="comunidad",
    color_continuous_scale=px.colors.sequential.Plasma_r,
    size_max=20,
    zoom=4.8,
    center={"lat": 40.41, "lon": -3.70},
    mapbox_style="carto-positron",          
    template="plotly_dark",
    height=600
)

# Ajustes de la leyenda
fig_mapa.update_layout(
    margin={"r":0, "t":0, "l":0, "b":0},
    coloraxis_colorbar=dict(
        title=dict(text=metrica_mapa, font=dict(color='white', size=14)),
        tickfont=dict(color='white', size=15),
        bgcolor="rgba(30,30,30,0.85)",
        bordercolor="gray",
        thickness=25,
        len=0.8
    )
)

# Hover más legible sobre fondo claro
fig_mapa.update_traces(
    hoverlabel=dict(
        bgcolor="rgba(0,0,0,0.8)",
        font=dict(color="white")
    )
)

st.plotly_chart(fig_mapa, use_container_width=True)

# ====================
# 1️ GRÁFICO IPC 
# ====================

st.subheader("Evolución Temporal del IPC")

años_ipc = sorted(df_ipc.select(pl.col("fecha_iso").dt.year()).unique().to_series().to_list())
opciones_ipc = ["Todos"] + años_ipc

años_sel_ipc = st.multiselect("Seleccionar año(s)", opciones_ipc, default=["Todos"], key="ipc_años")

if "Todos" in años_sel_ipc:
    df_ipc_filtrado = df_ipc
else:
    df_ipc_filtrado = df_ipc.filter(pl.col("fecha_iso").dt.year().is_in(años_sel_ipc))

fig1 = px.line(
    df_ipc_filtrado.to_pandas(),
    x="fecha_iso", y="valor_ipc",
    markers=True, template="plotly_dark",
    title="Evolución Temporal del IPC General (Base 2021)"
)

# Cambiar nombres de los ejes
fig1.update_layout(
    xaxis_title="FECHA",
    yaxis_title="IPC"
)
st.plotly_chart(fig1, use_container_width=True)

# =======================
# 2️ GRÁFICO SALARIOS
# =======================

st.subheader("Evolución del Salario Medio por Comunidad Autónoma")

col1, col2 = st.columns(2)
años_sal = sorted(df_final.select(pl.col("fecha_iso").dt.year()).unique().to_series().to_list())
comunidades = sorted(df_final.filter(pl.col("comunidad") != "Total Nacional").select("comunidad").unique().to_series().to_list())

años_sel_sal = col1.multiselect("Seleccionar año(s)", ["Todos"] + años_sal, default=["Todos"], key="sal_años")
com_sel = col2.multiselect("Seleccionar Comunidad(es) Autónoma(s)", ["Todos"] + comunidades, default=["Todos"], key="sal_comunidad")

df_sal_filtrado = df_final.filter(pl.col("comunidad") != "Total Nacional")
if "Todos" not in años_sel_sal:
    df_sal_filtrado = df_sal_filtrado.filter(pl.col("fecha_iso").dt.year().is_in(años_sel_sal))
if "Todos" not in com_sel:
    df_sal_filtrado = df_sal_filtrado.filter(pl.col("comunidad").is_in(com_sel))

# Agrupamos y ordenamos para que la línea se dibuje correctamente
df_sal_plot = (
    df_sal_filtrado
    .group_by(["fecha_iso", "comunidad"])
    .agg(pl.col("valor_salario").mean())
    .sort("fecha_iso")
    .to_pandas()
)

# Creamos la figura
fig2 = px.line(
    df_sal_plot, 
    x="fecha_iso", 
    y="valor_salario", 
    color="comunidad",
    markers=True, 
    template="plotly_dark",
    title="Tendencia del Salario Medio por Comunidad"
)

# Mejoras de legibilidad
fig2.update_traces(
    line=dict(width=2),      
    marker=dict(size=6)       
)

fig2.update_layout(
    xaxis_title="FECHA",
    yaxis_title="SALARIO MEDIO (€)",
    hovermode="x unified",     
    legend=dict(
        orientation="h", 
        y=-0.3,
        font=dict(size=10)
    )
)

st.plotly_chart(fig2, use_container_width=True)

# ================================
# 3️ GRÁFICO PODER ADQUISITIVO 
# ================================

st.subheader("Poder Adquisitivo Medio por Sector y Sexo")

col3, col4, col5 = st.columns(3)
sectores = sorted(df_final.filter((pl.col("sector_cnae") != "Total") & (pl.col("sector_cnae") != "N/A")).select("sector_cnae").unique().to_series().to_list())

años_sel_ratio = col3.multiselect("Seleccionar año(s)", ["Todos"] + años_sal, default=["Todos"], key="ratio_años")
sexo_sel = col4.multiselect("Seleccionar sexo(s)", ["Todos", "Hombres", "Mujeres"], default=["Todos"], key="ratio_sexo")
sector_sel = col5.multiselect("Seleccionar Sector(es)", ["Todos"] + sectores, default=["Todos"], key="ratio_sector")

# 1. Filtramos según la selección del usuario
df_ratio_filtrado = df_final.filter((pl.col("sector_cnae") != "Total") & (pl.col("sector_cnae") != "N/A"))

if "Todos" not in años_sel_ratio:
    df_ratio_filtrado = df_ratio_filtrado.filter(pl.col("fecha_iso").dt.year().is_in(años_sel_ratio))
if "Todos" not in sexo_sel:
    df_ratio_filtrado = df_ratio_filtrado.filter(pl.col("sexo").is_in(sexo_sel))
if "Todos" not in sector_sel:
    df_ratio_filtrado = df_ratio_filtrado.filter(pl.col("sector_cnae").is_in(sector_sel))

# PROCESAMIENTO: Aquí usamos TODOS los datos para calcular la media
# Al agrupar así, Polars procesa las miles de filas de la DB instantáneamente
df_resumen = (
    df_ratio_filtrado
    .group_by(["sector_cnae", "sexo"])
    .agg(pl.col("ratio_poder_adquisitivo").mean()) # <--- Aquí se incluyen todos los datos
    .sort("ratio_poder_adquisitivo", descending=True)
    .to_pandas()
)

# Creación del gráfico: Barras horizontales 
fig3 = px.bar(
    df_resumen, 
    y="sector_cnae", 
    x="ratio_poder_adquisitivo",
    color="sexo", 
    barmode="group",
    orientation='h', 
    template="plotly_dark",
    title="Ranking de Poder Adquisitivo por Sector (Media del periodo seleccionado)",
    color_discrete_map={"Hombres": "#1157B3", "Mujeres": "#AB73F0"}
)

fig3.update_layout(
    xaxis_title="RATIO PODER ADQUISITIVO (Promedio)",
    yaxis_title="",
    legend=dict(orientation="h", y=-0.2),
    height=600, 
    margin=dict(l=200) 
)

st.plotly_chart(fig3, use_container_width=True)