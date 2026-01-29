# ==============================================================================
# SCRIPT: detect_changes.py
# ==============================================================================
# Descripción: Implementa múltiples métodos de detección de cambios urbanos
#              mediante análisis multitemporal de índices espectrales.
#
# Este script es el núcleo del análisis de cambios (Parte 3 del laboratorio).
# Implementa tres métodos complementarios:
#
#   Método 1 - Diferencia Simple: Resta de índices entre dos fechas.
#              Detecta cambios positivos (ganancia) y negativos (pérdida).
#
#   Método 2 - Clasificación Urbana: Combina NDVI, NDBI y NDWI para
#              clasificar tipos específicos de cambio (urbanización,
#              pérdida/ganancia de vegetación, nuevo agua).
#
#   Método 3 - Anomalías Temporales: Calcula Z-Score comparando un año
#              objetivo contra la serie histórica completa.
#
# Uso desde línea de comandos:
#   python scripts/detect_changes.py --t1 2019 --t2 2025 --method all
#   o simplemente ejecuta: python scripts/detect_changes.py
#
# Argumentos:
#   --t1: Año inicial (base) del análisis
#   --t2: Año final (objetivo) del análisis
#   --method: Método a ejecutar (diff, urban, anomaly, all)
# ==============================================================================

# 1) Importación de librerías
import argparse # para el procesamiento de argumentos de línea de comandos
import rasterio # para la lectura y escritura de datos raster geoespaciales (GeoTIFF)
import numpy as np # para las operaciones numéricas y manipulación de arrays multidimensionales
import geopandas as gpd # para la manipulación de datos vectoriales (shapefiles, geopackages)
from rasterio.mask import mask # para recortar rasters usando geometrías vectoriales
from pathlib import Path # para manejar rutas de archivos multiplataforma
from datetime import datetime # para el manejo de fechas para logging de operaciones
import sys # para acceder a funcionalidades del intérprete (sys.exit para códigos de error)

# ==============================================================================
# 2) Configuración de rutas y directorios

# Obtiene la ubicación del script actual
SCRIPT_DIR = Path(__file__).parent.resolve()
# Directorio raíz del proyecto (un nivel arriba del script)
PROJECT_ROOT = SCRIPT_DIR.parent
# Directorio donde se encuentran los índices espectrales procesados
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
# Directorio con archivos vectoriales (límites comunales, etc.)
VECTOR_DIR = PROJECT_ROOT / "data" / "vector"
# Directorio de salida (mismo que processed para mantener coherencia)
OUTPUT_DIR = PROCESSED_DIR 
# Archivo de metadatos para registrar el log de operaciones
METADATA_FILE = PROCESSED_DIR / "metadata_changes.txt"
# Archivo vectorial con el límite comunal de Viña del Mar
VECTOR_FILE = VECTOR_DIR / "limite_comuna.gpkg"

# ==============================================================================
# 3) Inicialización del archivo de metadatos

# Modo 'w' sobrescribe el archivo, reiniciando el log en cada ejecución
# Esto evita acumulación de logs de ejecuciones anteriores
with open(METADATA_FILE, "w", encoding="utf-8") as f:
    f.write("METADATOS DE DETECCIÓN DE CAMBIOS\n")
    f.write("="*50 + "\n\n")

# ==============================================================================
# 4) Función de logging
def log_message(msg):
    """
    Registra mensajes tanto en consola como en archivo de metadatos.
    
    Descripción:
        Función de utilidad para logging dual. Cada mensaje se imprime
        en la consola y también se agrega al archivo de metadatos con
        marca de tiempo (timestamp) para trazabilidad.
    
    Entradas:
        msg (str): Mensaje a registrar
    
    Salidas:
        Ninguna (efectos secundarios: imprime en consola y escribe en archivo)
    """
    # Imprime el mensaje en la consola
    print(msg)
    # Agrega el mensaje al archivo de metadatos con timestamp
    # Modo 'a' (append) agrega al final sin sobrescribir
    with open(METADATA_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

# ==============================================================================
# 5) Funciones utiles para el procesamiento de raster
# ==============================================================================
# FUNCIÓN: load_masked_image()
# ==============================================================================
def load_masked_image(tif_path, band_indices=None):
    """
    Carga una imagen raster y aplica máscara del límite de Viña del Mar.
    
    Descripción:
        Lee un archivo GeoTIFF y lo recorta usando el polígono del límite
        comunal. Opcionalmente puede seleccionar bandas específicas.
        Los píxeles fuera del límite se convierten a NaN para análisis.
    
    Entradas:
        tif_path (Path): Ruta al archivo GeoTIFF a cargar
        band_indices (list, opcional): Lista de índices de bandas a leer.
                                       Ej: [1] para NDVI, [1,2,3] para NDVI+NDBI+NDWI
                                       Si es None, lee todas las bandas.
    
    Salidas:
        tuple: (out_image, profile)
            - out_image (np.array): Array con los datos enmascarados (float con NaN)
            - profile (dict): Metadatos del raster (CRS, transform, etc.)
    
    Raises:
        FileNotFoundError: Si no existe el archivo vectorial de límite comunal
    """
    # Abre el archivo raster en modo lectura
    with rasterio.open(tif_path) as src:
        # Verifica que exista el archivo vectorial del límite
        if not VECTOR_FILE.exists():
            raise FileNotFoundError(f"Falta el vector: {VECTOR_FILE}")
        
        # Carga el límite comunal desde el geopackage
        gdf = gpd.read_file(VECTOR_FILE)
        # Reproyecta el vector al CRS del raster si son diferentes
        if gdf.crs != src.crs:
            gdf = gdf.to_crs(src.crs)
        
        # Aplica la máscara según si se especificaron bandas o no
        if band_indices:
            # Lee solo las bandas especificadas
            out_image, out_transform = mask(src, gdf.geometry, crop=False, indexes=band_indices)
            profile = src.profile
            # Actualiza el número de bandas en el perfil
            profile.update(count=len(band_indices))
        else:
            # Lee todas las bandas
            out_image, out_transform = mask(src, gdf.geometry, crop=False)
            profile = src.profile
        
        # Convierte a float para poder usar NaN como valor de máscara
        out_image = out_image.astype(float)
        # Los píxeles fuera del límite (valor 0) se convierten a NaN
        out_image[out_image == 0] = np.nan
        return out_image, profile

# ==============================================================================
# FUNCIÓN: save_raster()
# ==============================================================================
def save_raster(data, profile, output_path, description=None):
    """
    Guarda un array numpy como raster GeoTIFF comprimido.
    
    Descripción:
        Escribe datos raster a disco con compresión LZW para optimizar
        el espacio. Detecta automáticamente el tipo de dato apropiado
        (int8, int16 o float32) según el rango de valores.
    
    Entradas:
        data (np.array): Array 2D o 3D con los datos a guardar
        profile (dict): Perfil/metadatos del raster (CRS, transform, etc.)
        output_path (Path): Ruta de salida para el archivo GeoTIFF
        description (str, opcional): Descripción a guardar en metadatos del TIFF
    
    Salidas:
        Ninguna (efecto secundario: crea archivo GeoTIFF en disco)
    """
    # Determina el tipo de dato óptimo según el contenido
    if 'int' in str(data.dtype):
        # Para enteros, usa int8 si cabe en el rango [-128, 127], sino int16
        dtype = rasterio.int8 if data.min() >= -128 and data.max() <= 127 else rasterio.int16
        nodata = 0  # Valor nodata para enteros
    else:
        # Para flotantes, usa float32
        dtype = rasterio.float32
        nodata = np.nan  # Valor nodata para flotantes

    # Actualiza el perfil con el tipo de dato, nodata y compresión LZW
    profile.update(dtype=dtype, nodata=nodata, compress='lzw')
    
    # Escribe el archivo raster
    with rasterio.open(output_path, "w", **profile) as dst:
        if data.ndim == 2:
            # Datos 2D (una sola banda)
            dst.write(data.astype(dtype), 1)
        else:
            # Datos 3D (múltiples bandas)
            for i in range(data.shape[0]):
                dst.write(data[i].astype(dtype), i + 1)
        
        # Agrega descripción a los metadatos si se proporcionó
        if description:
            dst.update_tags(DESCRIPTION=description)
            
    # Registra la operación en el log
    log_message(f"✔ Guardado: {output_path.name}")

# ==============================================================================
# 6) Métodos de detección de cambios
# ==============================================================================
# MÉTODO 1: method_difference() - DIFERENCIA SIMPLE DE ÍNDICES
# ==============================================================================
def method_difference(t1_path, t2_path, index_band=1, threshold=0.15):
    """
    Detecta cambios mediante resta simple de índices espectrales (T2 - T1).
    
    Descripción:
        Método más básico de detección de cambios. Calcula la diferencia
        entre dos fechas para un índice espectral específico. Los cambios
        se clasifican según un umbral:
        - Diferencia > umbral: Ganancia (valor = 1)
        - Diferencia < -umbral: Pérdida (valor = -1)
        - Diferencia entre umbrales: Sin cambio (valor = 0)
        
        Por defecto usa NDVI (banda 1) para detectar cambios en vegetación.
    
    Entradas:
        t1_path (Path): Ruta al raster de índices del año inicial (base)
        t2_path (Path): Ruta al raster de índices del año final (objetivo)
        index_band (int): Número de banda a analizar. Default=1 (NDVI)
                         Bandas disponibles: 1=NDVI, 2=NDBI, 3=NDWI, 4=BSI
        threshold (float): Umbral de cambio significativo. Default=0.15
                          Valores típicos: 0.10-0.20 para NDVI
    
    Salidas:
        Ninguna (genera archivo GeoTIFF: cambio_diferencia_indices_YYYY_YYYY.tif)
        
    Archivo de salida:
        Valores: -1 (pérdida), 0 (sin cambio), 1 (ganancia)
    """
    log_message(f"--- Ejecutando Método 1: Diferencia Simple (Banda {index_band}) ---")
    
    # Carga las imágenes de ambas fechas (solo la banda especificada)
    img_t1, prof = load_masked_image(t1_path, [index_band])
    img_t2, _    = load_masked_image(t2_path, [index_band])
    
    # Silencia warnings por operaciones con NaN (píxeles enmascarados)
    with np.errstate(invalid='ignore'):
        # Calcula la diferencia: valores positivos = aumento, negativos = disminución
        diff = img_t2[0] - img_t1[0]
        
        # Inicializa mapa de cambios como "sin cambio" (0)
        change_map = np.zeros_like(diff, dtype=np.int8)
        # Marca píxeles con ganancia significativa
        change_map[diff > threshold] = 1   # Ganancia
        # Marca píxeles con pérdida significativa
        change_map[diff < -threshold] = -1 # Pérdida
    
    # Calcula estadísticas solo para píxeles válidos (no NaN)
    valid_mask = np.isfinite(diff)
    total = np.count_nonzero(valid_mask)
    
    # Reporta estadísticas si hay píxeles válidos
    if total > 0:
        pos = np.count_nonzero(change_map == 1)
        neg = np.count_nonzero(change_map == -1)
        log_message(f"Ganancia (> {threshold}): {pos} px ({pos/total:.1%})")
        log_message(f"Pérdida (< -{threshold}): {neg} px ({neg/total:.1%})")
    
    # Genera nombre de archivo de salida basado en los años
    out_name = f"cambio_diferencia_indices_{t1_path.stem.split('_')[1]}_{t2_path.stem.split('_')[1]}.tif"
    # Guarda el resultado
    save_raster(change_map, prof, OUTPUT_DIR / out_name, description=f"Diff Band {index_band}")

# ==============================================================================
# MÉTODO 2: method_urban_classification() - CLASIFICACIÓN DE CAMBIO URBANO
# ==============================================================================
def method_urban_classification(t1_path, t2_path):
    """
    Clasifica tipos de cambio urbano combinando múltiples índices espectrales.
    
    Descripción:
        Método más sofisticado que usa NDVI, NDBI y NDWI simultáneamente
        para identificar diferentes tipos de transición de cobertura.
        
        Clases de cambio detectadas:
        - Clase 0: Sin cambio significativo
        - Clase 1: Urbanización (vegetación → área construida)
        - Clase 2: Pérdida de vegetación (no urbana, ej: incendios, sequía)
        - Clase 3: Ganancia de vegetación (recuperación, nuevas áreas verdes)
        - Clase 4: Nuevo cuerpo de agua
        
        Las reglas de clasificación se basan en umbrales empíricos
        típicos para zonas mediterráneas de Chile central.
    
    Entradas:
        t1_path (Path): Ruta al raster de índices del año inicial
        t2_path (Path): Ruta al raster de índices del año final
    
    Salidas:
        Ninguna (genera archivo GeoTIFF: cambio_urbano_YYYY_YYYY.tif)
        
    Archivo de salida:
        Valores: 0-4 representando las clases de cambio
    """
    log_message(f"--- Ejecutando Método 2: Clasificación Urbana ---")
    
    # Carga las 3 primeras bandas de cada fecha: NDVI, NDBI, NDWI
    img_t1, prof = load_masked_image(t1_path, [1, 2, 3])
    img_t2, _    = load_masked_image(t2_path, [1, 2, 3])
    
    # Desempaqueta las bandas para cada fecha
    ndvi_t1, ndbi_t1, ndwi_t1 = img_t1  # Índices del año base
    ndvi_t2, ndbi_t2, ndwi_t2 = img_t2  # Índices del año objetivo
    
    # Inicializa el mapa de clases como "sin cambio" (0)
    clase = np.zeros_like(ndvi_t1, dtype=np.int8)
    # Máscara de píxeles válidos (con datos en ambas fechas)
    valid = np.isfinite(ndvi_t1) & np.isfinite(ndvi_t2)
    
    # Silencia warnings en operaciones booleanas con NaN
    with np.errstate(invalid='ignore'):
        # ---------------------------------------------------------------
        # CLASE 1: URBANIZACIÓN
        # Condiciones: Era vegetación (NDVI alto) → Ahora construido (NDBI positivo)
        # y el NDBI aumentó significativamente (>0.1)
        # ---------------------------------------------------------------
        mask_urb = (ndvi_t1 > 0.3) & (ndbi_t2 > 0.0) & ((ndbi_t2 - ndbi_t1) > 0.1)
        clase[mask_urb & valid] = 1
        
        # ---------------------------------------------------------------
        # CLASE 2: PÉRDIDA DE VEGETACIÓN (NO URBANA)
        # Condiciones: Era vegetación → Perdió vegetación pero NO se urbanizó
        # Típico de incendios, sequía o deforestación
        # ---------------------------------------------------------------
        mask_loss = (ndvi_t1 > 0.3) & ((ndvi_t1 - ndvi_t2) > 0.1) & (ndbi_t2 <= 0.0)
        # Solo asigna si no fue ya clasificado como urbanización
        clase[mask_loss & valid & (clase == 0)] = 2
        
        # ---------------------------------------------------------------
        # CLASE 3: GANANCIA DE VEGETACIÓN
        # Condiciones: Ahora tiene vegetación significativa que antes no tenía
        # Típico de recuperación post-incendio o nuevas áreas verdes
        # ---------------------------------------------------------------
        mask_gain = (ndvi_t2 > 0.3) & ((ndvi_t2 - ndvi_t1) > 0.1)
        clase[mask_gain & valid & (clase == 0)] = 3
        
        # ---------------------------------------------------------------
        # CLASE 4: NUEVO CUERPO DE AGUA
        # Condiciones: No era agua (NDWI negativo) → Ahora es agua (NDWI positivo)
        # Detecta inundaciones, nuevos embalses, etc.
        # ---------------------------------------------------------------
        mask_new_water = (ndwi_t1 < 0.0) & (ndwi_t2 > 0.0)
        clase[mask_new_water & valid & (clase == 0)] = 4
    
    # Calcula y reporta estadísticas por clase
    counts = np.bincount(clase[valid & (clase > 0)].flatten())
    labels = {1: "Urbanización", 2: "Pérdida Veg", 3: "Ganancia Veg", 4: "Nuevo Agua"}
    
    for k, v in labels.items():
        if k < len(counts):
            # Reporta cantidad de píxeles y hectáreas aproximadas (10m x 10m = 0.01 ha)
            log_message(f"Clase {v}: {counts[k]} px (~{counts[k]*0.01:.1f} ha)")

    # Genera nombre y guarda el resultado
    out_name = f"cambio_urbano_{t1_path.stem.split('_')[1]}_{t2_path.stem.split('_')[1]}.tif"
    save_raster(clase, prof, OUTPUT_DIR / out_name, description="Urban Change Classification")

# ==============================================================================
# MÉTODO 3: method_anomaly() - ANÁLISIS DE ANOMALÍAS TEMPORALES (Z-SCORE)
# ==============================================================================
def method_anomaly(target_year):
    """
    Detecta anomalías usando Z-Score histórico (Criterio 7.0 - Serie Temporal).
    
    Descripción:
        Método estadístico que compara el año objetivo contra toda la serie
        histórica disponible. Para cada píxel calcula:
        
        Z-Score = (valor_actual - media_histórica) / desviación_estándar
        
        Interpretación del Z-Score:
        - Z > 2: Anomalía positiva significativa (más vegetación de lo normal)
        - Z < -2: Anomalía negativa significativa (menos vegetación de lo normal)
        - |Z| < 2: Dentro del rango normal de variabilidad
        
        Este método es útil para identificar cambios que se desvían del
        comportamiento típico de la zona, filtrando variaciones estacionales.
    
    Entradas:
        target_year (int): Año objetivo a comparar contra la historia.
                          Debe existir un archivo indices_YYYY.tif
    
    Salidas:
        Ninguna (genera archivo GeoTIFF: anomalia_temporal_YYYY.tif)
        
    Archivo de salida:
        Valores: Z-Score continuo (típicamente entre -3 y +3)
        Valores extremos se truncan para visualización
    """
    log_message(f"--- Ejecutando Método 3: Anomalías Temporales (Target: {target_year}) ---")
    
    # Busca todos los archivos de índices disponibles
    all_files = sorted(list(PROCESSED_DIR.glob("indices_*.tif")))
    # Separa archivos históricos (todos excepto el año objetivo)
    history_files = [f for f in all_files if str(target_year) not in f.name]
    # Identifica el archivo del año objetivo
    target_file = next((f for f in all_files if str(target_year) in f.name), None)
    
    # Valida que existan los datos necesarios
    if not target_file or not history_files:
        log_message("✘ Error: Faltan datos para análisis histórico.")
        return

    # Construye el stack temporal con los datos históricos
    stack = []
    for f in history_files:
        # Carga solo la banda 1 (NDVI) de cada año histórico
        img, prof = load_masked_image(f, [1])
        stack.append(img[0])
    
    # Silencia warnings por operaciones con muchos NaN
    with np.errstate(invalid='ignore'):
        # Convierte la lista a array 3D: (años, filas, columnas)
        stack = np.array(stack)
        # Calcula la media histórica ignorando NaN
        mean_hist = np.nanmean(stack, axis=0)
        # Calcula la desviación estándar histórica ignorando NaN
        std_hist = np.nanstd(stack, axis=0)
        
        # Carga el año objetivo
        target_img, _ = load_masked_image(target_file, [1])
        current = target_img[0]
        
        # Calcula Z-Score: (valor - media) / desviación_estándar
        # Se suma 1e-6 a std para evitar división por cero
        with np.errstate(divide='ignore'):  # Ignora división por cero
            z_score = (current - mean_hist) / (std_hist + 1e-6)
        
        # Reemplaza valores infinitos o NaN con 0 (sin anomalía)
        z_score[~np.isfinite(z_score)] = 0
    
    # Genera nombre y guarda el resultado
    out_name = f"anomalia_temporal_{target_year}.tif"
    prof.update(dtype=rasterio.float32, nodata=np.nan)
    save_raster(z_score, prof, OUTPUT_DIR / out_name, description=f"NDVI Z-Score {target_year}")

# ==============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ==============================================================================
# Este bloque se ejecuta solo cuando el script se invoca directamente
# (no cuando se importa como módulo)
if __name__ == "__main__":
    # -------------------------------------------------------------------------
    # CONFIGURACIÓN DE ARGUMENTOS DE LÍNEA DE COMANDOS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(description="Detección de Cambios Multitemporal")
    # Argumento: año inicial (base) para la comparación
    parser.add_argument("--t1", type=int, default=2019, help="Año inicial (Base)")
    # Argumento: año final (objetivo) para la comparación
    parser.add_argument("--t2", type=int, default=2025, help="Año final (Target)")
    # Argumento: método(s) de detección a ejecutar
    parser.add_argument("--method", type=str, default="all", choices=["diff", "urban", "anomaly", "all"])
    
    # Parsea los argumentos proporcionados
    args = parser.parse_args()
    
    # -------------------------------------------------------------------------
    # VALIDACIONES DE ENTRADA
    # -------------------------------------------------------------------------
    # Define el rango válido de años (según datos disponibles)
    MIN_YEAR, MAX_YEAR = 2019, 2025
    
    # Valida que los años estén dentro del rango permitido
    if not (MIN_YEAR <= args.t1 <= MAX_YEAR) or not (MIN_YEAR <= args.t2 <= MAX_YEAR):
        print(f"✘ Error: Los años deben estar entre {MIN_YEAR} y {MAX_YEAR}.")
        sys.exit(1)  # Termina con código de error 1

    # Valida que el año base sea anterior al año objetivo
    if args.t1 >= args.t2:
        print(f"✘ Error Lógico: El año base (t1={args.t1}) debe ser ANTERIOR al año objetivo (t2={args.t2}).")
        sys.exit(1)

    # Construye las rutas a los archivos de índices
    file_t1 = PROCESSED_DIR / f"indices_{args.t1}.tif"
    file_t2 = PROCESSED_DIR / f"indices_{args.t2}.tif"
    
    # Verifica que existan los archivos necesarios
    if not file_t1.exists() or not file_t2.exists():
        print(f"✘ Error: Faltan archivos de índices.")
        sys.exit(1)
        
    # -------------------------------------------------------------------------
    # EJECUCIÓN DE MÉTODOS DE DETECCIÓN
    # -------------------------------------------------------------------------
    print(f"➤ Iniciando Detección de Cambios: {args.t1} -> {args.t2}")
    
    # Ejecuta Método 1: Diferencia Simple (si se solicitó)
    if args.method in ["diff", "all"]:
        method_difference(file_t1, file_t2, index_band=1, threshold=0.15)
    
    # Ejecuta Método 2: Clasificación Urbana (si se solicitó)
    if args.method in ["urban", "all"]:
        method_urban_classification(file_t1, file_t2)
    
    # Ejecuta Método 3: Anomalías Temporales (si se solicitó)
    if args.method in ["anomaly", "all"]:
        method_anomaly(args.t2)
        
    # Mensaje de finalización
    print(f"\n✔ ✔ Proceso finalizado. Resultados en {OUTPUT_DIR}")