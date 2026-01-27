# =============================================================================
# SCRIPT: download_sentinel.py
# =============================================================================
# Descripción: Descarga imágenes Sentinel-2 desde Google Earth Engine y las guarda localmente.
#              Estas imágenes se utilizarán para calcular índices espectrales (NDVI, NDBI, NDWI, BSI).
#              Este script también registra los metadatos técnicos de las imágenes descargadas.
#
# Uso: python scripts/download_sentinel.py
# =============================================================================

# 1) Importación de librerías
import ee # Para conectarse con Google Earth Engine (API de Python) y acceder a imágenes satelitales (como Sentinel-2).
import geemap # Para la descarga de imágenes EE en archivos locales.
import os # Para el manejo de archivos.
import sys # Para manejo de errores y salida del sistema
import shutil # Para mover archivos y limpiar directorios temporales (Plan B)
from pathlib import Path # Para el manejo de rutas de archivos y directorios.
from datetime import datetime # Para registrar la fecha y hora de generación de los metadatos.

# 2) CONFIGURACIÓN
DEFAULT_GEE_PROJECT = "composed-augury-451119-b6" # ID del proyecto compartido. Para acceder a Google Earth Engine
# Enlace de respaldo a Google Drive (como plan B) con los TIFs ya procesados
DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1rjRRUQr6b-QIs79J05r7nMv4_mGzYcbT?usp=sharing"
script_location = Path(__file__).parent.resolve() # Ubicación del script actual (scripts/download_sentinel.py)
# Define la ruta de salida subiendo un nivel y entrando a data/raw (donde se guardarán las imágenes descargadas)
output_dir = script_location.parent / "data" / "raw"
# Crea el directorio si no existe (incluyendo padres)
output_dir.mkdir(parents=True, exist_ok=True)
# Ruta donde se guardará el archivo de metadatos
metadata_file = output_dir / "metadata.txt"
print(f"Los datos se guardarán en: {output_dir}")

# Reiniciar archivo de metadatos al iniciar el script
# Abre el archivo en modo escritura ('w') para limpiarlo al inicio (si es que se generó anteriormente)
with open(metadata_file, "w", encoding="utf-8") as f: # Usé UTF-8 para soportar caracteres especiales
    f.write(f"METADATOS DE IMÁGENES SATELITALES\n")
    f.write(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n") # fecha y hora actual
    f.write("="*50 + "\n\n")

# 3) FUNCIONES AUXILIARES

def log_metadata(filename, year, source="GEE"):
    """
    Descripción: Función para registrar los metadatos técnicos de la imagen descargada en el archivo de texto.

    Entradas:
        filename (str): Nombre del archivo .tif guardado.
        year (int): Año correspondiente a la imagen.
        source (str): Fuente de la descarga ('GEE' o 'Google Drive Plan B').
    
    Salidas:
        None: Escribe directamente en el archivo metadata.txt.
    """
    # Abre el archivo en modo 'append' ('a') para agregar sin borrar lo anterior
    with open(metadata_file, "a", encoding="utf-8") as f:
        f.write(f"Archivo: {filename}\n") # Nombre del archivo
        f.write(f" - Fuente: {source}\n") # Fuente de datos
        f.write(f" - Sensor: Sentinel-2 (COPERNICUS/S2_SR_HARMONIZED)\n") # Sensor y colección
        f.write(f" - Año: {year}\n") # Año de la imagen
        f.write(f" - Rango Temporal: 01 Enero - 30 Marzo (Verano)\n") # Rango temporal
        f.write(f" - Filtro Nubosidad: < 30% (Pixel Percentage)\n") # Filtro de nubosidad
        if source == "GEE":
            f.write(f" - Procesamiento: Mediana temporal (Cloud Masking + Median Composite)\n")
        else:
            f.write(f" - Procesamiento: Pre-procesado (descarga directa desde Google Drive)\n")
        f.write(f" - Bandas: B2, B3, B4, B8, B11, B12\n") # Bandas incluidas
        f.write("-" * 30 + "\n")

def init_gee():
    """
    Descripción: Función que inicializa la sesión de Google Earth Engine (GEE), y maneja
                 la autenticación y la conexión con el proyecto definido.

    Salidas:
        bool: True si la conexión fue exitosa, False si falló (activando Plan B).
    """
    # Intenta obtener el proyecto de las variables de entorno o usa el default
    project = os.environ.get('EE_PROJECT') or DEFAULT_GEE_PROJECT
    print(f" Conectando a GEE con proyecto: {project}...")
    try:
        # Intenta inicializar directamente si ya hay credenciales cacheadas
        ee.Initialize(project=project)
        print(f"✔ GEE inicializado.")
        return True # <--- ¡AQUÍ ESTABA EL ERROR! Faltaba retornar True
    except Exception as e: # Si falla, intenta autenticarse
        print(f"Advertencia: No se pudo conectar al proyecto GEE ({e}).")
        print("   Intentando autenticación interactiva...")
        try:
            ee.Authenticate()
            ee.Initialize(project=project)
            print(f"✔ GEE inicializado tras autenticación.")
            return True
        except Exception as e2: # Si falla de nuevo, avisa y retorna False
            print(f"✘ Error Crítico GEE: {e2}")
            return False

def descarga_drive():
    """
    Descripción: Función que implementa el plan de emergencia descargando los archivos directamente
                 desde Google Drive usando 'gdown' (si es que no funciona la conexión con GEE).
                 Filtra solo los archivos sentinel2_*.tif y borra el resto.
    
    Salidas:
        None: Descarga archivos, filtra y mueve los útiles a la carpeta destino.
    """
    print("\n" + "!"*60)
    print("Activando plan B: Descarga de Emergencia (Google Drive)")
    print("   No se pudo acceder a Earth Engine. Usando respaldo pre-procesado.")
    print("!"*60 + "\n")
    
    # Carpeta temporal para descargar todo el contenido del Drive antes de filtrar
    temp_dir = output_dir / "temp_drive_download"
    temp_dir.mkdir(exist_ok=True)

    try:
        import gdown # Librería para descargar archivos desde Google Drive
        print("Descargando carpeta completa temporalmente...")
        # Descarga la carpeta completa
        gdown.download_folder(url=DRIVE_FOLDER_URL, output=str(temp_dir), quiet=False, use_cookies=False)
        
        print("\n Filtrando archivos Sentinel (2019-2025)...")
        # Registrar metadatos simulados para mantener consistencia y filtrar
        for year in range(2019, 2026):
            target_name = f"sentinel2_{year}.tif" # Nombre del archivo esperado
            src_file = temp_dir / target_name
            dst_file = output_dir / target_name
            
            if src_file.exists(): # Verifica que el archivo se haya descargado en la carpeta temporal
                # Mover el archivo a la carpeta final (data/raw)
                if dst_file.exists():
                    os.remove(dst_file) # Asegurar limpieza
                shutil.move(str(src_file), str(dst_file))
                
                print(f"✔ Recuperado: {target_name}")
                log_metadata(target_name, year, source="Google Drive (Plan B)")
            else:
                print(f"No encontrado en Drive: {target_name}")

        print("\nLimpiando archivos temporales...")
        shutil.rmtree(temp_dir) # Borrar carpeta temporal con el resto de archivos basura
        print("\n✔ Plan B completado exitosamente.")
        
    except ImportError: # Si gdown no está instalado
        print("✘ Error: La librería 'gdown' no está instalada.")
        print(f"Por favor, descargue manualmente los archivos desde este enlace:")
        print(f" {DRIVE_FOLDER_URL}")
        print(f"Y guárdelos en la carpeta: {output_dir}")
    except Exception as e: # Otros errores durante la descarga
        print(f"✘ Error en descarga de datos desde Google Drive: {e}")
        # Limpieza de emergencia
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

# Ejecutar inicialización de Google Earth Engine
# Se guarda el resultado en una variable booleana para decidir qué plan usar
gee_disponible = init_gee()

# Geometría exacta (Viña del Mar + Margen)
geometry = ee.Geometry.Rectangle([-71.607, -33.125, -71.423, -32.925])
years = range(2019, 2026) # Años a descargar
# Bandas: Azul, Verde, Rojo, NIR (Infrarrojo Cercano), SWIR1, SWIR2
bands = ["B2", "B3", "B4", "B8", "B11", "B12"]

def mask_clouds_s2(image):
    """
    Descripción: Función que aplica una máscara de nubes y cirrus a una imagen Sentinel-2 usando la banda QA60.
                 También escala los valores de reflectancia y selecciona las bandas de interés.

    Entradas:
        image (ee.Image): Imagen original de la colección Sentinel-2.

    Salidas:
        ee.Image: Imagen procesada, enmascarada y escalada (0-1).
    """
    # Selecciona la banda de calidad QA60 que contiene flags de nubes
    qa = image.select("QA60")
    # Identifica bits correspondientes a nubes (bit 10) y cirrus (bit 11)
    # bitwiseAnd chequea si esos bits son 0 (despejado)
    cloud_mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    # Aplica la máscara, divide por 10000 para obtener reflectancia (0-1), 
    # selecciona bandas útiles y asegura rango 0-1 con clamp
    return image.updateMask(cloud_mask).divide(10000).select(bands).clamp(0, 1).copyProperties(image, ["system:time_start"])

# 4) DESCARGA DE IMÁGENES SATELITALES
# Comando de descarga: python scripts/download_sentinel.py
if __name__ == "__main__":
    
    if gee_disponible: # Si la conexión con GEE fue exitosa (Plan A)
        # Plan A: Descarga desde Google Earth Engine
        print(f"➤  Iniciando descarga oficial desde GEE...\n")
        for year in years: # Para cada año (2019-2025)
            filename = f"sentinel2_{year}.tif" # Nombre del archivo de salida
            output_path = output_dir / filename # Ruta completa del archivo de salida
            
            # Verificar existencia previa
            if output_path.exists(): # Si el archivo ya existe
                if output_path.stat().st_size > 1000: # Verifica que no esté corrupto (tamaño > 1KB)
                    print(f"✔ [YA EXISTE] {filename}") # Si ya existe, omite descarga
                    log_metadata(filename, year)
                    continue
                else: # Si el archivo es muy pequeño, asume que está corrupto y lo borra
                    os.remove(output_path) # Borrar archivo corrupto
            
            # Definir colección
            collection = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") # Selección de colección Sentinel-2 Surface Reflectance
                .filterBounds(geometry) # Filtrar por área de interés (Viña del Mar)
                .filterDate(f"{year}-01-01", f"{year}-03-30") # Filtrar por rango de fechas (verano), aunque se considera un poco de Otoño
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)) # Filtrar por nubosidad < 30%
                .map(mask_clouds_s2) # Aplicar máscara de nubes y pre-procesamiento
            )
            
            count = collection.size().getInfo() # Contar número de imágenes tras filtros
            if count == 0:
                print(f" [AVISO] Cero imágenes para {year}")
                continue
            
            # Descargando la imagen compuesta
            print(f"➤ [DESCARGANDO] {filename} (Usando {count} imágenes)...")
            
            # Reducción temporal (Mediana)
            composite = collection.median().clip(geometry) # Compuesto mediano para reducir ruido
            
            # Intentar descargar usando geemap
            try:
                geemap.download_ee_image( 
                    composite, # Imagen a descargar
                    filename=str(output_path), # Ruta de salida
                    scale=10, # Resolución espacial (10m para Sentinel-2)
                    region=geometry, # Región de interés (Viña del Mar)
                    crs='EPSG:32719', # Sistema de referencia de coordenadas UTM Zona 19S
                    overwrite=True # Sobrescribir si ya existe
                )
                print(f" ✔ Éxito: {filename}") # Confirmación de descarga exitosa
                log_metadata(filename, year) # Registrar metadatos
            except Exception as e: # En caso de errores en la descarga
                print(f" ✘ Error en descarga GEE: {e}")
                
    else: # Si la conexión con Google Earth Engine falló
        # Descarga desde Google Drive (Plan B)
        descarga_drive()

    print(f"\n✔ ✔ Proceso finalizado. Metadatos en: {metadata_file}")