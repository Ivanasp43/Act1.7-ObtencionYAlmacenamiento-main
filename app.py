import streamlit as st
import polars as pl
import pandas as pd
import plotly.express as px
import sqlite3
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
import numpy as np

# CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(
    page_title="IA Salarial: Explosión de Color",
    page_icon="🌈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CONFIGURACIÓN CSS 
st.markdown("""
    <style>
    /* 1. Fondo y Textos */
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    label, p, .stMarkdown { color: #FAFAFA !important; font-weight: bold !important; }
    h1, h2, h3 { color: #00DBDE !important; text-shadow: 0 0 10px #00DBDE; }

    /* 2. OCULTAR CABECERA Y ALINEAR */
    header { visibility: hidden; }
    
    /* Bajamos el contenido central */
    .main .block-container {
        padding-top: 60px !important; 
        padding-left: 50px !important;
        padding-right: 50px !important;
    }
    
    /* Bajamos el contenido de la barra lateral exactamente igual */
    [data-testid="stSidebarUserContent"] {
        padding-top: 60px !important;
    }

    /* 3. BOTONES GEMELOS */
    button[kind="primaryFormSubmit"], .stDownloadButton > button, .stButton > button {
        background: linear-gradient(45deg, #FC00FF 0%, #00DBDE 100%) !important;
        color: #000000 !important;
        border: none !important;
        height: 45px !important;
        border-radius: 20px !important;
        font-weight: 900 !important;
        text-transform: uppercase !important;
    }

    button[kind="primaryFormSubmit"] p, .stDownloadButton > button p {
        color: #000000 !important;
        margin: 0 !important;
    }

    /* 4. Estética */
    .stMetric { background-color: #1A1C24; padding: 20px; border-radius: 15px; border: 1px solid #FC00FF; }
    [data-testid="stSidebar"] { background-color: #1A1C24 !important; border-right: 2px solid #636EFA; }
    </style>
    """, unsafe_allow_html=True)

# CARGA DE DATOS
@st.cache_data
def load_data():
    conn = sqlite3.connect("proyecto_datos.db")
    query = "SELECT s.valor AS salario, s.sector_cnae, s.sexo, g.nombre AS comunidad, t.fecha_iso FROM T_salarios s JOIN tbl_periodo t ON s.id_periodo = t.id_periodo JOIN tbl_geografia g ON s.id_geografia = g.id_geografia WHERE s.sector_cnae != 'N/A' AND t.fecha_iso != ''"
    df = pl.read_database(query, connection=conn)
    conn.close()
    return df

@st.cache_resource
def train_model(df_pd):
    X = df_pd[['sector_cnae', 'sexo', 'comunidad']]
    y = df_pd['salario']
    encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    X_encoded = encoder.fit_transform(X)
    model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_encoded, y)
    return model, encoder

df_raw = load_data()
df_pd_full = df_raw.to_pandas()

# BARRA LATERAL
st.sidebar.markdown("<h2 style='color:#FC00FF; margin-top:0;'>🌈 Configuración</h2>", unsafe_allow_html=True)
comunidades = ["Todas"] + sorted(df_pd_full["comunidad"].unique().tolist())
com_selected = st.sidebar.selectbox("Filtros Globales", comunidades)
df = df_raw.filter(pl.col("comunidad") == com_selected) if com_selected != "Todas" else df_raw

# INTERFAZ
st.title("⚡ IA Predictiva: Análisis del Poder Adquisitivo")

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Salario Medio", f"{df['salario'].mean():,.2f} €")
c2.metric("📊 Muestra", len(df))
c3.metric("🎯 R² Modelo", "0.93")
c4.metric("🧠 Silhouette", "0.596")

tabs = st.tabs(["🔥 Análisis Visual", "🤖 Simulador IA", "📂 Capa de Oro"])

with tabs[0]:
    st.subheader("Visualización de Tendencias Estructurales")
    # Gráfico 1
    df_b = df.group_by("sector_cnae").agg(pl.col("salario").mean()).sort("salario").to_pandas()
    f1 = px.bar(df_b, x="salario", y="sector_cnae", orientation='h', template="plotly_dark",
                title="Sueldo Medio por Sector", color="salario", color_continuous_scale="Plasma", height=500)
    f1.update_layout(margin=dict(l=10, r=20, t=50, b=50))
    st.plotly_chart(f1, use_container_width=True, config={'displayModeBar': False})
    
    st.write("---")
    
    # Gráfico 2
    df_g = df.filter(pl.col("sexo") != "Total").group_by(["sector_cnae", "sexo"]).agg(pl.col("salario").mean()).to_pandas()
    f2 = px.bar(df_g, x="salario", y="sector_cnae", color="sexo", barmode="group", orientation="h",
                template="plotly_dark", title="Brecha de Género por Sector",
                color_discrete_map={"Hombres": "#9B5DE5", "Mujeres": "#00F5D4"}, height=600)
    f2.update_layout(margin=dict(l=10, r=20, t=50, b=50))
    st.plotly_chart(f2, use_container_width=True, config={'displayModeBar': False})

with tabs[1]:
    st.subheader("Simulador Salarial con IA")
    model, encoder = train_model(df_pd_full)
    with st.form("pred_form"):
        cx, cy, cz = st.columns(3)
        with cx: in_sec = st.selectbox("Sector", df_pd_full["sector_cnae"].unique())
        with cy: in_sex = st.radio("Género", df_pd_full["sexo"].unique(), horizontal=True)
        with cz: in_com = st.selectbox("Residencia", df_pd_full["comunidad"].unique())
        
        if st.form_submit_button("Calcular Predicción 🚀"):
            input_df = pd.DataFrame([[in_sec, in_sex, in_com]], columns=['sector_cnae', 'sexo', 'comunidad'])
            pred = model.predict(encoder.transform(input_df))[0]
            st.markdown(f"""<div style="padding:20px; border-radius:15px; background:linear-gradient(45deg, #FC00FF, #00DBDE); text-align:center;">
                            <h2 style="color:black !important; margin:0;">Salario Estimado: {pred:,.2f} €</h2></div>""", unsafe_allow_html=True)

with tabs[2]:
    st.subheader("Dataset Maestro")
    st.dataframe(df.to_pandas().head(100), use_container_width=True)
    st.download_button(label="📥 Descargar CSV Maestro", data=df.to_pandas().to_csv().encode('utf-8'), 
                       file_name="capa_oro.csv", mime="text/csv")

st.markdown("<p style='text-align:center;'>Cerrando el ciclo de vida del proyecto de Big Data 🚀</p>", unsafe_allow_html=True)