import streamlit as st
import polars as pl
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Dashboard Económico", layout="wide")

st.title("📊 Análisis de Poder Adquisitivo y Empleo")
st.markdown("""
Esta aplicación muestra los resultados del procesamiento de datos de Big Data utilizando **Polars** y **Plotly**.
""")

# --- CARGA DE DATOS ---
@st.cache_data # Para que la web cargue rápido
def load_data():
    df_ipc = pl.read_parquet("data_output/Evolucion_IPC_Nacional.parquet")
    df_relacion = pl.read_parquet("data_output/Relacion_Paro_Salarios.parquet")
    return df_ipc, df_relacion

df_ipc, df_relacion = load_data()

# --- SIDEBAR (Filtros interactivos) ---
st.sidebar.header("Filtros")
sector = st.sidebar.multiselect(
    "Selecciona Sector:",
    options=df_relacion["sector_cnae"].unique().to_list(),
    default=df_relacion["sector_cnae"].unique().to_list()[0]
)

# Filtrar datos según selección
df_filtrado = df_relacion.filter(pl.col("sector_cnae").is_in(sector))

# --- DISEÑO DEL DASHBOARD ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Evolución del IPC")
    fig1 = px.line(df_ipc.to_pandas(), x="fecha_iso", y="valor_ipc", title="Índice de Precios")
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Relación Paro vs Salario")
    fig2 = px.scatter(df_filtrado.to_pandas(), x="valor_empleo", y="valor_salario", 
                     color="sexo", title="Correlación por Género")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# Gráfico de ancho completo
st.subheader("Análisis del Poder Adquisitivo")
fig3 = px.line(df_filtrado.to_pandas(), x="fecha_iso", y="ratio_poder_adquisitivo", 
              color="sector_cnae", facet_col="sexo")
st.plotly_chart(fig3, use_container_width=True)

# Mostrar tabla de datos si el usuario quiere
if st.checkbox("Mostrar tabla de datos brutos"):
    st.dataframe(df_filtrado.to_pandas())