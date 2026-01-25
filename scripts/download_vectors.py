import os
import requests
import zipfile
import io
import shutil
import gdown
import osmnx as ox
import geopandas as gpd
from pathlib import Path
import warnings

# Ignorar advertencias
warnings.filterwarnings("ignore")

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
COMUNA_OBJETIVO = "Viña del Mar"
# Opción 1: Enlace directo IDE Chile
URL_DIRECTA = "https://www.geoportal.cl/geoportal/catalog/download/912598ad-ac92-35f6-8045-098f214bd9c2"
# Opción 2: Tu Carpeta en Google Drive (ID extraído de tu enlace)
DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/10Gu5WlkQBlvkL25cpUQfOurOURu_MEov?usp=sharing"

# Rutas
script_location = Path(__file__).parent.resolve()
vector_dir = script_location.parent / "data" / "vector"
temp_dir = vector_dir / "temp_download"
output_file = vector_dir / "limite_comuna.gpkg"

# Crear carpetas
vector_dir.mkdir(parents=True, exist_ok=True)
temp_dir.mkdir(parents=True, exist_ok=True)

print(f"📍 Directorio de salida: {vector_dir}")

# ==============================================================================
# LÓGICA DE PROCESAMIENTO (Común para Opción 1 y 2)
# ==============================================================================
def procesar_shapefile_descargado(directorio_busqueda):
    """Busca el shapefile de comunas en el directorio y extrae Viña del Mar."""
    print("   Consumer: Buscando shapefiles descargados...")
    
    # Buscar recursivamente cualquier archivo que parezca ser el de comunas
    # Buscamos "COMUNA" o "comuna" en el nombre
    shapefiles = list(directorio_busqueda.rglob("*OMUNA*.shp"))
    
    if not shapefiles:
        # Si no encuentra por nombre, intenta buscar cualquier .shp
        shapefiles = list(directorio_busqueda.rglob("*.shp"))
    
    if not shapefiles:
        raise FileNotFoundError("No se encontraron archivos .shp en la descarga.")

    archivo_shp = shapefiles[0]
    print(f"   📖 Leyendo: {archivo_shp.name}")
    
    gdf = gpd.read_file(archivo_shp)
    
    # Identificar columna de nombre
    columna_nombre = None
    possible_cols = ["COMUNA", "Comuna", "NOM_COM", "NOM_COMUNA"]
    for col in gdf.columns:
        if col in possible_cols:
            columna_nombre = col
            break
            
    if not columna_nombre:
        raise ValueError(f"No se encontró columna de nombre. Columnas: {gdf.columns.tolist()}")

    # Filtrar Viña
    print(f"   🔍 Filtrando '{COMUNA_OBJETIVO}'...")
    gdf_vina = gdf[gdf[columna_nombre].astype(str).str.contains(COMUNA_OBJETIVO, case=False, na=False)]

    if gdf_vina.empty:
        raise ValueError(f"La comuna '{COMUNA_OBJETIVO}' no está en el archivo.")

    # Reproyectar a UTM 19S
    if gdf_vina.crs and gdf_vina.crs.to_string() != "EPSG:32719":
        print("   🔄 Reproyectando a UTM 19S (EPSG:32719)...")
        gdf_vina = gdf_vina.to_crs("EPSG:32719")

    # Guardar
    gdf_vina.to_file(output_file, driver="GPKG")
    print(f"   ✨ ¡Éxito! Archivo guardado en: {output_file}")
    return True

# ==============================================================================
# OPCIÓN 1: DESCARGA DIRECTA (IDE CHILE)
# ==============================================================================
def opcion_1_directa():
    print("\n1️⃣  INTENTO 1: Descarga directa desde IDE Chile...")
    try:
        r = requests.get(URL_DIRECTA, stream=True, timeout=60) # Timeout de 60s
        r.raise_for_status()
        
        print("   ⬇️  Descargando ZIP (esto puede tardar)...")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(temp_dir)
        print("   📦 Descompresión lista.")
        
        return procesar_shapefile_descargado(temp_dir)
        
    except Exception as e:
        print(f"   ❌ Falló Opción 1: {e}")
        return False

# ==============================================================================
# OPCIÓN 2: GOOGLE DRIVE (TU RESPALDO)
# ==============================================================================
def opcion_2_drive():
    print("\n2️⃣  INTENTO 2: Descarga desde Google Drive (Respaldo)...")
    try:
        # Limpiar temp por si acaso
        for item in temp_dir.iterdir():
            if item.is_dir(): shutil.rmtree(item)
            else: item.unlink()
            
        print(f"   ⬇️  Descargando carpeta desde Drive...")
        # Descarga la carpeta completa
        gdown.download_folder(url=DRIVE_FOLDER_URL, output=str(temp_dir), quiet=False, use_cookies=False)
        
        # A veces descarga un ZIP dentro de la carpeta, o los archivos sueltos
        # Si hay zips dentro, los descomprimimos
        for zip_file in temp_dir.rglob("*.zip"):
            print(f"   📦 Descomprimiendo zip interno: {zip_file.name}")
            with zipfile.ZipFile(zip_file, 'r') as z:
                z.extractall(temp_dir)
        
        return procesar_shapefile_descargado(temp_dir)

    except Exception as e:
        print(f"   ❌ Falló Opción 2: {e}")
        return False

# ==============================================================================
# OPCIÓN 3: OPENSTREETMAP (FALLBACK FINAL)
# ==============================================================================
def opcion_3_osm():
    print("\n3️⃣  INTENTO 3: Descarga desde OpenStreetMap (OSM)...")
    try:
        print(f"   🌍 Consultando API de OSM para '{COMUNA_OBJETIVO}'...")
        gdf_boundary = ox.geocode_to_gdf(f"{COMUNA_OBJETIVO}, Chile")
        
        print("   🔄 Reproyectando a UTM 19S...")
        gdf_boundary = gdf_boundary.to_crs("EPSG:32719")
        
        # Limpieza de columnas complejas
        cols_to_drop = [c for c in gdf_boundary.columns if isinstance(gdf_boundary[c].iloc[0], list)]
        gdf_boundary = gdf_boundary.drop(columns=cols_to_drop)

        gdf_boundary.to_file(output_file, driver="GPKG")
        print(f"   ✨ ¡Éxito! Límite (OSM) guardado en: {output_file}")
        return True
        
    except Exception as e:
        print(f"   ❌ Falló Opción 3: {e}")
        return False

# ==============================================================================
# FUNCIÓN: RED VIAL (BONUS) - SIEMPRE SE EJECUTA
# ==============================================================================
def descargar_red_vial():
    vial_file = vector_dir / "red_vial.geojson"
    if vial_file.exists():
        print("\n✅ Red vial ya existe. Saltando...")
        return

    print(f"\n🚗 Descargando Red Vial (Bonus) de OSM...")
    try:
        graph = ox.graph_from_place(f"{COMUNA_OBJETIVO}, Chile", network_type="drive")
        gdf_nodes, gdf_edges = ox.graph_to_gdfs(graph)
        gdf_edges.to_file(vial_file, driver="GeoJSON")
        print(f"   ✨ Red vial guardada en: {vial_file}")
    except Exception as e:
        print(f"   ❌ Error en red vial: {e}")

# ==============================================================================
# EJECUCIÓN PRINCIPAL
# ==============================================================================
if __name__ == "__main__":
    exito = False
    
    # 1. Intentar IDE Chile
    if not exito:
        exito = opcion_1_directa()
    
    # 2. Intentar Drive
    if not exito:
        exito = opcion_2_drive()
        
    # 3. Intentar OSM
    if not exito:
        exito = opcion_3_osm()
        
    if not exito:
        print("\n💥 FATAL: Todas las opciones fallaron. Revisa tu conexión.")
    else:
        # Limpieza final de temporales
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
            
    # Siempre intentar bajar la red vial (es otro archivo)
    descargar_red_vial()
    
    print("\n🏁 Proceso finalizado.")