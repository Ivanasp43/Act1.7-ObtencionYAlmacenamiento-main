#Creación Base de Datos

# colores
rojo = '\033[91m'
amarillo = '\033[93m'
turquesa = '\033[38;5;44m'
reset = '\033[0m'

import sqlite3
from contextlib import contextmanager

DB_NAME = 'proyecto_datos.db'

class DatabaseConnection:
    _instance = None
    _connection = None

    def __new__(cls):
        """Implementa el patrón Singleton (asegura que solo se cree una instancia)"""
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            # Inicializar la conexion la primera vez que se llama a la instancia
            cls._instance.connect()

        return cls._instance
    
    def connect(self):
        """Establece la conexion a la base de datos"""
        if self._connection is None:
            try:
                self._connection = sqlite3.connect(DB_NAME)
            except sqlite3.Error as e:
                print(f"Error al conectar a la BD: {e}")
                self._connection = None

    def get_connection(self):
        """Devuelve el objeto de conexion"""
        if self._connection is None:
            self.connect()
        return self._connection
    
    def close(self):
        """Cierra la conexion"""
        if self._connection:
            self._connection.close()
            self._connection = None # Resetea oara permitir una nueva conexion si es necesario
    

@contextmanager
def get_cursor():
    """
    Proporciona un cursor para realizar operaciones de BD, 
    gestionando automáticamente el commit o rollback.
    """
    conn = DatabaseConnection().get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()  # Si todo sale bien, guarda los cambios
    except Exception as e:
        conn.rollback() # Si hay un error, revierte
        print(f"Operación de base de datos fallida: {e}")
        raise
    
    
def crear_base_datos():
    with get_cursor() as cursor:

        # --------------------------------------------------------------
        # TABLAS DE DIMENSIONES (LOOKUPS)
        # --------------------------------------------------------------


        # TABLA PERIODO
        # Antes teníamos tablas separadas por frecuencia (mensual, trimestral).
        # Se eliminó esa estructura porque hacía más difícil combinar datos.
        # Ahora existe un único lookup con flexibilidad para IPC (mensual),
        # IPV (trimestral), ETCL (trimestral) y EES (anual).
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tbl_periodo (
            id_periodo INTEGER PRIMARY KEY,
            anio INTEGER NOT NULL,
            trimestre INTEGER, -- NULL si es mensual o anual
            mes INTEGER, -- NULL si es trimestral o anual
            fecha_iso TEXT NOT NULL UNIQUE -- YYYY-MM-DD 
        );
        """)
        print(f"\n{turquesa}Tabla{reset} {amarillo}'tbl_periodo'{reset}{turquesa} creada o ya existente.{reset}")

        # TABLA INDICADOR
        # Sustituye tablas antiguas como tbl_ipc, tbl_ipv, tbl_paro...
        # El objetivo es permitir una tabla de hechos unificada.
        # Ejemplos de indicadores:
        # IPC_General, IPC_Alimentos, IPV_Nueva, IPV_Usada,
        # Coste_Salarial_Total (ETCL), Mediana_Salarial (EES), Tasa_Paro...
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tbl_indicador (
            id_indicador INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL UNIQUE, -- Ej: 'IPC_Gral', 'Paro_Juvenil', 'Salario_Mediana'
            unidad TEXT                        -- Ej: '%', 'Euros', 'Índice Base 100'
        );
        """)
        print(f"\n{turquesa}Tabla{reset} {amarillo}'tbl_indicador'{reset}{turquesa} creada o ya existente.{reset}")
        
        # 3. Dimensión Geografía 
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tbl_geografia (
            id_geografia INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL UNIQUE
        );
        """)
        print(f"\n{turquesa}Tabla{reset} {amarillo}'tbl_geografia'{reset}{turquesa} creada o ya existente.{reset}")


        # --------------------------------------------------------------
        # TABLAS DE HECHOS (ALMACENAN VALORES MULTIDIMENSIONALES)
        # --------------------------------------------------------------

        # TABLA T_precios
        # NOTA SOBRE CAMBIOS:
        # Antes existía una tabla específica para IPC.
        # Se eliminó y se unificó con el IPV porque ambos son
        # índices de precios: solo cambia la frecuencia.
        # Aquí se registran:
        # * IPC (mensual)
        # * IPV (trimestral)
        # Campos comentados/eliminados:
        # - No añadimos "tipo_indice" porque ya lo define tbl_indicador.
        # - No usamos "id_geografia" normalizada para no complicar
        # la carga masiva; se usa texto libre.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS T_precios (
            id_precio INTEGER PRIMARY KEY,
            id_periodo INTEGER NOT NULL,
            id_indicador INTEGER NOT NULL,
            id_geografia INTEGER NOT NULL,
            categoria_gasto TEXT NOT NULL, -- IPC: alimentos, vivienda... IPV: nueva, usada...
            valor REAL NOT NULL,

            FOREIGN KEY (id_periodo) REFERENCES tbl_periodo(id_periodo),
            FOREIGN KEY (id_indicador) REFERENCES tbl_indicador(id_indicador),
            FOREIGN KEY (id_geografia) REFERENCES tbl_geografia(id_geografia),
                       
            UNIQUE(id_periodo, id_indicador, id_geografia, categoria_gasto)
        );
        """)
        print(f"{turquesa}Tabla {reset}{amarillo}'T_precios'{reset}{turquesa} creada o ya existente.{reset}")

        
        # TABLA T_salarios
        # NOTA SOBRE CAMBIOS:
        # Antes existían una sola tabla: EES.
        # Se eliminó y se unificó con ETCL porque ambas representan salarios brutos.
        # Esta tabla integra:
        # * ETCL (trimestral, con CNAE)
        # * EES (anual, con CNO11)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS T_salarios (
            id_salario INTEGER PRIMARY KEY,
            id_periodo INTEGER NOT NULL,
            id_indicador INTEGER NOT NULL,      -- Coste salarial total, Mediana, P10, etc.
            id_geografia INTEGER NOT NULL,
            
            sexo TEXT,                          -- Ambos, Hombres, Mujeres
            sector_cnae TEXT,                   -- Sector de Actividad (solo en ETCL)
            ocupacion_cno11 TEXT,               -- Ocupación (solo en EES)
            
            valor REAL NOT NULL,               -- Salario en euros

            FOREIGN KEY (id_periodo) REFERENCES tbl_periodo(id_periodo),
            FOREIGN KEY (id_indicador) REFERENCES tbl_indicador(id_indicador),
            FOREIGN KEY (id_geografia) REFERENCES tbl_geografia(id_geografia),
            
            UNIQUE(id_periodo, id_indicador, id_geografia, sexo, sector_cnae, ocupacion_cno11)        
        );
        """)
        print(f"{turquesa}Tabla{reset}{amarillo} 'T_salarios'{reset}{turquesa} creada o ya existente.{reset}")
        

        # TABLA T_empleo
        # NOTA SOBRE CAMBIOS:
        # Antes existía una tabla solo para tasa de paro.
        # Se amplió para almacenar también:
        # * Absolutos del 65132 (asalariados totales, temporales, indefinidos)
        # * Temporalidad (%), calculado o directamente cargado

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS T_empleo (
            id_empleo INTEGER PRIMARY KEY,
            id_periodo INTEGER NOT NULL,
            id_indicador INTEGER NOT NULL, -- Tasa Paro, Total Asalariados, Temporalidad %
            id_geografia INTEGER NOT NULL,

            sexo TEXT NOT NULL,
            grupo_edad TEXT,                     -- 16-24, 25-54, etc.
            tipo_jornada TEXT,                   -- Completa, Parcial
            tipo_contrato TEXT,                  -- Indefinido, Temporal
                        
            valor REAL NOT NULL,                 -- El dato numérico (Tasa o Miles de Personas)

            FOREIGN KEY (id_periodo) REFERENCES tbl_periodo(id_periodo),
            FOREIGN KEY (id_indicador) REFERENCES tbl_indicador(id_indicador),
            FOREIGN KEY (id_geografia) REFERENCES tbl_geografia(id_geografia), 
            
            UNIQUE(id_periodo, id_indicador, id_geografia, sexo, grupo_edad, tipo_jornada, tipo_contrato)
        );
        """)
        print(f"{turquesa}Tabla{reset}{amarillo} 'T_empleo'{reset}{turquesa} creada o ya existente.{reset}")
        
    print(f"\n{turquesa}Base de Datos lista. Faltan las funciones de precarga.{reset}")
