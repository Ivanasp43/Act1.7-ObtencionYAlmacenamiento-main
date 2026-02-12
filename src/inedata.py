import requests
import json

INE_BASE_URL = "https://servicios.ine.es/wstempus/jsCache/ES/DATOS_TABLA/"

class INEDataExtractor:
    def __init__(self, codigo_tabla):
        self.codigo_tabla = codigo_tabla
        self.raw_data = None
        self.esquema = None

    def obtener_datos(self):
        url = f"{INE_BASE_URL}{self.codigo_tabla}"
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            
            respuesta = r.json()
            
            if isinstance(respuesta, list):
                self.raw_data = respuesta
            else:
                self.raw_data = [respuesta] # Asegurar que siempre sea una lista

            return True
        

        except Exception as e:
            print(f"[{self.codigo_tabla}] Error en obtención: {e}")
            self.raw_data = None
            return False

    # Para inspeccionar la estructura de la tabla
    def _tipo_simple(self, valor):
        if isinstance(valor, bool): return "BOOLEAN"
        elif isinstance(valor, int): return "INTEGER"
        elif isinstance(valor, float): return "FLOAT"
        elif isinstance(valor, str): return "STRING"
        elif valor is None: return "NULL"
        else: return "UNKNOWN"

    def _esquema(self, data=None):
        if data is None:
            data = self.raw_data[0] if isinstance(self.raw_data, list) else self.raw_data
        esquema = {}
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    esquema[k] = {"type": "OBJECT", "fields": self._esquema(v)}
                elif isinstance(v, list) and v:
                    esquema[k] = {"type": "ARRAY", "element_type": self._esquema(v[0])}
                elif isinstance(v, list):
                    esquema[k] = {"type": "ARRAY (empty)"}
                else:
                    esquema[k] = {"type": self._tipo_simple(v)}
        elif isinstance(data, list) and data:
             esquema = self._esquema(data[0])
        return esquema
    def generar_esquema(self):
        if self.raw_data is None:
            self.obtener_datos()
        if self.raw_data:
            self.esquema = self._esquema(self.raw_data[0])
        return self.esquema
    
    def imprimir_esquema(self):
        if self.esquema is None:
            self.generar_esquema()
        print(json.dumps(self.esquema, indent=4, ensure_ascii=False))
