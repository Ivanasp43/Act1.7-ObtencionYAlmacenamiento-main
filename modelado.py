# colores
magenta = '\033[95m'
amarillo = '\033[93m'
turquesa = '\033[38;5;44m'
lima = '\33[38;5;46m'
reset = '\033[0m'

import polars as pl
import pandas as pd
import sqlite3
import os
import numpy as np
import plotly.express as px
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.cluster import KMeans
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error, silhouette_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder

DB_PATH = "proyecto_datos.db"
VIS_DIR = "visualizaciones_modelado"

os.makedirs(VIS_DIR, exist_ok=True)

# CARGA DE DATOS (Versión ultra-robusta contra errores de esquema)
def cargar_datos():
    print(f"{amarillo}\nCargando datos con limpieza profunda...{reset}")
    conn = sqlite3.connect(DB_PATH)

    # Forzamos que fecha_iso sea tratada como texto desde la base de datos
    query = """
    SELECT CAST(s.valor AS FLOAT) AS salario, 
           CAST(s.sector_cnae AS TEXT) AS sector_cnae, 
           CAST(s.sexo AS TEXT) AS sexo, 
           CAST(g.nombre AS TEXT) AS comunidad,
           CAST(t.fecha_iso AS TEXT) AS fecha_iso
    FROM T_salarios s
    INNER JOIN tbl_periodo t ON s.id_periodo = t.id_periodo
    INNER JOIN tbl_geografia g ON s.id_geografia = g.id_geografia
    WHERE s.sector_cnae IS NOT NULL 
      AND s.sexo != 'Total' 
      AND t.fecha_iso IS NOT NULL
      AND t.fecha_iso != ''
    """
    
    # Cargamos y eliminamos cualquier rastro de nulos antes de transformar
    df = pl.read_database(query=query, connection=conn).drop_nulls()
    conn.close()

    # Ahora sí extraemos el año y el sexo numérico de forma segura
    df = df.with_columns([
        pl.col("fecha_iso").str.slice(0, 4).cast(pl.Int32).alias("anio"),
        pl.when(pl.col("sexo") == "Hombres").then(0).otherwise(1).alias("sexo_num")
    ])

    print(f"{lima}Dataset cargado correctamente. Filas listas: {df.shape[0]}{reset}")
    return df

# PROCESADO DE CATEGORÍAS
def preparar_variables_ia(df):
    data = df.to_pandas()
    encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    categoricas = ['sector_cnae', 'comunidad']
    X_encoded = encoder.fit_transform(data[categoricas])
    
    X = np.hstack([data[['anio', 'sexo_num']].values, X_encoded])
    y = data['salario'].values
    return X, y, encoder.get_feature_names_out(categoricas)

# MATRIZ DE CORRELACIÓN
def grafico_correlacion(df):
    print(f"{amarillo}Generando matriz de correlación...{reset}")
    df_pd = df.select(["salario", "sexo_num", "anio"]).to_pandas()
    corr = df_pd.corr()
    fig = px.imshow(corr, text_auto=True, title="Correlación: Salario, Sexo y Año")
    fig.write_html(f"{VIS_DIR}/correlacion.html")

# REGRESIÓN LINEAL MÚLTIPLE
def regresion_lineal(df):
    print(f"{turquesa}\nRegresión Lineal Múltiple{reset}")
    X, y, _ = preparar_variables_ia(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    modelo = LinearRegression()
    modelo.fit(X_train, y_train)
    pred = modelo.predict(X_test)

    print(f"{magenta}R2:{reset}", r2_score(y_test, pred))
    print(f"{magenta}MAE:{reset}", mean_absolute_error(y_test, pred))

    fig = px.scatter(x=y_test, y=pred, title="Regresión: Salario Real vs Predicho", labels={'x': 'Real', 'y': 'Predicho'})
    fig.write_html(f"{VIS_DIR}/regresion_lineal.html")

# RANDOM FOREST
def random_forest(df):
    print(f"{turquesa}\nRandom Forest Regressor{reset}")
    X, y, nombres_col = preparar_variables_ia(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    modelo = RandomForestRegressor(n_estimators=200, max_depth=10,min_samples_split=5, random_state=42, n_jobs=-1)
    modelo.fit(X_train, y_train)
    pred = modelo.predict(X_test)

    print(f"{magenta}R2 RandomForest:{reset}", r2_score(y_test, pred))
    
    todas_vars = ['anio', 'sexo_num'] + list(nombres_col)
    importancia = pd.DataFrame({"Var": todas_vars, "Imp": modelo.feature_importances_}).sort_values(by="Imp", ascending=False).head(10)
    
    fig = px.bar(importancia, x="Imp", y="Var", orientation='h', title="Top 10 Factores Determinantes")
    fig.write_html(f"{VIS_DIR}/random_forest_importancia.html")

# COMPARACIÓN DE MODELOS
def comparar_modelos(df):
    print(f"{turquesa}\nComparación de Modelos{reset}")
    X, y, _ = preparar_variables_ia(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    lr = LinearRegression().fit(X_train, y_train)
    rf = RandomForestRegressor(n_estimators=50, n_jobs=1, random_state=42).fit(X_train, y_train)

    r2_lr = r2_score(y_test, lr.predict(X_test))
    r2_rf = r2_score(y_test, rf.predict(X_test))

    print(f"{magenta}R2 Regresión Lineal:{reset}", r2_lr)
    print(f"{magenta}R2 RandomForest:{reset}", r2_rf)

    df_comp = pd.DataFrame({"Modelo": ["Regresión Lineal", "Random Forest"], "R2": [r2_lr, r2_rf]})
    fig = px.bar(df_comp, x="Modelo", y="R2", title="Comparativa R2")
    fig.write_html(f"{VIS_DIR}/comparacion_modelos.html")

# CLUSTERING
def clustering(df):
    print(f"{turquesa}\nClustering K-Means{reset}")
    df_pd = df.to_pandas()
    X = df_pd[["salario", "sexo_num", "anio"]]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    modelo = KMeans(n_clusters=4, n_init=10, random_state=42)
    clusters = modelo.fit_predict(X_scaled)

    df_pd["cluster"] = clusters

    score = silhouette_score(X_scaled, clusters)
    print(f"{magenta}Silhouette Score:{reset}", score)

    fig = px.scatter(df_pd, x="anio", y="salario", color="sexo", symbol="cluster", title="Clusters de Salarios")
    fig.write_html(f"{VIS_DIR}/clustering.html")

# MAIN
def main():
    df = cargar_datos()
    grafico_correlacion(df)
    regresion_lineal(df)
    random_forest(df)
    comparar_modelos(df)
    clustering(df)
    print(f"{lima}\nModelado completado con éxito. Puedes ver los gráficos en la carpeta:{reset} {VIS_DIR}")

if __name__ == "__main__":
    main()
