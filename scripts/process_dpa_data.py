import geopandas as gpd
from pathlib import Path

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
# Nombre exacto de la comuna a buscar
COMUNA_OBJETIVO = "Viña del Mar"

# Rutas automáticas
script_location = Path(__file__).parent.resolve()
vector_dir = script_location.parent / "data" / "vector"

# Ruta donde pegaste la carpeta COMUNAS (dentro de data/vector)
input_shapefile = vector_dir / "DPA_2023" / "COMUNAS" / "COMUNAS_v1.shp"
output_file = vector_dir / "limite_comuna.gpkg"

print(f"📍 Carpeta de trabajo: {vector_dir}")

# ==============================================================================
# PROCESAMIENTO
# ==============================================================================
def procesar_oficial():
    if not input_shapefile.exists():
        print(f"❌ ERROR: No encuentro el archivo en: {input_shapefile}")
        print("⚠️ Asegúrate de copiar la carpeta 'COMUNAS' dentro de 'data/vector/'")
        return

    print(f"📖 Leyendo base de datos oficial IDE Chile: {input_shapefile.name}...")
    
    try:
        # Cargar el shapefile completo
        gdf = gpd.read_file(input_shapefile)
        
        # Verificar columnas (sabemos que existe 'COMUNA' gracias a tu log anterior)
        print(f"📊 Columnas disponibles: {gdf.columns.tolist()[:5]}...") 
        
        # Filtrar Viña del Mar
        print(f"🔍 Buscando '{COMUNA_OBJETIVO}'...")
        gdf_vina = gdf[gdf["COMUNA"].astype(str).str.contains(COMUNA_OBJETIVO, case=False, na=False)]

        if gdf_vina.empty:
            print(f"❌ No se encontró la comuna. ¿Quizás está escrita distinto?")
            return

        # Proyección: El DPA suele venir en coordenadas geográficas (EPSG:4326) o SIRGAS.
        # Necesitamos pasarlo a UTM 19S (EPSG:32719) para que calce con el satélite.
        print(f"🔄 Reproyectando de {gdf_vina.crs} a EPSG:32719 (UTM 19S)...")
        gdf_vina = gdf_vina.to_crs("EPSG:32719")

        # Guardar sobrescribiendo el archivo anterior de OSM
        gdf_vina.to_file(output_file, driver="GPKG")
        print(f"✨ ¡ÉXITO! Límite oficial guardado en: {output_file}")
        print("✅ Ahora cumples 100% con el requisito de fuente 'IDE Chile'.")
        
    except Exception as e:
        print(f"❌ Error procesando: {e}")

if __name__ == "__main__":
    procesar_oficial()