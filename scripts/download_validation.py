# ==============================================================================
# SCRIPT: download_validation.py
# ==============================================================================
# Descripción: Descarga datos de referencia (Ground Truth) desde Google Dynamic
#              World para validar los resultados de detección de cambios.
#
# Dynamic World es un producto de clasificación de cobertura terrestre de Google
# que proporciona etiquetas de uso de suelo a 10m de resolución, ideal para
# validar las clasificaciones de cambio urbano realizadas en este laboratorio.
#
# Fuente de datos: GOOGLE/DYNAMICWORLD/V1 (Google Earth Engine)
# Resolución espacial: 10 metros
# Cobertura temporal: Desde mediados de 2019
#
# Clases de Dynamic World:
#   0: Agua         | 1: Árboles      | 2: Pasto
#   3: Veg. Inundada| 4: Cultivos     | 5: Arbustos
#   6: Construido   | 7: Suelo desnudo| 8: Nieve/Hielo
#
# ==============================================================================

# 1) Importación de librerías
import ee # para conectar con API de Google Earth Engine para acceso a catálogos de imágenes satelitales
import geemap # para la descarga de imágenes desde GEE a archivos locales
import os # para interactuar con variables de entorno del sistema
from pathlib import Path # para la manipulación de rutas de archivos (de forma multiplataforma)

# ==============================================================================

# 2) Configuración de rutas y proyecto GEE
# Proyecto de Google Earth Engine (reemplazar con el propio si es necesario)
DEFAULT_GEE_PROJECT = "composed-augury-451119-b6" 
# Obtiene la ruta absoluta del directorio donde está este script
script_location = Path(__file__).parent.resolve()
# Define el directorio de salida para los datos de validación
output_dir = script_location.parent / "data" / "validation"
# Crea el directorio si no existe (parents=True crea directorios intermedios)
output_dir.mkdir(parents=True, exist_ok=True)

# Mensaje informativo sobre la ubicación de salida
print(f"➤ Los datos de validación se guardarán en: {output_dir}")

# ==============================================================================

# 3) Inicialización de Google Earth Engine
def init_gee():
    """
    Inicializa la conexión con Google Earth Engine.
    
    Descripción:
        Intenta inicializar GEE con el proyecto configurado. Si falla (por
        ejemplo, si no hay credenciales válidas), solicita autenticación
        interactiva al usuario y luego reintenta la inicialización.
    
    Entradas:
        Ninguna (usa variable global DEFAULT_GEE_PROJECT o variable de entorno)
    
    Salidas:
        Ninguna (efecto secundario: conexión a GEE establecida)
    
    Variables de entorno:
        EE_PROJECT: Si está definida, se usa en lugar de DEFAULT_GEE_PROJECT
    """
    # Intenta obtener el proyecto desde variable de entorno o usa el default
    project = os.environ.get('EE_PROJECT') or DEFAULT_GEE_PROJECT
    try:
        # Intenta inicializar con las credenciales existentes
        ee.Initialize(project=project)
        print(f"✔ GEE inicializado.")
    except Exception:
        # Si falla, solicita autenticación interactiva (abre navegador)
        ee.Authenticate()
        # Reintenta la inicialización después de autenticar
        ee.Initialize(project=project)

# Ejecuta la inicialización de GEE al cargar el módulo
init_gee()

# ==============================================================================

# 4) Definición del área de estudio

# Geometría del área de estudio: Viña del Mar, Chile
# Formato: [longitud_oeste, latitud_sur, longitud_este, latitud_norte]
# Coordenadas en WGS84 (EPSG:4326), mismas que en download_sentinel.py
geometry = ee.Geometry.Rectangle([-71.607, -33.125, -71.423, -32.925])

# ==============================================================================

# 5) Función para obtener la clasificación modal de Dynamic World
def get_dynamic_world_class(start_date, end_date):
    """
    Obtiene la moda de la clasificación Dynamic World para un rango de fechas.
    
    Descripción:
        Dynamic World proporciona clasificaciones diarias de cobertura terrestre.
        Esta función recopila todas las clasificaciones dentro del período 
        especificado y calcula la MODA (valor más frecuente) para cada píxel.
        Usar la moda reduce el impacto de nubes y clasificaciones erróneas.
    
    Entradas:
        start_date (str): Fecha de inicio en formato 'YYYY-MM-DD'
        end_date (str): Fecha de fin en formato 'YYYY-MM-DD'
    
    Salidas:
        ee.Image: Imagen con la clasificación modal recortada al área de estudio.
                  Valores de 0-8 representando las 9 clases de Dynamic World.
    """
    # Carga la colección de imágenes Dynamic World de Google
    dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1") \
        .filterBounds(geometry) \
        .filterDate(start_date, end_date) \
        .select('label') # Seleccionamos solo la banda de etiqueta clasificada
    
    # Calcula la moda (valor más frecuente) para evitar efectos de nubes
    # reduce() aplica el reductor a toda la colección temporal
    classification = dw.reduce(ee.Reducer.mode()).clip(geometry)
    return classification

# ==============================================================================

# 6) Descargar de datos de validación

# Define los rangos de fechas para descargar referencias de 2019 y 2025
# Formato: (etiqueta_año, fecha_inicio, fecha_fin)
# Nota: Dynamic World comienza a mediados de 2019, por eso el rango específico
years_ranges = [
    ("2019", "2019-06-01", "2020-01-01"), # Período disponible más antiguo de DW
    ("2025", "2024-10-01", "2025-03-30")  # Temporada de verano 2025 (hemisferio sur)
]

print("➤ Descargando datos de validación (Dynamic World)...")

# Itera sobre cada año definido para descargar su clasificación
for year, start, end in years_ranges:
    # Define el nombre del archivo de salida
    filename = f"reference_lulc_{year}.tif"
    output_path = output_dir / filename
    
    # Verifica si el archivo ya existe para evitar descargas redundantes
    if output_path.exists():
        print(f"✔ [YA EXISTE] {filename}")
        continue  # Salta al siguiente año si ya existe
        
    print(f"➤ [DESCARGANDO] Referencia {year}...")
    
    # Obtiene la clasificación modal para el período especificado
    image = get_dynamic_world_class(start, end)
    
    try:
        # Descarga la imagen usando geemap con los parámetros especificados
        geemap.download_ee_image(
            image,
            filename=str(output_path),
            scale=10,  # Resolución de 10 metros (igual que Sentinel-2)
            region=geometry,  # Área de estudio definida
            crs='EPSG:32719',  # Sistema de coordenadas UTM Zona 19S (Chile central)
            overwrite=True  # Sobrescribe si existe (aunque ya verificamos arriba)
        )
        print(f"✔ Éxito: {filename}")
    except Exception as e:
        # Captura y muestra cualquier error durante la descarga
        print(f"✘ Error: {e}")


# ==============================================================================

# 7) Creación de archivo de leyenda

# Crea un archivo README con la descripción de las clases de Dynamic World
# Esto es útil como referencia rápida al interpretar los datos de validación
readme_path = output_dir / "README_CLASSES.txt"
with open(readme_path, "w") as f:
    f.write("CLASES DYNAMIC WORLD:\n")
    f.write("0: Water\n1: Trees\n2: Grass\n3: Flooded Vegetation\n")
    f.write("4: Crops\n5: Shrub & Scrub\n6: Built (Urbano)\n7: Bare (Suelo)\n8: Snow & Ice")

print("\n✔ ✔ Datos de validación listos.")