# 📁 Carpeta `data/`

Contiene todos los datos del proyecto: imágenes satelitales, índices procesados, datos de validación y archivos vectoriales.

---

## Generación de datos

```bash
# 1. Descargar imágenes Sentinel-2
python scripts/download_sentinel.py

# 2. Descargar datos vectoriales
python scripts/download_vectors.py

# 3. Descargar datos de validación (Dynamic World)
python scripts/download_validation.py

# 4. Calcular índices espectrales
python scripts/calculate_indices.py

# 5. Detectar cambios
python scripts/detect_changes.py --t1 2019 --t2 2025 --method all
```

---

## `raw/` — Imágenes Sentinel-2 originales

Composiciones anuales descargadas desde Google Earth Engine.

| Archivo | Descripción |
|---------|-------------|
| `sentinel2_YYYY.tif` | Imagen compuesta del año YYYY |
| `metadata.txt` | Metadatos técnicos |

**Bandas:** B2 (Blue), B3 (Green), B4 (Red), B8 (NIR), B11 (SWIR1), B12 (SWIR2)  
**Período:** Enero-Marzo (verano austral)  
**Nubosidad:** < 30%

---

## `processed/` — Índices espectrales y cambios

Productos derivados del procesamiento de imágenes.

| Archivo | Descripción |
|---------|-------------|
| `indices_YYYY.tif` | Índices espectrales (4 bandas) |
| `cambio_urban_YYYY_YYYY.tif` | Clasificación de cambio urbano |
| `cambio_diff_YYYY_YYYY.tif` | Diferencia de índices |
| `cambio_anomaly_YYYY.tif` | Anomalías temporales (Z-Score) |
| `metadata.txt` | Estadísticas de índices |
| `metadata_changes.txt` | Log de detección de cambios |

**Bandas de índices:** 1:NDVI, 2:NDBI, 3:NDWI, 4:BSI

**Clases de cambio urbano:**
| Código | Clase |
|--------|-------|
| 0 | Sin cambio |
| 1 | Nueva urbanización |
| 2 | Pérdida de vegetación |
| 3 | Ganancia de vegetación |
| 4 | Nuevo cuerpo de agua |

---

## `validation/` — Datos de referencia (Ground Truth)

Clasificaciones de Google Dynamic World para validación.

| Archivo | Descripción |
|---------|-------------|
| `dynamic_world_YYYY.tif` | Clasificación modal del año YYYY |
| `README_CLASSES.txt` | Descripción de clases |

**Clases Dynamic World:**
| Código | Clase |
|--------|-------|
| 0 | Agua |
| 1 | Árboles |
| 2 | Pasto |
| 3 | Vegetación inundada |
| 4 | Cultivos |
| 5 | Arbustos |
| 6 | Construido (urbano) |
| 7 | Suelo desnudo |
| 8 | Nieve/Hielo |

---

## `vector/` — Datos vectoriales

Archivos geoespaciales para delimitación y análisis zonal.

| Archivo | Fuente | Descripción |
|---------|--------|-------------|
| `limite_comuna.gpkg` | IDE Chile | Límite comunal Viña del Mar |
| `manzanas_censales.shp` | INE (Censo 2017) | Manzanas para análisis zonal |
| `red_vial.geojson` | OpenStreetMap | Red vial (contexto) |
| `metadata.txt` | — | Metadatos técnicos |

**CRS:** EPSG:32719 (WGS 84 / UTM zona 19S)

---

## Notas

- Los archivos `.gitkeep` mantienen las carpetas vacías en el repositorio
- Todos los rasters están en formato GeoTIFF con compresión LZW
- El área de estudio es Viña del Mar: `[-71.607, -33.125, -71.423, -32.925]`
