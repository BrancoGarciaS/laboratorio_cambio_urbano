import argparse
import rasterio
import numpy as np
import geopandas as gpd
from rasterio.mask import mask
from pathlib import Path
from datetime import datetime
import sys

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
VECTOR_DIR = PROJECT_ROOT / "data" / "vector"
OUTPUT_DIR = PROCESSED_DIR 
METADATA_FILE = PROCESSED_DIR / "metadata_changes.txt"
VECTOR_FILE = VECTOR_DIR / "limite_comuna.gpkg"

# --- CAMBIO 1: SIEMPRE REINICIAR METADATA AL EJECUTAR ---
# Modo 'w' sobrescribe el archivo, borrando lo anterior.
with open(METADATA_FILE, "w", encoding="utf-8") as f:
    f.write("METADATOS DE DETECCIÓN DE CAMBIOS\n")
    f.write("="*50 + "\n\n")

def log_message(msg):
    print(msg)
    # Modo 'a' agrega líneas a la ejecución actual
    with open(METADATA_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

# ==============================================================================
# UTILIDADES
# ==============================================================================
def load_masked_image(tif_path, band_indices=None):
    """Carga imagen y aplica máscara de Viña del Mar."""
    with rasterio.open(tif_path) as src:
        if not VECTOR_FILE.exists():
            raise FileNotFoundError(f"Falta el vector: {VECTOR_FILE}")
            
        gdf = gpd.read_file(VECTOR_FILE)
        if gdf.crs != src.crs:
            gdf = gdf.to_crs(src.crs)
            
        if band_indices:
            out_image, out_transform = mask(src, gdf.geometry, crop=False, indexes=band_indices)
            profile = src.profile
            profile.update(count=len(band_indices))
        else:
            out_image, out_transform = mask(src, gdf.geometry, crop=False)
            profile = src.profile
        
        out_image = out_image.astype(float)
        out_image[out_image == 0] = np.nan
        return out_image, profile

def save_raster(data, profile, output_path, description=None):
    """Guarda raster comprimido."""
    if 'int' in str(data.dtype):
        dtype = rasterio.int8 if data.min() >= -128 and data.max() <= 127 else rasterio.int16
        nodata = 0
    else:
        dtype = rasterio.float32
        nodata = np.nan

    profile.update(dtype=dtype, nodata=nodata, compress='lzw')
    
    with rasterio.open(output_path, "w", **profile) as dst:
        if data.ndim == 2:
            dst.write(data.astype(dtype), 1)
        else:
            for i in range(data.shape[0]):
                dst.write(data[i].astype(dtype), i + 1)
        
        if description:
            dst.update_tags(DESCRIPTION=description)
            
    log_message(f"💾 Guardado: {output_path.name}")

# ==============================================================================
# MÉTODOS DE DETECCIÓN
# ==============================================================================
def method_difference(t1_path, t2_path, index_band=1, threshold=0.15):
    """Método 1: Resta simple (T2 - T1). Banda 1=NDVI."""
    log_message(f"--- Ejecutando Método 1: Diferencia Simple (Banda {index_band}) ---")
    img_t1, prof = load_masked_image(t1_path, [index_band])
    img_t2, _    = load_masked_image(t2_path, [index_band])
    
    # --- CAMBIO 2: SILENCIAR WARNINGS POR NaNs ---
    with np.errstate(invalid='ignore'):
        diff = img_t2[0] - img_t1[0]
        
        change_map = np.zeros_like(diff, dtype=np.int8)
        change_map[diff > threshold] = 1   # Ganancia
        change_map[diff < -threshold] = -1 # Pérdida
    
    valid_mask = np.isfinite(diff)
    total = np.count_nonzero(valid_mask)
    
    if total > 0:
        pos = np.count_nonzero(change_map == 1)
        neg = np.count_nonzero(change_map == -1)
        log_message(f"Ganancia (> {threshold}): {pos} px ({pos/total:.1%})")
        log_message(f"Pérdida (< -{threshold}): {neg} px ({neg/total:.1%})")
    
    out_name = f"cambio_diferencia_indices_{t1_path.stem.split('_')[1]}_{t2_path.stem.split('_')[1]}.tif"
    save_raster(change_map, prof, OUTPUT_DIR / out_name, description=f"Diff Band {index_band}")

def method_urban_classification(t1_path, t2_path):
    """Método 2: Clasificación Urbana (NDVI + NDBI + NDWI)."""
    log_message(f"--- Ejecutando Método 2: Clasificación Urbana ---")
    img_t1, prof = load_masked_image(t1_path, [1, 2, 3])
    img_t2, _    = load_masked_image(t2_path, [1, 2, 3])
    
    ndvi_t1, ndbi_t1, ndwi_t1 = img_t1
    ndvi_t2, ndbi_t2, ndwi_t2 = img_t2
    
    clase = np.zeros_like(ndvi_t1, dtype=np.int8)
    valid = np.isfinite(ndvi_t1) & np.isfinite(ndvi_t2)
    
    # --- CAMBIO 2: SILENCIAR WARNINGS EN LOGICA BOOLEANA ---
    with np.errstate(invalid='ignore'):
        # 1. Urbanización: Veg -> Urbano (NDBI aumenta)
        mask_urb = (ndvi_t1 > 0.3) & (ndbi_t2 > 0.0) & ((ndbi_t2 - ndbi_t1) > 0.1)
        clase[mask_urb & valid] = 1
        
        # 2. Pérdida Veg (No urbana): Veg -> Suelo
        mask_loss = (ndvi_t1 > 0.3) & ((ndvi_t1 - ndvi_t2) > 0.1) & (ndbi_t2 <= 0.0)
        clase[mask_loss & valid & (clase == 0)] = 2
        
        # 3. Ganancia Veg
        mask_gain = (ndvi_t2 > 0.3) & ((ndvi_t2 - ndvi_t1) > 0.1)
        clase[mask_gain & valid & (clase == 0)] = 3
        
        # 4. Agua
        mask_new_water = (ndwi_t1 < 0.0) & (ndwi_t2 > 0.0)
        clase[mask_new_water & valid & (clase == 0)] = 4
    
    counts = np.bincount(clase[valid & (clase > 0)].flatten())
    labels = {1: "Urbanización", 2: "Pérdida Veg", 3: "Ganancia Veg", 4: "Nuevo Agua"}
    
    for k, v in labels.items():
        if k < len(counts):
            log_message(f"Clase {v}: {counts[k]} px (~{counts[k]*0.01:.1f} ha)")

    out_name = f"cambio_urbano_{t1_path.stem.split('_')[1]}_{t2_path.stem.split('_')[1]}.tif"
    save_raster(clase, prof, OUTPUT_DIR / out_name, description="Urban Change Classification")

def method_anomaly(target_year):
    """Método 3: Z-Score Histórico (Criterio 7.0 - Serie Temporal)."""
    log_message(f"--- Ejecutando Método 3: Anomalías Temporales (Target: {target_year}) ---")
    all_files = sorted(list(PROCESSED_DIR.glob("indices_*.tif")))
    history_files = [f for f in all_files if str(target_year) not in f.name]
    target_file = next((f for f in all_files if str(target_year) in f.name), None)
    
    if not target_file or not history_files:
        log_message("❌ Error: Faltan datos para análisis histórico.")
        return

    stack = []
    for f in history_files:
        img, prof = load_masked_image(f, [1])
        stack.append(img[0])
    
    # Silenciar warnings también en la media/std si hay muchos NaNs
    with np.errstate(invalid='ignore'):
        stack = np.array(stack)
        mean_hist = np.nanmean(stack, axis=0)
        std_hist = np.nanstd(stack, axis=0)
        
        target_img, _ = load_masked_image(target_file, [1])
        current = target_img[0]
        
        # Z-Score
        # z = (x - u) / s
        with np.errstate(divide='ignore'): # Ignorar división por cero también
            z_score = (current - mean_hist) / (std_hist + 1e-6)
        
        z_score[~np.isfinite(z_score)] = 0
    
    out_name = f"anomalia_temporal_{target_year}.tif"
    prof.update(dtype=rasterio.float32, nodata=np.nan)
    save_raster(z_score, prof, OUTPUT_DIR / out_name, description=f"NDVI Z-Score {target_year}")

# ==============================================================================
# MAIN (CON VALIDACIONES)
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detección de Cambios Multitemporal")
    parser.add_argument("--t1", type=int, default=2019, help="Año inicial (Base)")
    parser.add_argument("--t2", type=int, default=2025, help="Año final (Target)")
    parser.add_argument("--method", type=str, default="all", choices=["diff", "urban", "anomaly", "all"])
    
    args = parser.parse_args()
    
    # --- VALIDACIONES ---
    MIN_YEAR, MAX_YEAR = 2019, 2025
    if not (MIN_YEAR <= args.t1 <= MAX_YEAR) or not (MIN_YEAR <= args.t2 <= MAX_YEAR):
        print(f"❌ Error: Los años deben estar entre {MIN_YEAR} y {MAX_YEAR}.")
        sys.exit(1)

    if args.t1 >= args.t2:
        print(f"❌ Error Lógico: El año base (t1={args.t1}) debe ser ANTERIOR al año objetivo (t2={args.t2}).")
        sys.exit(1)

    file_t1 = PROCESSED_DIR / f"indices_{args.t1}.tif"
    file_t2 = PROCESSED_DIR / f"indices_{args.t2}.tif"
    
    if not file_t1.exists() or not file_t2.exists():
        print(f"❌ Error: Faltan archivos de índices.")
        sys.exit(1)
        
    # --- EJECUCIÓN ---
    print(f"🚀 Iniciando Detección de Cambios: {args.t1} -> {args.t2}")
    
    if args.method in ["diff", "all"]:
        method_difference(file_t1, file_t2, index_band=1, threshold=0.15)
        
    if args.method in ["urban", "all"]:
        method_urban_classification(file_t1, file_t2)
        
    if args.method in ["anomaly", "all"]:
        method_anomaly(args.t2)
        
    print(f"\n🏁 Proceso finalizado. Resultados en {OUTPUT_DIR}")