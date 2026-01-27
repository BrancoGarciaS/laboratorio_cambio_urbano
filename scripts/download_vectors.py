# =============================================================================
# SCRIPT: download_vectors.py
# =============================================================================
# Descripción: Descarga y procesa datos vectoriales geoespaciales (shapefiles, geojson, gpkg)
#              para la comuna objetivo (Viña del Mar). Incluye descarga desde APIs, OpenStreetMap y Google Drive.
#              Este script registra los metadatos técnicos de los vectores descargados.
#
# Uso: python scripts/download_vectors.py
# =============================================================================
# Librerías
import argparse        # Para manejar argumentos de línea de comandos para controlar el flujo del script
import requests        # Para realizar solicitudes HTTP para descargar datos desde APIs y URLs
import geopandas as gpd # Para procesar datos vectoriales geoespaciales (shapefile, geojson, gpkg)
import osmnx as ox     # Para descargar y manipular datos geográficos de OpenStreetMap (límites, calles)
import zipfile         # Para leer y extraer archivos comprimidos ZIP
import io              # Para manejar flujos de datos en memoria (bytes, buffers)
import shutil          # Para operaciones de alto nivel sobre archivos y carpetas (copiar, borrar)
import gdown           # Para descargar archivos y carpetas directamente desde Google Drive
import unicodedata     # Para normalizar texto Unicode (eliminar tildes, acentos, caracteres especiales)
import json            # Para manejar datos en formato JSON (lectura y escritura)
import warnings        # Para controlar y filtrar mensajes de advertencia de librerías
from pathlib import Path # Para el manejo moderno y multiplataforma de rutas de archivos
from tqdm import tqdm  # Para mostrar barras de progreso en bucles largos (descargas)
from datetime import datetime # Para el manejo de fechas y horas para registro de metadatos

# Ignorar advertencias
warnings.filterwarnings("ignore")

# 1) Configuración global
COMUNA_OBJETIVO = "VIÑA DEL MAR"

# URLs
URL_DPA_DIRECTA = "https://www.geoportal.cl/geoportal/catalog/download/912598ad-ac92-35f6-8045-098f214bd9c2" # Descarga directa de DPA
URL_DPA_DRIVE = "https://drive.google.com/drive/folders/10Gu5WlkQBlvkL25cpUQfOurOURu_MEov?usp=sharing" # Respaldo en Drive
URL_CENSO_API = "https://services5.arcgis.com/hUyD8u3TeZLKPe4T/arcgis/rest/services/Manzana_2017_2/FeatureServer/0" # API del Censo 2017

# Rutas
SCRIPT_DIR = Path(__file__).parent.resolve() # Carpeta del script actual
VECTOR_DIR = SCRIPT_DIR.parent / "data" / "vector" # Carpeta de salida para vectores
TEMP_DIR = VECTOR_DIR / "temp_download" # Carpeta temporal para descargas intermedias
METADATA_FILE = VECTOR_DIR / "metadata.txt" # Archivo de metadatos

# Crear carpetas necesarias
VECTOR_DIR.mkdir(parents=True, exist_ok=True) # Crear carpeta de vectores si no existe
TEMP_DIR.mkdir(parents=True, exist_ok=True) # Crear carpeta temporal si no existe

# Reiniciar metadatos, para que no se sobreescriban con ejecuciones anteriores
with open(METADATA_FILE, "w", encoding="utf-8") as f: # Abrir en modo escritura (sobrescribe)
    f.write(f"METADATOS DE VECTORES\n")
    f.write(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n") # Fecha y hora de generación
    f.write("="*50 + "\n\n")


# 2) Funciones de utilidad
def normalize(text: str) -> str:
    """
    Descripción: Función que normaliza un texto eliminando acentos y convirtiéndolo a mayúsculas.
                 Es crucial para comparar nombres de comunas (ej: "Viña" vs "Vina").

    Entradas:
        text (str): Texto de entrada.

    Salidas:
        str: Texto normalizado (mayúsculas sin tildes).
    """
    if text is None: return "" # Si el texto es None, retornar cadena vacía
    text = str(text) # Asegurar que es string
    # Descompone caracteres unicode (ej: 'ñ' -> 'n' + '~')
    text = unicodedata.normalize("NFKD", text)
    # Filtra los caracteres combinados (tildes) y une el string
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.upper().strip() # Retorna texto en mayúsculas y sin espacios extra

def cleanup_temp(force_create=False):
    """
    Descripción: Función que limpia el directorio temporal para evitar residuos de descargas anteriores.

    Entradas:
        force_create (bool): Si es True, vuelve a crear la carpeta vacía después de borrarla.
    """
    try:
        # Borra el árbol de directorios temporal si existe
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        # Vuelve a crear la carpeta limpia si se requiere
        if force_create:
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e: # En caso de error, indicar que no se pudo manipular la carpeta
        print(f"No se pudo manipular carpeta temp: {e}")

def log_metadata(filename, source, description):
    """
    Descripción: Función que registra la información técnica del archivo descargado en metadata.txt.

    Entradas:
        filename (str): Nombre del archivo vectorial.
        source (str): Fuente de los datos (ej: IDE Chile, INE).
        description (str): Breve descripción del contenido del archivo.
    
    Salidas:
        None: Solo registra la información en el archivo de metadatos.
    """
    with open(METADATA_FILE, "a", encoding="utf-8") as f:
        f.write(f"Archivo: {filename}\n") # Nombre del archivo
        f.write(f" - Fuente: {source}\n") # Fuente de los datos
        f.write(f" - Descripción: {description}\n") # Descripción del contenido
        # Registro el CRS estándar del proyecto
        f.write(f" - CRS: EPSG:32719 (WGS 84 / UTM zone 19S)\n")
        f.write("-" * 30 + "\n")

# ==============================================================================
# Módulo 1: Descarga de Límites Comunales (IDE Chile)
# ==============================================================================
def download_limites():
    """
    Descripción: Descarga el polígono del límite comunal. Implementa 3 estrategias de fallback:
                 1. Descarga directa desde GeoPortal (IDE Chile).
                 2. Respaldo en Google Drive.
                 3. Geocodificación con OpenStreetMap (OSMnx).
    
    Salidas: None: Genera archivo 'limite_comuna.gpkg'
    """
    output_file = VECTOR_DIR / "limite_comuna.gpkg" # Archivo de salida para el límite comunal
    # Verifica si el archivo ya existe para evitar trabajo duplicado
    if output_file.exists():
        print("✔ [IDE] Límite comunal ya existe. Saltando...") # Indica que el archivo ya existe
        log_metadata("limite_comuna.gpkg", "IDE Chile / GeoPortal", "División Político Administrativa (DPA) 2020")
        return
    # Inicia el proceso de descarga
    print("\n➤ Iniciando descarga de LÍMITES COMUNALES...")

    # Función para buscar y procesar el shapefile correcto en el directorio
    def procesar_shp(directorio):
        """
            Descripción: Función interna para buscar, filtrar y guardar el Shapefile correcto desde una carpeta.
            Entradas:
                directorio (Path): Carpeta donde buscar los archivos shapefile.
            Salidas:
                bool: True si se encontró y guardó el shapefile correctamente, False en caso contrario
        """
        # Busca archivos .shp recursivamente
        shapefiles = list(directorio.rglob("*OMUNA*.shp")) or list(directorio.rglob("*.shp"))
        if not shapefiles: raise FileNotFoundError("No hay .shp") # Si no hay shapefiles, lanza error
        # Toma el primer shapefile encontrado
        shp = shapefiles[0]
        print(f"   Leyendo: {shp.name}")
        gdf = gpd.read_file(shp) # Carga el vector en memoria
        # Busca dinámicamente la columna del nombre de la comuna
        col_name = next((c for c in gdf.columns if c in ["COMUNA", "NOM_COM", "NOM_COMUNA"]), None)
        # Si no se encuentra la columna, lanza error
        if not col_name: raise ValueError("Columna de nombre no encontrada")
        # Indica la columna usada para filtrar
        print(f"   Filtrando '{COMUNA_OBJETIVO}'...")
        # Filtra el GeoDataFrame
        gdf_vina = gdf[gdf[col_name].astype(str).str.contains(COMUNA_OBJETIVO, case=False, na=False)]
        # Si no se encuentra la comuna en el shapefile, lanza error
        if gdf_vina.empty: raise ValueError("Comuna no encontrada")
        # Reproyecta a UTM 19S (EPSG:32719) para estandarizar coordenadas métricas
        if gdf_vina.crs.to_string() != "EPSG:32719":
            print("    Reproyectando a UTM 19S...")
            gdf_vina = gdf_vina.to_crs("EPSG:32719")
        # Guarda el resultado en formato GeoPackage
        gdf_vina.to_file(output_file, driver="GPKG")
        print(f"   ✔ Guardado en: {output_file.name}")
        log_metadata("limite_comuna.gpkg", "IDE Chile / GeoPortal", "División Político Administrativa (DPA) 2020")
        return True # Se retorna true, como completado exitosamente

    # 1. Descarga directa desde GeoPortal (IDE Chile).
    try:
        print("   1)  Intento IDE Chile Directo...")
        cleanup_temp(force_create=True) # Limpia y crea carpeta temporal
        zip_temp_path = TEMP_DIR / "dpa_temp.zip"
        # Petición HTTP con stream para barra de progreso
        r = requests.get(URL_DPA_DIRECTA, stream=True, timeout=60)
        r.raise_for_status() # Lanza error si la respuesta no es 200 OK
        total_size = int(r.headers.get('content-length', 0)) # Tamaño total para la barra de progreso
        # Escritura del archivo por chunks
        with open(zip_temp_path, 'wb') as f, tqdm(total=total_size, unit='iB', unit_scale=True, desc="Descargando") as bar:
            # Escritura en chunks de 8KB
            for chunk in r.iter_content(chunk_size=8192):
                size = f.write(chunk) # Escribe el chunk en el archivo
                bar.update(size) # Actualiza la barra de progreso
        # Descompresión del ZIP descargado
        with zipfile.ZipFile(zip_temp_path, 'r') as z:
            z.extractall(TEMP_DIR) # Extrae todo el contenido en la carpeta temporal
        # Procesa el shapefile extraído
        zip_temp_path.unlink() # Borrar ZIP
        if procesar_shp(TEMP_DIR): return # Si se procesa correctamente, termina la función

    except Exception as e:
        print(f"   ✘ Falló IDE Directo: {e}")

    # 2. Descarga desde Google Drive (Respaldo)
    try:
        print("   2)  Intento Google Drive (Respaldo)...")
        cleanup_temp(force_create=True) # Limpia y crea carpeta temporal
        # Descarga carpeta drive usando librería gdown
        gdown.download_folder(url=URL_DPA_DRIVE, output=str(TEMP_DIR), quiet=False, use_cookies=False)
        # Descomprime todos los zips encontrados
        for z in TEMP_DIR.rglob("*.zip"):
            with zipfile.ZipFile(z, 'r') as zf: zf.extractall(TEMP_DIR) # Extrae todo el contenido en la carpeta temporal
        if procesar_shp(TEMP_DIR): return # Si se procesa correctamente, termina la función
    except Exception as e:
        print(f"   ✘ Falló Drive: {e}")

    # 3. Intento OpenStreetMap (Fallback)
    try: # Descarga usando OSMnx
        print("   3)  Intento OpenStreetMap (Fallback)...")
        # Geocodificación inversa
        gdf = ox.geocode_to_gdf(f"{COMUNA_OBJETIVO}, Chile")
        gdf = gdf.to_crs("EPSG:32719") # Reproyectar a UTM 19S
        # Limpieza de columnas complejas incompatibles con GPKG
        drop_cols = [c for c in gdf.columns if isinstance(gdf[c].iloc[0], list)]
        # Guardar resultado como GeoPackage
        gdf.drop(columns=drop_cols).to_file(output_file, driver="GPKG")
        print(f"   ✔ Guardado (OSM) en: {output_file.name}")
        log_metadata("limite_comuna.gpkg", "OpenStreetMap", "Geocode Fallback")
    except Exception as e:
        print(f"   ✘ ERROR: No se pudo descargar límites. Error: {e}")

# ==============================================================================
# Módulo 2: Descarga de manzanas censales (INE)
# ==============================================================================
def download_censo():
    """
    Descripción: Descarga las manzanas censales (Censo 2017) desde la API de ArcGIS del INE.
                 Filtra por nombre de comuna y reproyecta a UTM 19S.
    
    Salidas: None: Genera archivo 'manzanas_censales.shp'
    """
    output_file = VECTOR_DIR / "manzanas_censales.shp" # Archivo de salida para manzanas censales
    # Verifica si el archivo ya existe para evitar trabajo duplicado
    if output_file.exists(): # Si el archivo ya existe, salta la descarga
        print("✔ [INE] Manzanas censales ya existen. Saltando...")
        log_metadata("manzanas_censales.shp", "INE / API ArcGIS", "Censo 2017 - Manzanas")
        return
    # Inicia el proceso de descarga
    print("\n➤ Iniciando descarga de MANZANAS CENSALES (INE)...")
    # Probar variaciones del nombre (con/sin tildes) para la API
    nombres = [COMUNA_OBJETIVO.upper(), normalize(COMUNA_OBJETIVO)]
    # Por cada variación del nombre de la ciudad, intentar descargar
    for nombre in nombres:
        print(f"    Buscando '{nombre}' en API ArcGIS...") # Busca el nombre en la API (Viña del Mar)
        # Configuración de la consulta REST API
        params = {
            "where": f"UPPER(COMUNA) LIKE '{nombre}%'", # Filtro SQL
            "outFields": "*", # Todos los campos
            "returnGeometry": "true", # Incluir geometría
            "f": "geojson", # Formato de retorno
            "outSR": "4326" # CRS de salida WGS84
        }
        try: # Realiza la solicitud HTTP GET
            # Solicitud a la API
            r = requests.get(f"{URL_CENSO_API.rstrip('/')}/query", params=params, timeout=60)
            if r.status_code != 200: continue # Si no es 200 OK, continua
            # Procesa la respuesta JSON
            data = r.json()
            if data.get('features'): # Si hay características en la respuesta
                count = len(data['features']) # Cuenta cuántas manzanas se descargaron
                print(f"   ✔ Encontradas {count} manzanas.")
                # Crea GeoDataFrame desde JSON
                gdf = gpd.GeoDataFrame.from_features(data["features"])
                gdf.set_crs(epsg=4326, inplace=True) # Establece CRS WGS84
                # Reproyecta a UTM 19S (EPSG:32719)
                print("    Reproyectando a UTM 19S...")
                gdf = gdf.to_crs("EPSG:32719")
                # Guarda como Shapefile
                gdf.to_file(output_file, driver="ESRI Shapefile")
                print(f"   ✔ Guardado en: {output_file.name}") # Mensaje de éxito
                log_metadata("manzanas_censales.shp", "INE / API ArcGIS", "Censo 2017 - Manzanas")
                return
        except Exception as e: # En caso de error, indica el problema
            print(f"    Error parcial: {e}")
    print("   ✘ ERROR: No se pudieron descargar manzanas.")

# ==============================================================================
# Módulo 3: Descarga de Red Vial (OpenStreetMap)
# ==============================================================================
def download_red_vial():
    """
    Descripción: Descarga la red vial transitable (calles) usando OpenStreetMap (OSMnx).
                 Y guarda el resultado como GeoJSON.
    
    Salidas: None: Genera archivo 'red_vial.geojson'
    """
    output_file = VECTOR_DIR / "red_vial.geojson" # Archivo de salida para la red vial
    if output_file.exists(): # Si el archivo ya existe, salta la descarga
        print("✔ [OSM] Red vial ya existe. Saltando...")
        log_metadata("red_vial.geojson", "OpenStreetMap (OSMnx)", "Red vial (drive)")
        return

    print("\n➤ Iniciando descarga de RED VIAL (OSM)...")
    try: # Intenta descargar la red vial de Viña del Mar
        print(f"    Descargando calles de '{COMUNA_OBJETIVO}'...")
        # Descarga el grafo de calles tipo 'drive' (vehículos)
        graph = ox.graph_from_place(f"{COMUNA_OBJETIVO}, Chile", network_type="drive")
        # Convierte el grafo en GeoDataFrame
        gdf_edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)
        # Asegurar proyección UTM
        if gdf_edges.crs.to_string() != "EPSG:32719":
             gdf_edges = gdf_edges.to_crs("EPSG:32719")
        # Guarda como GeoJSON
        gdf_edges.to_file(output_file, driver="GeoJSON")
        print(f"   ✔ Guardado en: {output_file.name}") # Mensaje de éxito
        log_metadata("red_vial.geojson", "OpenStreetMap (OSMnx)", "Red vial (drive)")
    except Exception as e: # En caso de error, indica problema
        print(f"   ✘ Error descargando red vial: {e}")

# ==============================================================================
# MAIN
# Comandos de descarga:
# - Descarga todos los datos (por defecto): python scripts/download_vectors.py
# - Descarga todos los datos: python scripts/download_vectors.py --sources all
# - Solo límites comunales: python scripts/download_vectors.py --sources ide
# - Solo manzanas censales: python scripts/download_vectors.py --sources ine
# - Solo red vial: python scripts/download_vectors.py --sources osm
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser() # Inicializa el parser de argumentos
    # Argumento CLI para elegir qué fuentes descargar
    parser.add_argument("--sources", type=str, default="all")
    args = parser.parse_args() # Parsea los argumentos de línea de comandos
    mode = args.sources.lower() # Modo de descarga (todo o específico)
    print(f"➤ Ejecutando descarga de vectores. Modo: {mode.upper()}")
    # Lógica de ejecución condicional
    if mode == "all" or mode == "ide": download_limites() # Descargar límites comunales
    if mode == "all" or mode == "ine": download_censo() # Descargar manzanas censales
    if mode == "all" or mode == "osm": download_red_vial() # Descargar red vial
    cleanup_temp(force_create=False) # Limpieza final
    # Mensaje de finalización
    print(f"\n✔ ✔ Proceso finalizado. Metadatos en: {METADATA_FILE}")