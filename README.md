# Laboratorio 2: Cambio Urbano
- Análisis Multitemporal con Imágenes Satelitales
- Desarrollo de Aplicaciones Geoinformáticas

## Descripción

Este laboratorio tiene los siguientes objetivos:

- **Objetivo general:** Desarrollar un sistema completo de detección y cuantificación de cambios urbanos utilizando series temporales de imágenes satelitales, aplicando técnicas de teledetección y visualización interactiva. 
- **Objetivos Específicos:**
1. Adquirir y procesar series temporales de imágenes Sentinel-2 o Landsat 
2. Calcular índices espectrales (NDVI, NDBI, NDWI) para múltiples fechas 
3. Implementar algoritmos de detección de cambios 
4. Clasificar tipos de cambio (urbanización, pérdida de vegetación, etc.) 
5. Cuantificar cambios por sector/zona 
6. Desarrollar un dashboard interactivo para explorar los resultados

## Información del equipo

| Integrante | Rol | GitHub |
|------------|-----|--------|
| Branco García | Ingeniero y ciencista de datos geoespaciales | [@BrancoGarciaS](https://github.com/BrancoGarciaS) |
| Aracely Castro | Analista geoestadística y desarrolladora web | [@AracelyU](https://github.com/AracelyU) |

**Comuna seleccionada:** Viña del Mar  
**Período de análisis:** 2019 - 2025  
**Repositorio del equipo:** [github.com/BrancoGarciaS/laboratorio_cambio_urbano](https://github.com/BrancoGarciaS/laboratorio_cambio_urbano)  
**Repositorio del curso:** [github.com/franciscoparrao/geoinformatica](https://github.com/franciscoparrao/geoinformatica)

---

## Estructura del Proyecto

```
laboratorio_cambio_urbano/
├── app/                        # Dashboard interactivo (Parte 5)
│   ├── app.py                  # Aplicación Streamlit principal
│   ├── config.py               # Configuración de la app
│   ├── utils.py                # Funciones auxiliares
│   └── utils/                  # Datos y salidas para la app
├── data/
│   ├── raw/                    # Imágenes Sentinel-2 originales
│   ├── processed/              # Índices espectrales calculados
│   ├── validation/             # Datos Dynamic World para validación
│   └── vector/                 # Archivos vectoriales (límites, manzanas, vías)
├── notebooks/                  # Jupyter Notebooks documentados
│   ├── 01_descarga_datos.ipynb
│   ├── 02_calculo_indices.ipynb
│   ├── 03_deteccion_cambios.ipynb
│   └── 04_analisis_zonal.ipynb
├── outputs/
│   ├── figures/                # Gráficos y visualizaciones
│   ├── maps/                   # Mapas generados
│   └── reports/                # Reportes CSV
├── scripts/                    # Scripts Python ejecutables
│   ├── download_sentinel.py    # Descarga imágenes satelitales
│   ├── download_vectors.py     # Descarga datos vectoriales
│   ├── download_validation.py  # Descarga datos Dynamic World
│   ├── calculate_indices.py    # Cálculo de índices espectrales
│   ├── detect_changes.py       # Detección de cambios
│   ├── zonal_analysis.py       # Análisis zonal
│   └── crear_gif_indices.py    # Generación de GIFs animados
├── requirements.txt            # Dependencias del proyecto
├── enunciado.txt               # Enunciado del laboratorio
└── README.md                   # Este archivo
```

---

## Requisitos Previos

### Software necesario
- Python 3.9 o superior
- Git
- Cuenta de Google Earth Engine (gratuita)

### Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/BrancoGarciaS/laboratorio_cambio_urbano.git
cd laboratorio_cambio_urbano

# 2. Crear entorno virtual (recomendado)
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Autenticarse en Google Earth Engine (primera vez)
earthengine authenticate
```

### Dependencias principales
| Paquete | Uso |
|---------|-----|
| `earthengine-api`, `geemap` | Acceso a Google Earth Engine |
| `rasterio` | Lectura/escritura de archivos raster |
| `geopandas` | Procesamiento de datos vectoriales |
| `rasterstats` | Estadísticas zonales |
| `streamlit` | Dashboard interactivo |
| `folium` | Mapas interactivos |
| `plotly`, `matplotlib` | Visualizaciones |

---

## Flujo de Trabajo

El laboratorio se desarrolla en **5 partes secuenciales**. Cada parte puede ejecutarse mediante **scripts** (línea de comandos) o **notebooks** (interactivo con visualizaciones):

1. Adquisición de datos
2. Cálculo de índices
3. Detección de cambios
4. Análisis zonal
5. Dashboard interactivo

---

## Parte 1: Adquisición de Datos (15%)

**Objetivo:** Descargar y organizar series temporales de imágenes satelitales y datos vectoriales.

### 1.1 Descarga de imágenes Sentinel-2

**Script:** `scripts/download_sentinel.py`  
**Notebook:** `notebooks/01_descarga_datos.ipynb`

Este script descarga imágenes Sentinel-2 desde Google Earth Engine para el período 2019-2025. Incluye un plan B de descarga desde Google Drive si GEE no está disponible.

```bash
# Ejecutar script de descarga de imágenes
python scripts/download_sentinel.py
```

**Configuración:**
- Área de estudio: Viña del Mar (coordenadas: [-71.607, -33.125, -71.423, -32.925])
- Período: Enero-Marzo de cada año (verano austral)
- Filtro de nubosidad: < 30%
- Bandas descargadas: B2 (Blue), B3 (Green), B4 (Red), B8 (NIR), B11 (SWIR1), B12 (SWIR2)

**Salidas:**
- `data/raw/sentinel2_YYYY.tif` - Imágenes compuestas por año
- `data/raw/metadata.txt` - Metadatos de las imágenes

### 1.2 Descarga de datos vectoriales

**Script:** `scripts/download_vectors.py`

Descarga límites comunales, manzanas censales y red vial.

```bash
# Ejecutar script de descarga de vectores
python scripts/download_vectors.py
```

**Fuentes de datos:**
| Dato | Fuente | Formato |
|------|--------|---------|
| Límites comunales | IDE Chile / Geoportal | GeoPackage |
| Manzanas censales | INE (Censo 2017) | Shapefile |
| Red vial | OpenStreetMap | GeoJSON |

**Salidas:**
- `data/vector/limite_comuna.gpkg`
- `data/vector/manzanas_censales.shp`
- `data/vector/red_vial.geojson`
- `data/vector/metadata.txt`

### 1.3 Descarga de datos de validación (opcional)

**Script:** `scripts/download_validation.py`

Descarga clasificaciones de cobertura terrestre de Google Dynamic World para validar los resultados.

```bash
# Ejecutar script de descarga de datos de validación
python scripts/download_validation.py
```

**Salidas:**
- `data/validation/dynamic_world_YYYY.tif` - Clasificación modal por año
- `data/validation/README_CLASSES.txt` - Descripción de clases

### 1.4 Notebook interactivo

El notebook `01_descarga_datos.ipynb` permite:
- Ejecutar los scripts de descarga desde el notebook
- Visualizar el área de estudio en un mapa interactivo
- Previsualizar las imágenes descargadas
- Verificar la cobertura de nubes

---

## Parte 2: Procesamiento y Cálculo de Índices (20%)

**Objetivo:** Calcular índices espectrales para caracterizar vegetación, construcciones, agua y suelo.

### 2.1 Índices espectrales calculados

| Índice | Nombre | Fórmula | Interpretación |
|--------|--------|---------|----------------|
| **NDVI** | Normalized Difference Vegetation Index | (NIR - Red) / (NIR + Red) | Vegetación: valores altos (+1) = densa |
| **NDBI** | Normalized Difference Built-up Index | (SWIR - NIR) / (SWIR + NIR) | Construcciones: valores altos = urbano |
| **NDWI** | Normalized Difference Water Index | (Green - NIR) / (Green + NIR) | Agua: valores positivos = presencia |
| **BSI** | Bare Soil Index | ((SWIR+Red)-(NIR+Blue)) / ((SWIR+Red)+(NIR+Blue)) | Suelo desnudo: valores altos |

### 2.2 Ejecución

**Script:** `scripts/calculate_indices.py`  
**Notebook:** `notebooks/02_calculo_indices.ipynb`

```bash
# Ejecutar cálculo de índices para todas las imágenes
python scripts/calculate_indices.py
```

**Salidas:**
- `data/processed/indices_YYYY.tif` - GeoTIFF con 4 bandas (NDVI, NDBI, NDWI, BSI)
- `data/processed/metadata.txt` - Estadísticas de cada índice
- `outputs/reports/02_estadisticas_anuales.csv` - Resumen estadístico
- `outputs/reports/02_superficies_clasificadas.csv` - Superficies por clase

### 2.3 Notebook interactivo

El notebook `02_calculo_indices.ipynb` incluye:
- Ejecución del script de cálculo
- Mapas comparativos lado a lado por año
- Histogramas de distribución de valores
- Series temporales de valores promedio
- Clasificación supervisada de cobertura
- Generación de tablas de superficies

### 2.4 Generación de GIF animado (opcional)

```bash
# Crear animación temporal de índices
python scripts/crear_gif_indices.py
```

**Salida:** `outputs/figures/animacion_NDVI.gif`

---

## Parte 3: Detección de Cambios (25%)

**Objetivo:** Implementar algoritmos para detectar y clasificar cambios urbanos.

### 3.1 Métodos implementados

#### Método 1: Diferencia de índices
Resta simple entre índices de dos fechas. Detecta cambios positivos (ganancia) y negativos (pérdida).

#### Método 2: Clasificación de cambio urbano
Combina NDVI, NDBI y NDWI para clasificar tipos específicos de cambio:

| Código | Clase | Descripción |
|--------|-------|-------------|
| 0 | Sin cambio | Área estable |
| 1 | Nueva urbanización | Aumento de NDBI, pérdida de vegetación |
| 2 | Pérdida de vegetación | Disminución significativa de NDVI |
| 3 | Ganancia de vegetación | Aumento significativo de NDVI |
| 4 | Nuevo cuerpo de agua | Aparición de NDWI positivo |

#### Método 3: Análisis de anomalías temporales
Calcula Z-Score comparando un año contra la serie histórica completa.

### 3.2 Ejecución

**Script:** `scripts/detect_changes.py`  
**Notebook:** `notebooks/03_deteccion_cambios.ipynb`

```bash
# Ejecutar todos los métodos de detección
python scripts/detect_changes.py --t1 2019 --t2 2025 --method all

# Ejecutar solo diferencia de índices
python scripts/detect_changes.py --t1 2019 --t2 2025 --method diff

# Ejecutar solo clasificación urbana
python scripts/detect_changes.py --t1 2019 --t2 2025 --method urban

# Ejecutar solo análisis de anomalías
python scripts/detect_changes.py --t1 2019 --t2 2025 --method anomaly
```

**Argumentos:**
| Argumento | Descripción | Valores |
|-----------|-------------|---------|
| `--t1` | Año inicial (base) | 2019-2024 |
| `--t2` | Año final (objetivo) | 2020-2025 |
| `--method` | Método a ejecutar | `diff`, `urban`, `anomaly`, `all` |

**Salidas:**
- `data/processed/cambio_diff_YYYY_YYYY.tif` - Diferencia de índices
- `data/processed/cambio_urban_YYYY_YYYY.tif` - Clasificación de cambio
- `data/processed/cambio_anomaly_YYYY.tif` - Anomalías temporales
- `data/processed/metadata_changes.txt` - Log de operaciones
- `outputs/reports/03_matriz_confusion.csv` - Matriz de confusión (si hay validación)

### 3.3 Notebook interactivo

El notebook `03_deteccion_cambios.ipynb` incluye:
- Ejecución de scripts de detección y validación
- Visualización de mapas de cambio
- Comparación de métodos
- Validación con datos Dynamic World
- Cálculo de métricas (Precisión, Recall, F1-Score)
- Generación de matriz de confusión

---

## Parte 4: Cuantificación y Análisis Zonal (20%)

**Objetivo:** Cuantificar los cambios por zonas administrativas (manzanas censales).

### 4.1 Análisis realizados

- Estadísticas zonales de cambio por manzana censal
- Porcentaje de área urbanizada por zona
- Identificación de zonas con mayor transformación
- Evolución temporal de índices espectrales (NDVI, NDBI)
- Clasificación de niveles de urbanización

### 4.2 Ejecución

**Notebook:** `notebooks/04_analisis_zonal.ipynb`

> **Nota:** El análisis zonal se realiza completamente en el notebook interactivo, ya que requiere visualización y exploración de resultados.

Para ejecutar el análisis zonal:
1. Abrir el notebook `notebooks/04_analisis_zonal.ipynb`
2. Ejecutar todas las celdas secuencialmente
3. Los resultados se guardan automáticamente en `outputs/`

### 4.3 Contenido del Notebook

El notebook `04_analisis_zonal.ipynb` implementa:

| Celda | Descripción |
|-------|-------------|
| **1** | Importación de librerías y configuración de rutas |
| **2** | Función `analisis_zonal_cambios()` - Cálculo de estadísticas por manzana censal |
| **3** | Mapa coroplético de intensidad de urbanización (hectáreas) |
| **4** | Clasificación por niveles de urbanización (Bajo/Medio/Alto) |
| **5** | Análisis temporal de índices espectrales (NDVI y NDBI) |

### 4.4 Funciones principales

#### `analisis_zonal_cambios(ruta_cambios, ruta_zonas, columna_zona)`
Calcula estadísticas zonales a partir del raster de cambios clasificado:
- Conteo de píxeles por categoría (urbanización, pérdida/ganancia vegetación, agua)
- Porcentajes relativos por zona
- Conversión a hectáreas (10x10m = 0.01 ha por píxel)

#### `analisis_temporal(lista_indices, fechas, mascara_area)`
Analiza la evolución temporal de NDVI y NDBI:
- Estadísticas descriptivas (media, desviación estándar)
- Porcentaje de cobertura vegetal y urbana
- Gráficos de evolución anual

### 4.5 Salidas generadas

| Archivo | Descripción |
|---------|-------------|
| `outputs/reports/04_cambios_por_zona.csv` | Estadísticas por manzana censal |
| `outputs/maps/04_mapa_coropletico_urbanizacion.png` | Mapa de intensidad de urbanización |
| `outputs/maps/04_nivel_urbanizacion.png` | Mapa de niveles categóricos |
| `outputs/figures/04_evolucion_temporal_indices.png` | Gráficos de evolución NDVI/NDBI |

---

## Parte 5: Dashboard Interactivo (20%)

**Objetivo:** Desarrollar una aplicación web para explorar los resultados de forma interactiva.

### 5.1 Características del dashboard

- **Selector temporal:** Comparar cualquier par de años (2019-2025)
- **Selector de índice:** Visualizar NDVI, NDBI, NDWI o BSI
- **Mapa interactivo:** Límites comunales, red vial y manzanas censales
- **Gráficos dinámicos:** Evolución temporal, distribución de cambios
- **Tabla de datos:** Estadísticas por zona exportables

### 5.2 Ejecución

```bash
# Navegar a la carpeta de la aplicación
cd app

# Ejecutar el dashboard
streamlit run app.py
```

O desde la raíz del proyecto:

```bash
streamlit run app/app.py
```

**Acceso:** El dashboard estará disponible en `http://localhost:8501`

### 5.3 Estructura de la aplicación

```
app/
├── app.py              # Aplicación principal Streamlit
├── config.py           # Configuración (rutas, colores, etc.)
├── utils.py            # Funciones auxiliares
└── utils/
    ├── data/vector/    # Datos vectoriales para la app
    └── outputs/        # Reportes CSV para la app
```

---

## Ejecución Completa (Secuencial)

Para ejecutar todo el flujo de trabajo desde cero:

```bash
# 1. Activar entorno virtual
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. PARTE 1: Descarga de datos
python scripts/download_sentinel.py
python scripts/download_vectors.py
python scripts/download_validation.py

# 3. PARTE 2: Cálculo de índices
python scripts/calculate_indices.py

# 4. PARTE 3: Detección de cambios
python scripts/detect_changes.py --t1 2019 --t2 2025 --method all

# 5. PARTE 4: Análisis zonal (ejecutar notebook)
# Abrir y ejecutar: notebooks/04_analisis_zonal.ipynb

# 6. PARTE 5: Dashboard interactivo
streamlit run app/app.py
```

## Streamlit Cloud
El dashboard estará disponible en streamlit cloud para que pueda ser utilizada, accediendo al siguiente url:

https://laboratoriocambiourbano-j42t7qv36xtuavrvq4claj.streamlit.app/

---

## Notebooks vs Scripts

| Componente | Script (CLI) | Notebook (Interactivo) |
|------------|--------------|------------------------|
| **Parte 1** | `download_sentinel.py`, `download_vectors.py`, `download_validation.py` | `01_descarga_datos.ipynb` |
| **Parte 2** | `calculate_indices.py` | `02_calculo_indices.ipynb` |
| **Parte 3** | `detect_changes.py` | `03_deteccion_cambios.ipynb` |
| **Parte 4** | N/A (solo notebook) | `04_analisis_zonal.ipynb` |
| **Parte 5** | `app/app.py` | N/A (solo Streamlit) |

**Recomendación:** 
- Usar **notebooks** para exploración, visualización y documentación
- Usar **scripts** para ejecución automatizada y reproducibilidad

---

## Entregables por Parte

### Parte 1: Adquisición de Datos
- [x] Mínimo 4 imágenes de diferentes años (2019, 2021, 2023, 2025)
- [x] Scripts de descarga documentados
- [x] Metadatos de cada imagen (`data/raw/metadata.txt`)
- [x] Justificación de fechas seleccionadas

### Parte 2: Cálculo de Índices
- [x] Rasters de índices para cada fecha (`data/processed/`)
- [x] Visualización comparativa de índices (notebook)
- [x] Estadísticas descriptivas (`outputs/reports/02_*.csv`)
- [x] Notebook documentado

### Parte 3: Detección de Cambios
- [x] Implementación de 3 métodos de detección
- [x] Mapa de cambios clasificado (`data/processed/cambio_*.tif`)
- [x] Comparación de métodos (notebook)
- [x] Matriz de confusión (`outputs/reports/03_matriz_confusion.csv`)

### Parte 4: Análisis Zonal
- [x] Tabla de cambios por zona (`outputs/reports/04_cambios_por_zona.csv`)
- [x] Gráficos de evolución temporal
- [x] Mapa coroplético de intensidad de cambio
- [x] Interpretación de resultados (notebook)

### Parte 5: Dashboard
- [x] Aplicación Streamlit funcional (`app/app.py`)
- [x] Controles interactivos (años, índices)
- [x] Mapas y gráficos dinámicos
- [x] Documentación de uso

---

## Problemas comunes

### Error de autenticación en Google Earth Engine

```bash
# Reautenticarse
earthengine authenticate

# Verificar configuración
earthengine set_project YOUR_PROJECT_ID
```

### Error de dependencias faltantes

```bash
# Reinstalar todas las dependencias
pip install -r requirements.txt --upgrade
```

### Los archivos raster no se encuentran

Verificar que se ejecutaron los scripts en orden:
1. Primero `download_sentinel.py` → genera archivos en `data/raw/`
2. Luego `calculate_indices.py` → requiere archivos en `data/raw/`

### El dashboard no carga los datos

Verificar que existen los archivos CSV en `app/utils/outputs/reports/`:
- `02_estadisticas_anuales.csv`
- `02_superficies_clasificadas.csv`
- `03_matriz_confusion.csv`
- `04_cambios_por_zona.csv`

---

## Referencias

- [Google Earth Engine Documentation](https://developers.google.com/earth-engine)
- [Sentinel-2 User Handbook](https://sentinel.esa.int/web/sentinel/user-guides/sentinel-2-msi)
- [Dynamic World Dataset](https://dynamicworld.app/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [GeoPandas Documentation](https://geopandas.org/)
- [Rasterio Documentation](https://rasterio.readthedocs.io/)

---
