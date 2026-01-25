import ee
import geemap
import os
from pathlib import Path

# ==============================================================================
# CONFIGURACIÓN DE PROYECTO
# ==============================================================================
DEFAULT_GEE_PROJECT = "composed-augury-451119-b6" 

# ==============================================================================
# CONFIGURACIÓN DE RUTAS
# ==============================================================================
script_location = Path(__file__).parent.resolve()
output_dir = script_location.parent / "data" / "raw"
output_dir.mkdir(parents=True, exist_ok=True)

print(f"📍 Los datos se guardarán en: {output_dir}")

# ==============================================================================
# INICIALIZACIÓN ROBUSTA
# ==============================================================================
def init_gee():
    project = os.environ.get('EE_PROJECT') or DEFAULT_GEE_PROJECT
    print(f"🔌 Conectando a GEE con proyecto: {project}...")
    try:
        ee.Initialize(project=project)
        print(f"✅ GEE inicializado correctamente.")
    except Exception:
        try:
            ee.Authenticate()
            ee.Initialize(project=project)
        except Exception as e:
            print(f"❌ Error fatal: {e}")
            exit(1)

init_gee()

# ==============================================================================
# PARÁMETROS VIÑA DEL MAR
# ==============================================================================
geometry = ee.Geometry.Rectangle([-71.58, -33.08, -71.40, -32.95])

# DEFINITIVO: 7 Fechas (2019-2025) para asegurar el Bonus (Más de 6 fechas)
years = range(2019, 2026) 

bands = ["B2", "B3", "B4", "B8", "B11", "B12"]

# ==============================================================================
# FUNCIONES
# ==============================================================================
def mask_clouds_s2(image):
    qa = image.select("QA60")
    cloud_mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return image.updateMask(cloud_mask).divide(10000) \
                .select(bands) \
                .copyProperties(image, ["system:time_start"])

# ==============================================================================
# PROCESO DE DESCARGA
# ==============================================================================
print(f"🚀 Iniciando descarga para {len(years)} fechas (2019-2025)...\n")

for year in years:
    filename = f"sentinel2_{year}.tif"
    output_path = output_dir / filename
    
    # Verificar si ya existe para ahorrar tiempo
    if output_path.exists():
        if output_path.stat().st_size < 1000: 
            os.remove(output_path) # Borrar si es basura
        else:
            print(f"✅ [YA EXISTE] {filename}")
            continue

    # Filtro ESTRICTO: 10% de nubosidad para máxima calidad
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geometry)
        .filterDate(f"{year}-01-01", f"{year}-02-28")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 10)) 
        .map(mask_clouds_s2)
    )
    
    if collection.size().getInfo() == 0:
        print(f"⚠️ [AVISO] No hay imágenes limpias para {year}")
        continue
        
    composite = collection.median().clip(geometry)
    
    print(f"⬇️ [DESCARGANDO] {filename} ...")
    
    try:
        # Descarga robusta por partes
        geemap.download_ee_image(
            composite,
            filename=str(output_path),
            scale=10,
            region=geometry,
            crs='EPSG:32719', # UTM 19S
            overwrite=True
        )
        
        if output_path.exists() and output_path.stat().st_size > 1000:
            print(f"✨ Guardado exitoso: {filename} ({output_path.stat().st_size / 1024 / 1024:.2f} MB)")
        else:
            print(f"❌ Falló la descarga de {filename}")
            
    except Exception as e:
        print(f"❌ Error descargando {year}: {e}")

print("\n🏁 Proceso completado. Datos listos en data/raw/")