import rasterio
import numpy as np
import warnings
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# Ignorar advertencias de división por cero (las manejamos con nans)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
BASE_DIR = Path(__file__).parent.parent.resolve()
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
METADATA_FILE = PROCESSED_DIR / "metadata.txt"

# Crear carpeta de salida
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Reiniciar metadatos
with open(METADATA_FILE, "w", encoding="utf-8") as f:
    f.write(f"METADATOS DE ÍNDICES ESPECTRALES (PROCESSED)\n")
    f.write(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("="*50 + "\n\n")

# ==============================================================================
# FUNCIONES
# ==============================================================================
def log_metadata(filename, year, stats):
    """Registra estadísticas básicas en el archivo de texto."""
    with open(METADATA_FILE, "a", encoding="utf-8") as f:
        f.write(f"Archivo: {filename}\n")
        f.write(f" - Año: {year}\n")
        f.write(f" - Bandas: 1:NDVI, 2:NDBI, 3:NDWI, 4:BSI\n")
        f.write(f" - Estadísticas (Promedio):\n")
        f.write(f"   * NDVI: {stats['ndvi']:.3f}\n")
        f.write(f"   * NDBI: {stats['ndbi']:.3f}\n")
        f.write(f"   * NDWI: {stats['ndwi']:.3f}\n")
        f.write(f"   * BSI:  {stats['bsi']:.3f}\n")
        f.write("-" * 30 + "\n")

def calcular_indices(ruta_imagen, ruta_salida):
    """
    Calcula índices espectrales: NDVI, NDBI, NDWI, BSI.
    Bandas de entrada (según download_sentinel.py):
        1: Blue (B2)
        2: Green (B3)
        3: Red (B4)
        4: NIR (B8)
        5: SWIR1 (B11)
        6: SWIR2 (B12)
    """
    with rasterio.open(ruta_imagen) as src:
        profile = src.profile
        
        # Leer bandas
        # IMPORTANTE: Verificar escala. Si ya viene en 0-1, no dividir.
        # Leemos una muestra pequeña para testear
        sample = src.read(1, window=((0, 10), (0, 10)))
        factor = 1.0
        if np.max(sample) > 1.5: # Si hay valores > 1.5, asumimos escala 0-10000
            factor = 10000.0
            
        # Leer bandas necesarias y convertir a reflectancia (0-1)
        # Usamos .read(x) donde x es el índice 1-based
        blue  = src.read(1).astype(float) / factor
        green = src.read(2).astype(float) / factor
        red   = src.read(3).astype(float) / factor
        nir   = src.read(4).astype(float) / factor
        swir1 = src.read(5).astype(float) / factor
        
        # Enmascarar ceros o valores inválidos para evitar errores de cálculo
        # Si una banda es 0, todo es inválido en ese pixel
        mask = (blue + green + red + nir + swir1) == 0
        blue[mask] = np.nan
        
    # Epsilon para evitar división por cero
    eps = 1e-10

    # 1. NDVI (Vegetación) = (NIR - Red) / (NIR + Red)
    ndvi = (nir - red) / (nir + red + eps)

    # 2. NDBI (Construcciones) = (SWIR - NIR) / (SWIR + NIR)
    ndbi = (swir1 - nir) / (swir1 + nir + eps)

    # 3. NDWI (Agua - McFeeters) = (Green - NIR) / (Green + NIR)
    ndwi = (green - nir) / (green + nir + eps)

    # 4. BSI (Suelo Desnudo)
    # Fórmula: ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))
    bsi = ((swir1 + red) - (nir + blue)) / ((swir1 + red) + (nir + blue) + eps)

    # Preparar metadatos de salida
    profile.update(
        count=4,
        dtype=rasterio.float32,
        driver='GTiff',
        compress='lzw' # Compresión para ahorrar espacio
    )

    # Guardar
    with rasterio.open(ruta_salida, "w", **profile) as dst:
        dst.write(ndvi.astype(rasterio.float32), 1)
        dst.write(ndbi.astype(rasterio.float32), 2)
        dst.write(ndwi.astype(rasterio.float32), 3)
        dst.write(bsi.astype(rasterio.float32), 4)
        
        dst.set_band_description(1, "NDVI")
        dst.set_band_description(2, "NDBI")
        dst.set_band_description(3, "NDWI")
        dst.set_band_description(4, "BSI")

    return {
        "ndvi": np.nanmean(ndvi),
        "ndbi": np.nanmean(ndbi),
        "ndwi": np.nanmean(ndwi),
        "bsi": np.nanmean(bsi)
    }

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    print("🚀 Iniciando cálculo de índices espectrales...")
    print(f"📂 Origen: {RAW_DIR}")
    print(f"📂 Destino: {PROCESSED_DIR}\n")

    imagenes = sorted(list(RAW_DIR.glob("sentinel2_*.tif")))
    
    if not imagenes:
        print("❌ No se encontraron imágenes en data/raw")
        exit()

    # Barra de progreso
    pbar = tqdm(imagenes, desc="Procesando imágenes")

    for img in pbar:
        try:
            year = img.stem.split("_")[1]
            output_name = f"indices_{year}.tif"
            output_path = PROCESSED_DIR / output_name
            
            pbar.set_postfix_str(f"Año {year}")
            
            # Calcular
            stats = calcular_indices(img, output_path)
            
            # Registrar
            log_metadata(output_name, year, stats)
            
        except Exception as e:
            print(f"\n❌ Error procesando {img.name}: {e}")

    print(f"\n🏁 Proceso completado. Metadatos en: {METADATA_FILE}")