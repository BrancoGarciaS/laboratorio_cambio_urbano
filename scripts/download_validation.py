import ee
import geemap
import os
from pathlib import Path

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DEFAULT_GEE_PROJECT = "composed-augury-451119-b6" 
script_location = Path(__file__).parent.resolve()
output_dir = script_location.parent / "data" / "validation"
output_dir.mkdir(parents=True, exist_ok=True)

print(f"📍 Los datos de validación se guardarán en: {output_dir}")

def init_gee():
    project = os.environ.get('EE_PROJECT') or DEFAULT_GEE_PROJECT
    try:
        ee.Initialize(project=project)
        print(f"✅ GEE inicializado.")
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)

init_gee()

# Geometría Exacta (Misma que download_sentinel.py)
geometry = ee.Geometry.Rectangle([-71.607, -33.125, -71.423, -32.925])

def get_dynamic_world_class(start_date, end_date):
    """Obtiene la moda de la clasificación Dynamic World para un rango de fechas."""
    dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1") \
        .filterBounds(geometry) \
        .filterDate(start_date, end_date) \
        .select('label') # Seleccionamos la etiqueta clasificada
    
    # Calculamos la moda (el valor más común en ese periodo para evitar nubes)
    classification = dw.reduce(ee.Reducer.mode()).clip(geometry)
    return classification

# Descargar Referencias para 2019 y 2025
years_ranges = [
    ("2019", "2019-06-01", "2020-01-01"), # DW empieza a mediados de 2019
    ("2025", "2024-10-01", "2025-03-30")  # Verano 2025
]

print("🚀 Descargando datos de validación (Dynamic World)...")

for year, start, end in years_ranges:
    filename = f"reference_lulc_{year}.tif"
    output_path = output_dir / filename
    
    if output_path.exists():
        print(f"✅ [YA EXISTE] {filename}")
        continue
        
    print(f"⬇️ [DESCARGANDO] Referencia {year}...")
    
    image = get_dynamic_world_class(start, end)
    
    try:
        geemap.download_ee_image(
            image,
            filename=str(output_path),
            scale=10,
            region=geometry,
            crs='EPSG:32719',
            overwrite=True
        )
        print(f"✨ Éxito: {filename}")
    except Exception as e:
        print(f"❌ Error: {e}")

# Crear un archivo de leyenda
readme_path = output_dir / "README_CLASSES.txt"
with open(readme_path, "w") as f:
    f.write("CLASES DYNAMIC WORLD:\n")
    f.write("0: Water\n1: Trees\n2: Grass\n3: Flooded Vegetation\n")
    f.write("4: Crops\n5: Shrub & Scrub\n6: Built (Urbano)\n7: Bare (Suelo)\n8: Snow & Ice")

print("\n🏁 Datos de validación listos.")