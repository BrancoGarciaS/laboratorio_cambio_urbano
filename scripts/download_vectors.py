import argparse
import requests
import geopandas as gpd
import osmnx as ox
import zipfile
import io
import shutil
import gdown
import unicodedata
import json
import warnings
from pathlib import Path
from tqdm import tqdm

# Ignorar advertencias
warnings.filterwarnings("ignore")

# ==============================================================================
# CONFIGURACIÓN GLOBAL
# ==============================================================================
COMUNA_OBJETIVO = "VIÑA DEL MAR"

# URLs
URL_DPA_DIRECTA = "https://www.geoportal.cl/geoportal/catalog/download/912598ad-ac92-35f6-8045-098f214bd9c2"
URL_DPA_DRIVE = "https://drive.google.com/drive/folders/10Gu5WlkQBlvkL25cpUQfOurOURu_MEov?usp=sharing"
URL_CENSO_API = "https://services5.arcgis.com/hUyD8u3TeZLKPe4T/arcgis/rest/services/Manzana_2017_2/FeatureServer/0"

# Rutas
SCRIPT_DIR = Path(__file__).parent.resolve()
VECTOR_DIR = SCRIPT_DIR.parent / "data" / "vector"
TEMP_DIR = VECTOR_DIR / "temp_download"

# Crear carpetas necesarias (TEMP se crea aquí, se usa y se borra al final)
VECTOR_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# UTILIDADES
# ==============================================================================
def normalize(text: str) -> str:
    """Normaliza texto (quita tildes, mayúsculas)"""
    if text is None: return ""
    text = str(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.upper().strip()

def cleanup_temp(force_create=False):
    """
    Limpia la carpeta temporal.
    Si force_create=True, la recrea vacía (útil para limpiar ANTES de usar).
    Si force_create=False, la elimina por completo (útil para limpiar AL FINAL).
    """
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        
        if force_create:
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            
    except Exception as e:
        print(f"⚠️ No se pudo manipular carpeta temp: {e}")

# ==============================================================================
# MÓDULO 1: LÍMITES COMUNALES (IDE / DRIVE / OSM)
# ==============================================================================
def download_limites():
    output_file = VECTOR_DIR / "limite_comuna.gpkg"
    if output_file.exists():
        print("✅ [IDE] Límite comunal ya existe. Saltando...")
        return

    print("\n🔵 Iniciando descarga de LÍMITES COMUNALES...")

    # --- Lógica interna para procesar shapefiles ---
    def procesar_shp(directorio):
        shapefiles = list(directorio.rglob("*OMUNA*.shp")) or list(directorio.rglob("*.shp"))
        if not shapefiles: raise FileNotFoundError("No hay .shp")
        
        shp = shapefiles[0]
        print(f"   📖 Leyendo: {shp.name}")
        gdf = gpd.read_file(shp)
        
        col_name = next((c for c in gdf.columns if c in ["COMUNA", "NOM_COM", "NOM_COMUNA"]), None)
        if not col_name: raise ValueError("Columna de nombre no encontrada")
        
        print(f"   🔍 Filtrando '{COMUNA_OBJETIVO}'...")
        gdf_vina = gdf[gdf[col_name].astype(str).str.contains(COMUNA_OBJETIVO, case=False, na=False)]
        
        if gdf_vina.empty: raise ValueError("Comuna no encontrada")
        
        if gdf_vina.crs.to_string() != "EPSG:32719":
            print("   🔄 Reproyectando a UTM 19S...")
            gdf_vina = gdf_vina.to_crs("EPSG:32719")
            
        gdf_vina.to_file(output_file, driver="GPKG")
        print(f"   ✨ Guardado en: {output_file.name}")
        return True

    # --- Intento 1: Directo IDE (CON BARRA DE PROGRESO) ---
    try:
        print("   1️⃣  Intento IDE Chile Directo...")
        cleanup_temp(force_create=True) # Asegurar carpeta limpia y existente
        zip_temp_path = TEMP_DIR / "dpa_temp.zip"
        
        r = requests.get(URL_DPA_DIRECTA, stream=True, timeout=60)
        r.raise_for_status()
        
        total_size = int(r.headers.get('content-length', 0))
        
        with open(zip_temp_path, 'wb') as f, tqdm(
            desc="   ⬇️  Descargando ZIP",
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in r.iter_content(chunk_size=8192):
                size = f.write(chunk)
                bar.update(size)

        print("   📦 Descomprimiendo...")
        with zipfile.ZipFile(zip_temp_path, 'r') as z:
            z.extractall(TEMP_DIR)
        
        zip_temp_path.unlink()

        if procesar_shp(TEMP_DIR): return

    except Exception as e:
        print(f"   ❌ Falló IDE Directo: {e}")

    # --- Intento 2: Google Drive (CON BARRA DE PROGRESO NATIVA) ---
    try:
        print("   2️⃣  Intento Google Drive (Respaldo)...")
        cleanup_temp(force_create=True) # Limpiar antes del intento 2
        
        gdown.download_folder(url=URL_DPA_DRIVE, output=str(TEMP_DIR), quiet=False, use_cookies=False)
        
        for z in TEMP_DIR.rglob("*.zip"):
            with zipfile.ZipFile(z, 'r') as zf: zf.extractall(TEMP_DIR)
            
        if procesar_shp(TEMP_DIR): return
    except Exception as e:
        print(f"   ❌ Falló Drive: {e}")

    # --- Intento 3: OSM (Fallback) ---
    try:
        print("   3️⃣  Intento OpenStreetMap (Fallback)...")
        gdf = ox.geocode_to_gdf(f"{COMUNA_OBJETIVO}, Chile")
        gdf = gdf.to_crs("EPSG:32719")
        drop_cols = [c for c in gdf.columns if isinstance(gdf[c].iloc[0], list)]
        gdf.drop(columns=drop_cols).to_file(output_file, driver="GPKG")
        print(f"   ✨ Guardado (OSM) en: {output_file.name}")
    except Exception as e:
        print(f"   💥 FATAL: No se pudo descargar límites. Error: {e}")

# ==============================================================================
# MÓDULO 2: MANZANAS CENSALES (INE)
# ==============================================================================
def download_censo():
    output_file = VECTOR_DIR / "manzanas_censales.shp"
    if output_file.exists():
        print("✅ [INE] Manzanas censales ya existen. Saltando...")
        return

    print("\n🔵 Iniciando descarga de MANZANAS CENSALES (INE)...")
    
    nombres = [COMUNA_OBJETIVO.upper(), normalize(COMUNA_OBJETIVO)]
    
    for nombre in nombres:
        print(f"   🔍 Buscando '{nombre}' en API ArcGIS...")
        params = {
            "where": f"UPPER(COMUNA) LIKE '{nombre}%'",
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "outSR": "4326"
        }
        
        try:
            r = requests.get(f"{URL_CENSO_API.rstrip('/')}/query", params=params, timeout=60)
            if r.status_code != 200: continue
            
            data = r.json()
            if data.get('features'):
                count = len(data['features'])
                print(f"   ✅ Encontradas {count} manzanas.")
                
                gdf = gpd.GeoDataFrame.from_features(data["features"])
                gdf.set_crs(epsg=4326, inplace=True)
                
                print("   🔄 Reproyectando a UTM 19S...")
                gdf = gdf.to_crs("EPSG:32719")
                
                gdf.to_file(output_file, driver="ESRI Shapefile")
                print(f"   ✨ Guardado en: {output_file.name}")
                return # Éxito
        except Exception as e:
            print(f"   ⚠️ Error parcial: {e}")
            
    print("   💥 FATAL: No se pudieron descargar manzanas.")

# ==============================================================================
# MÓDULO 3: RED VIAL (OSM)
# ==============================================================================
def download_red_vial():
    output_file = VECTOR_DIR / "red_vial.geojson"
    if output_file.exists():
        print("✅ [OSM] Red vial ya existe. Saltando...")
        return

    print("\n🔵 Iniciando descarga de RED VIAL (OSM)...")
    try:
        print(f"   🚗 Descargando calles de '{COMUNA_OBJETIVO}'...")
        graph = ox.graph_from_place(f"{COMUNA_OBJETIVO}, Chile", network_type="drive")
        gdf_edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)
        gdf_edges.to_file(output_file, driver="GeoJSON")
        print(f"   ✨ Guardado en: {output_file.name}")
    except Exception as e:
        print(f"   ❌ Error descargando red vial: {e}")


# ==============================================================================
# CONTROLADOR PRINCIPAL (ARGPARSE)
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script unificado de descarga de vectores.")
    
    parser.add_argument(
        "--sources", 
        type=str, 
        default="all", 
        help="Fuentes a descargar: 'all', 'ine' (censo), 'ide' (limites), 'osm' (vial)."
    )
    
    args = parser.parse_args()
    mode = args.sources.lower()
    
    print(f"🚀 Ejecutando descarga de vectores. Modo: {mode.upper()}")
    print(f"📍 Directorio: {VECTOR_DIR}\n")
    
    # Lógica de banderas
    if mode == "all" or mode == "ide":
        download_limites()
        
    if mode == "all" or mode == "ine":
        download_censo()
        
    if mode == "all" or mode == "osm":
        download_red_vial()
        
    # Limpieza final: Eliminar carpeta temp completamente
    cleanup_temp(force_create=False)
    print("\n🏁 Proceso finalizado.")