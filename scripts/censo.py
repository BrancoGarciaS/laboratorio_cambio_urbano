import requests
import geopandas as gpd
from pathlib import Path
import unicodedata
import warnings
import json

# Ignorar advertencias
warnings.filterwarnings("ignore")

# ==============================================================================
# CONFIGURACIÓN (Extraída de tu script)
# ==============================================================================
# Esta es la URL que traía tu script (diferente a las anteriores)
CENSO_URL = "https://services5.arcgis.com/hUyD8u3TeZLKPe4T/arcgis/rest/services/Manzana_2017_2/FeatureServer/0"

COMUNA_OBJETIVO = "VIÑA DEL MAR"

# Rutas
script_location = Path(__file__).parent.resolve()
vector_dir = script_location.parent / "data" / "vector"
output_file = vector_dir / "manzanas_censales.shp"
vector_dir.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# FUNCIONES AUXILIARES (De tu script)
# ==============================================================================
def normalize(text: str) -> str:
    """Normaliza texto para comparaciones robustas (quita tildes)."""
    if text is None: return ""
    text = str(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.upper().strip()

# ==============================================================================
# LÓGICA DE DESCARGA
# ==============================================================================
def descargar_manzanas():
    print(f"📍 Directorio de salida: {vector_dir}")
    print(f"🌍 Conectando a API (URL de tu script): {CENSO_URL}...")
    
    # Normalizamos el nombre para la búsqueda (VIÑA -> VINA)
    # A veces las bases de datos guardan "VINA DEL MAR" o "VIÑA DEL MAR"
    nombres_a_probar = [
        COMUNA_OBJETIVO.upper(),          # VIÑA DEL MAR
        normalize(COMUNA_OBJETIVO)        # VINA DEL MAR
    ]
    
    success = False
    
    for nombre in nombres_a_probar:
        print(f"🔍 Intentando buscar comuna como: '{nombre}'...")
        
        # Query SQL para la API
        params = {
            "where": f"UPPER(COMUNA) LIKE '{nombre}%'",
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "outSR": "4326"
        }
        
        try:
            # Petición a la API
            query_url = CENSO_URL.rstrip('/') + '/query'
            r = requests.get(query_url, params=params, timeout=60)
            
            if r.status_code != 200:
                print(f"   ❌ Error HTTP {r.status_code}")
                continue
                
            try:
                data = r.json()
            except json.JSONDecodeError:
                print("   ❌ La respuesta no es un JSON válido.")
                continue

            # Verificar si trajo datos
            if 'features' in data and len(data['features']) > 0:
                count = len(data['features'])
                print(f"   ✅ ¡Encontrado! Descargadas {count} manzanas.")
                
                # Convertir a GeoDataFrame
                gdf = gpd.GeoDataFrame.from_features(data["features"])
                gdf.set_crs(epsg=4326, inplace=True)
                
                # Reproyectar a UTM 19S (Requisito del lab)
                print("   🔄 Reproyectando a UTM 19S (EPSG:32719)...")
                gdf = gdf.to_crs("EPSG:32719")
                
                # Guardar como Shapefile
                gdf.to_file(output_file, driver="ESRI Shapefile")
                print(f"   ✨ Archivo guardado en: {output_file}")
                success = True
                break # Terminar el bucle si tuvo éxito
            else:
                print(f"   ⚠️ La consulta funcionó pero trajo 0 resultados para '{nombre}'.")
                
        except Exception as e:
            print(f"   ❌ Error técnico: {e}")

    if not success:
        print("\n💥 FATAL: No se pudo descargar automáticamente.")
        print("👉 Plan B: Usa el botón 'Exportar a GeoJSON' del mapa web y usa el script 'convert_geojson.py'.")

if __name__ == "__main__":
    descargar_manzanas()