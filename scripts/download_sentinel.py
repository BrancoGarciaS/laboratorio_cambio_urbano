import ee
import geemap
import os
from pathlib import Path
from datetime import datetime

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DEFAULT_GEE_PROJECT = "composed-augury-451119-b6" 
script_location = Path(__file__).parent.resolve()
output_dir = script_location.parent / "data" / "raw"
output_dir.mkdir(parents=True, exist_ok=True)
metadata_file = output_dir / "metadata.txt"

print(f"📍 Los datos se guardarán en: {output_dir}")

# Reiniciar archivo de metadatos al iniciar el script
with open(metadata_file, "w", encoding="utf-8") as f:
    f.write(f"METADATOS DE IMÁGENES SATELITALES\n")
    f.write(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("="*50 + "\n\n")

def log_metadata(filename, year):
    """Escribe los metadatos técnicos en el archivo de texto."""
    with open(metadata_file, "a", encoding="utf-8") as f:
        f.write(f"Archivo: {filename}\n")
        f.write(f" - Sensor: Sentinel-2 (COPERNICUS/S2_SR_HARMONIZED)\n")
        f.write(f" - Año: {year}\n")
        f.write(f" - Rango Temporal: 01 Enero - 30 Marzo (Verano)\n")
        f.write(f" - Filtro Nubosidad: < 30% (Pixel Percentage)\n")
        f.write(f" - Procesamiento: Mediana Temporal (Cloud Masking + Median Composite)\n")
        f.write(f" - Bandas: B2, B3, B4, B8, B11, B12\n")
        f.write("-" * 30 + "\n")

def init_gee():
    project = os.environ.get('EE_PROJECT') or DEFAULT_GEE_PROJECT
    print(f"🔌 Conectando a GEE con proyecto: {project}...")
    try:
        ee.Initialize(project=project)
        print(f"✅ GEE inicializado.")
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)

init_gee()

# Geometría Exacta (Viña del Mar + Margen)
geometry = ee.Geometry.Rectangle([-71.607, -33.125, -71.423, -32.925])
years = range(2019, 2026) 
bands = ["B2", "B3", "B4", "B8", "B11", "B12"]

def mask_clouds_s2(image):
    qa = image.select("QA60")
    # Bits 10 y 11 son nubes y cirrus
    cloud_mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return image.updateMask(cloud_mask).divide(10000).select(bands).clamp(0, 1).copyProperties(image, ["system:time_start"])

print(f"🚀 Iniciando descarga (Filtro Relajado 30% Nubes) + Metadatos...\n")

for year in years:
    filename = f"sentinel2_{year}.tif"
    output_path = output_dir / filename
    
    # Si ya existe, solo registramos el metadato y saltamos
    if output_path.exists():
        if output_path.stat().st_size > 1000:
            print(f"✅ [YA EXISTE] {filename}")
            log_metadata(filename, year) # Registrar metadato aunque no se descargue
            continue
        else:
            os.remove(output_path) # Borrar basura

    # --- DESCARGA ---
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geometry)
        .filterDate(f"{year}-01-01", f"{year}-03-30") 
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)) 
        .map(mask_clouds_s2)
    )
    
    count = collection.size().getInfo()
    if count == 0:
        print(f"⚠️ [AVISO] Cero imágenes para {year}")
        continue
        
    print(f"⬇️ [DESCARGANDO] {filename} (Usando {count} imágenes candidatas)...")
    
    composite = collection.median().clip(geometry)
    
    try:
        geemap.download_ee_image(
            composite,
            filename=str(output_path),
            scale=10,
            region=geometry,
            crs='EPSG:32719',
            overwrite=True
        )
        print(f"✨ Éxito: {filename}")
        log_metadata(filename, year) # Registrar metadato tras descarga exitosa
    except Exception as e:
        print(f"❌ Error: {e}")

print(f"\n🏁 Listo. Metadatos guardados en: {metadata_file}")