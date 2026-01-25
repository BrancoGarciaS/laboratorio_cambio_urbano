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
from datetime import datetime

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
METADATA_FILE = VECTOR_DIR / "metadata.txt"

# Crear carpetas necesarias
VECTOR_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Reiniciar metadatos
with open(METADATA_FILE, "w", encoding="utf-8") as f:
    f.write(f"METADATOS DE VECTORES\n")
    f.write(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("="*50 + "\n\n")

# ==============================================================================
# UTILIDADES
# ==============================================================================
def normalize(text: str) -> str:
    if text is None: return ""
    text = str(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.upper().strip()

def cleanup_temp(force_create=False):
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        if force_create:
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"⚠️ No se pudo manipular carpeta temp: {e}")

def log_metadata(filename, source, description):
    """Registra la info en metadata.txt"""
    with open(METADATA_FILE, "a", encoding="utf-8") as f:
        f.write(f"Archivo: {filename}\n")
        f.write(f" - Fuente: {source}\n")
        f.write(f" - Descripción: {description}\n")
        f.write(f" - CRS: EPSG:32719 (WGS 84 / UTM zone 19S)\n")
        f.write("-" * 30 + "\n")

# ==============================================================================
# MÓDULO 1: LÍMITES COMUNALES
# ==============================================================================
def download_limites():
    output_file = VECTOR_DIR / "limite_comuna.gpkg"
    if output_file.exists():
        print("✅ [IDE] Límite comunal ya existe. Saltando...")
        log_metadata("limite_comuna.gpkg", "IDE Chile / GeoPortal", "División Político Administrativa (DPA) 2020")
        return

    print("\n🔵 Iniciando descarga de LÍMITES COMUNALES...")

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
        log_metadata("limite_comuna.gpkg", "IDE Chile / GeoPortal", "División Político Administrativa (DPA) 2020")
        return True

    # --- Intento 1: Directo IDE ---
    try:
        print("   1️⃣  Intento IDE Chile Directo...")
        cleanup_temp(force_create=True)
        zip_temp_path = TEMP_DIR / "dpa_temp.zip"
        
        r = requests.get(URL_DPA_DIRECTA, stream=True, timeout=60)
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))
        
        with open(zip_temp_path, 'wb') as f, tqdm(total=total_size, unit='iB', unit_scale=True, desc="Descargando") as bar:
            for chunk in r.iter_content(chunk_size=8192):
                size = f.write(chunk)
                bar.update(size)

        with zipfile.ZipFile(zip_temp_path, 'r') as z:
            z.extractall(TEMP_DIR)
        
        zip_temp_path.unlink()
        if procesar_shp(TEMP_DIR): return

    except Exception as e:
        print(f"   ❌ Falló IDE Directo: {e}")

    # --- Intento 2: Google Drive ---
    try:
        print("   2️⃣  Intento Google Drive (Respaldo)...")
        cleanup_temp(force_create=True)
        gdown.download_folder(url=URL_DPA_DRIVE, output=str(TEMP_DIR), quiet=False, use_cookies=False)
        for z in TEMP_DIR.rglob("*.zip"):
            with zipfile.ZipFile(z, 'r') as zf: zf.extractall(TEMP_DIR)
        if procesar_shp(TEMP_DIR): return
    except Exception as e:
        print(f"   ❌ Falló Drive: {e}")

    # --- Intento 3: OSM ---
    try:
        print("   3️⃣  Intento OpenStreetMap (Fallback)...")
        gdf = ox.geocode_to_gdf(f"{COMUNA_OBJETIVO}, Chile")
        gdf = gdf.to_crs("EPSG:32719")
        drop_cols = [c for c in gdf.columns if isinstance(gdf[c].iloc[0], list)]
        gdf.drop(columns=drop_cols).to_file(output_file, driver="GPKG")
        print(f"   ✨ Guardado (OSM) en: {output_file.name}")
        log_metadata("limite_comuna.gpkg", "OpenStreetMap", "Geocode Fallback")
    except Exception as e:
        print(f"   💥 FATAL: No se pudo descargar límites. Error: {e}")

# ==============================================================================
# MÓDULO 2: MANZANAS CENSALES
# ==============================================================================
def download_censo():
    output_file = VECTOR_DIR / "manzanas_censales.shp"
    if output_file.exists():
        print("✅ [INE] Manzanas censales ya existen. Saltando...")
        log_metadata("manzanas_censales.shp", "INE / API ArcGIS", "Censo 2017 - Manzanas")
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
                log_metadata("manzanas_censales.shp", "INE / API ArcGIS", "Censo 2017 - Manzanas")
                return
        except Exception as e:
            print(f"   ⚠️ Error parcial: {e}")
    print("   💥 FATAL: No se pudieron descargar manzanas.")

# ==============================================================================
# MÓDULO 3: RED VIAL
# ==============================================================================
def download_red_vial():
    output_file = VECTOR_DIR / "red_vial.geojson"
    if output_file.exists():
        print("✅ [OSM] Red vial ya existe. Saltando...")
        log_metadata("red_vial.geojson", "OpenStreetMap (OSMnx)", "Red vial (drive)")
        return

    print("\n🔵 Iniciando descarga de RED VIAL (OSM)...")
    try:
        print(f"   🚗 Descargando calles de '{COMUNA_OBJETIVO}'...")
        graph = ox.graph_from_place(f"{COMUNA_OBJETIVO}, Chile", network_type="drive")
        gdf_edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)
        # Aseguramos proyección UTM para metadata consistente
        if gdf_edges.crs.to_string() != "EPSG:32719":
             gdf_edges = gdf_edges.to_crs("EPSG:32719")
             
        gdf_edges.to_file(output_file, driver="GeoJSON")
        print(f"   ✨ Guardado en: {output_file.name}")
        log_metadata("red_vial.geojson", "OpenStreetMap (OSMnx)", "Red vial (drive)")
    except Exception as e:
        print(f"   ❌ Error descargando red vial: {e}")

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=str, default="all")
    args = parser.parse_args()
    mode = args.sources.lower()
    
    print(f"🚀 Ejecutando descarga de vectores. Modo: {mode.upper()}")
    
    if mode == "all" or mode == "ide": download_limites()
    if mode == "all" or mode == "ine": download_censo()
    if mode == "all" or mode == "osm": download_red_vial()
        
    cleanup_temp(force_create=False)
    print(f"\n🏁 Proceso finalizado. Metadatos en: {METADATA_FILE}")