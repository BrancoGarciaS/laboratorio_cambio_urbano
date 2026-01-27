# =============================================================================
# SCRIPT: calculate_indices.py
# =============================================================================
# Descripción: Calcula índices espectrales (NDVI, NDBI, NDWI, BSI) a partir de
#              imágenes Sentinel-2 descargadas. Los índices permiten caracterizar
#              diferentes tipos de cobertura del suelo (vegetación, áreas urbanas,
#              cuerpos de agua y suelo desnudo).
#
# Uso: python scripts/calculate_indices.py
# =============================================================================

# 1) Importación de librerías
import rasterio          # Lectura y escritura de archivos raster (GeoTIFF)
import numpy as np       # Operaciones numéricas con arrays multidimensionales
import warnings          # Control de mensajes de advertencia del sistema
from pathlib import Path # Manejo moderno de rutas de archivos multiplataforma
from datetime import datetime  # Registro de fecha y hora para metadatos
from tqdm import tqdm    # Barras de progreso visual en bucles

# 2) Configuración de advertencias
# Ignorar advertencias de división por cero (las manejamos manualmente con NaN)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# 3) Configuración de rutas y directorios

# Obtener la ruta base del proyecto (un nivel arriba de /scripts)
BASE_DIR = Path(__file__).parent.parent.resolve()

# Directorio de entrada: imágenes Sentinel-2 originales
RAW_DIR = BASE_DIR / "data" / "raw"

# Directorio de salida: archivos de índices procesados
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# Archivo de metadatos para documentar el procesamiento
METADATA_FILE = PROCESSED_DIR / "metadata.txt"

# 4) Crear carpeta de salida si no existe
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# 5) Inicialización del archivo de metadatos
# Se sobrescribe en cada ejecución para mantener registro actualizado
with open(METADATA_FILE, "w", encoding="utf-8") as f:
    f.write(f"METADATOS DE ÍNDICES ESPECTRALES (PROCESSED)\n")
    f.write(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("="*50 + "\n\n")

# 6) Funciones auxiliares

def log_metadata(filename, year, stats):
    """
    Registra las estadísticas de procesamiento en el archivo de metadatos.
    
    Descripción:
        Escribe información técnica sobre cada archivo de índices generado,
        incluyendo el año de la imagen y los valores promedio de cada índice.
        Para la trazabilidad y verificación del procesamiento.
    
    Entradas:
        filename (str): Nombre del archivo de índices generado (por ejemplo, indices_2019.tif)
        year (str): Año correspondiente a la imagen procesada
        stats (dict): Diccionario con estadísticas promedio de cada índice:
                      {'ndvi': float, 'ndbi': float, 'ndwi': float, 'bsi': float}
    
    Salidas:
        None: La función escribe directamente en el archivo metadata.txt
    """
    # Abrir archivo en modo append para agregar sin sobrescribir
    with open(METADATA_FILE, "a", encoding="utf-8") as f:
        f.write(f"Archivo: {filename}\n")                    # Nombre del archivo generado
        f.write(f" - Año: {year}\n")                         # Año de la imagen
        f.write(f" - Bandas: 1:NDVI, 2:NDBI, 3:NDWI, 4:BSI\n") # Orden de bandas en el archivo
        f.write(f" - Estadísticas (Promedio):\n")            # Encabezado de estadísticas
        f.write(f"   * NDVI: {stats['ndvi']:.3f}\n")         # Promedio de vegetación
        f.write(f"   * NDBI: {stats['ndbi']:.3f}\n")         # Promedio de construcciones
        f.write(f"   * NDWI: {stats['ndwi']:.3f}\n")         # Promedio de agua
        f.write(f"   * BSI:  {stats['bsi']:.3f}\n")          # Promedio de suelo desnudo
        f.write("-" * 30 + "\n")                             # Separador visual

def calcular_indices(ruta_imagen, ruta_salida):
    """
    Calcula índices espectrales a partir de una imagen Sentinel-2.
    
    Descripción:
        Procesa una imagen satelital multiespectral y genera 4 índices:
        - NDVI: Índice de Vegetación de Diferencia Normalizada
        - NDBI: Índice de Construcción de Diferencia Normalizada  
        - NDWI: Índice de Agua de Diferencia Normalizada
        - BSI: Índice de Suelo Desnudo
        
        Los índices se calculan usando combinaciones de bandas espectrales
        y permiten clasificar diferentes tipos de cobertura del suelo.
    
    Entradas:
        ruta_imagen (str o Path): Ruta al archivo GeoTIFF de entrada con bandas:
                                  1:Blue(B2), 2:Green(B3), 3:Red(B4), 
                                  4:NIR(B8), 5:SWIR1(B11), 6:SWIR2(B12)
        ruta_salida (str o Path): Ruta donde guardar el archivo de índices
    
    Salidas:
        dict: Diccionario con los valores promedio de cada índice:
              {'ndvi': float, 'ndbi': float, 'ndwi': float, 'bsi': float}
              
    Archivo generado:
        GeoTIFF con 4 bandas (1:NDVI, 2:NDBI, 3:NDWI, 4:BSI)
    """
    # Se abre imagen de entrada para lectura
    with rasterio.open(ruta_imagen) as src:
        # Copiar perfil de metadatos geoespaciales (CRS, transform, etc.)
        profile = src.profile
        
        # --- Detección automática de escala de valores ---
        # Las imágenes pueden venir en escala 0-1 (reflectancia) o 0-10000 (DN)
        # Leemos una muestra pequeña para determinar la escala
        sample = src.read(1, window=((0, 10), (0, 10)))
        factor = 1.0  # Factor de normalización por defecto
        if np.max(sample) > 1.5:  # Si hay valores > 1.5, asumimos escala 0-10000
            factor = 10000.0
            
        # --- Lectura de bandas espectrales ---
        # Cada banda se normaliza a reflectancia (rango 0-1)
        # Índices de rasterio son 1-based (1=primera banda)
        blue  = src.read(1).astype(float) / factor  # Banda Azul (B2)
        green = src.read(2).astype(float) / factor  # Banda Verde (B3)
        red   = src.read(3).astype(float) / factor  # Banda Roja (B4)
        nir   = src.read(4).astype(float) / factor  # Banda Infrarrojo Cercano (B8)
        swir1 = src.read(5).astype(float) / factor  # Banda SWIR1 (B11)
        
        # --- Creación de máscara de píxeles inválidos ---
        # Píxeles donde todas las bandas son 0 representan áreas sin datos
        mask = (blue + green + red + nir + swir1) == 0
        # Asignar NaN a píxeles inválidos para excluirlos de cálculos
        blue[mask] = np.nan
        
    # --- Constante epsilon para estabilidad numérica ---
    # Evita divisiones por cero en las fórmulas de índices normalizados
    eps = 1e-10

    # I) Cálculo de índices espectrales:
    
    # 1. NDVI (Normalized Difference Vegetation Index) - Índice de Vegetación
    # Fórmula: (NIR - Red) / (NIR + Red)
    # Interpretación: Valores altos (+1) = vegetación densa, bajos (-1) = sin vegetación
    ndvi = (nir - red) / (nir + red + eps)

    # 2. NDBI (Normalized Difference Built-up Index) - Índice de Construcciones
    # Fórmula: (SWIR - NIR) / (SWIR + NIR)
    # Interpretación: Valores altos = áreas urbanas/construidas, bajos = vegetación
    ndbi = (swir1 - nir) / (swir1 + nir + eps)

    # 3. NDWI (Normalized Difference Water Index) - Índice de Agua (McFeeters)
    # Fórmula: (Green - NIR) / (Green + NIR)
    # Interpretación: Valores positivos = cuerpos de agua, negativos = tierra
    ndwi = (green - nir) / (green + nir + eps)

    # 4. BSI (Bare Soil Index) - Índice de Suelo Desnudo
    # Fórmula: ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))
    # Interpretación: Valores altos = suelo expuesto, bajos = cobertura vegetal
    bsi = ((swir1 + red) - (nir + blue)) / ((swir1 + red) + (nir + blue) + eps)

    # II) Preparación y escritura del archivo de salida
    
    # Actualizar perfil de metadatos para el nuevo archivo
    profile.update(
        count=4,               # 4 bandas (una por índice)
        dtype=rasterio.float32, # Tipo de dato flotante de 32 bits
        driver='GTiff',        # Formato GeoTIFF
        compress='lzw'         # Compresión LZW para reducir tamaño de archivo
    )

    # --- Escritura del archivo raster de salida ---
    with rasterio.open(ruta_salida, "w", **profile) as dst:
        # Escribir cada índice como una banda separada
        dst.write(ndvi.astype(rasterio.float32), 1)  # Banda 1: NDVI
        dst.write(ndbi.astype(rasterio.float32), 2)  # Banda 2: NDBI
        dst.write(ndwi.astype(rasterio.float32), 3)  # Banda 3: NDWI
        dst.write(bsi.astype(rasterio.float32), 4)   # Banda 4: BSI
        
        # Asignar nombres descriptivos a cada banda (metadatos internos)
        dst.set_band_description(1, "NDVI")  # Vegetación
        dst.set_band_description(2, "NDBI")  # Construcciones
        dst.set_band_description(3, "NDWI")  # Agua
        dst.set_band_description(4, "BSI")   # Suelo desnudo

    # --- Retornar estadísticas promedio para registro ---
    # np.nanmean ignora valores NaN en el cálculo del promedio
    return {
        "ndvi": np.nanmean(ndvi),  # Promedio de vegetación en la imagen
        "ndbi": np.nanmean(ndbi),  # Promedio de áreas construidas
        "ndwi": np.nanmean(ndwi),  # Promedio de presencia de agua
        "bsi": np.nanmean(bsi)     # Promedio de suelo desnudo
    }

# ==============================================================================
# 7) Bloque principal de ejecución
# ==============================================================================
# Este bloque se ejecuta cuando el script se llama directamente:
# python scripts/calculate_indices.py
# ==============================================================================

if __name__ == "__main__":
    # --- Mensaje de inicio ---
    print("➤ Iniciando cálculo de índices espectrales...")
    print(f"Origen: {RAW_DIR}")        # Mostrar directorio de imágenes originales
    print(f"Destino: {PROCESSED_DIR}\n")  # Mostrar directorio de salida

    # --- Búsqueda de imágenes Sentinel-2 ---
    # Buscar todos los archivos que coincidan con el patrón sentinel2_*.tif
    imagenes = sorted(list(RAW_DIR.glob("sentinel2_*.tif")))
    
    # Verificar que existan imágenes para procesar
    if not imagenes:
        print("✘ No se encontraron imágenes en data/raw")
        exit()  # Terminar ejecución si no hay datos

    # --- Procesamiento con barra de progreso ---
    # tqdm muestra el avance visual del procesamiento
    pbar = tqdm(imagenes, desc="Procesando imágenes")

    # Iterar sobre cada imagen encontrada
    for img in pbar:
        try:
            # Extraer el año del nombre del archivo (ej: sentinel2_2019.tif -> 2019)
            year = img.stem.split("_")[1]
            
            # Definir nombre y ruta del archivo de salida
            output_name = f"indices_{year}.tif"
            output_path = PROCESSED_DIR / output_name
            
            # Actualizar barra de progreso con el año actual
            pbar.set_postfix_str(f"Año {year}")
            
            # Se hace el cálculo de índices espectrales
            stats = calcular_indices(img, output_path)
            
            # Se registran los metadatos
            log_metadata(output_name, year, stats)
            
        except Exception as e:
            # Capturar y mostrar errores sin detener el procesamiento completo
            print(f"\n✘ Error procesando {img.name}: {e}")

    # Mensaje de finalización 
    print(f"\n✔ ✔ Proceso completado. Metadatos en: {METADATA_FILE}")