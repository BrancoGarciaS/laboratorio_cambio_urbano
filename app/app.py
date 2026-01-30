import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import rasterio
import numpy as np
from rasterio.plot import show
from PIL import Image
import os
import base64

# -------------------------------------------------
# CONFIGURACIÓN GENERAL
# -------------------------------------------------
st.set_page_config(
    page_title="Cambio Urbano – Viña del Mar",
    layout="wide"
)

st.title("📊 Análisis de Cambio Urbano – Viña del Mar")
st.markdown(
    """
    **Detección y análisis de cambios urbanos mediante imágenes satelitales Sentinel-2**  
    Periodo de estudio: **2019 – 2025**

    Esta aplicación permite visualizar cómo ha cambiado el territorio urbano y la
    cobertura vegetal de Viña del Mar a lo largo del tiempo, usando índices espectrales
    derivados de imágenes satelitales.
    """
)

# -------------------------------------------------
# SIDEBAR – CONTROLES
# -------------------------------------------------
st.sidebar.header("⚙️ Configuración")
st.sidebar.markdown(
    """
    Selecciona los años a comparar y el índice espectral a analizar.

    - **NDVI**: vegetación (valores altos = más verde)
    - **NDBI**: zonas construidas (valores altos = más urbano)
    - **NDWI**: presencia de agua/humedad
    - **BSI**: suelo desnudo
    """
)

anio_inicio = st.sidebar.selectbox(
    "Año inicial",
    [2019, 2020, 2021, 2022, 2023, 2024]
)

anio_fin = st.sidebar.selectbox(
    "Año final",
    [2020, 2021, 2022, 2023, 2024, 2025],
    index=5
)

indice_sel = st.sidebar.selectbox(
    "Índice a visualizar",
    ["NDVI", "NDBI", "NDWI", "BSI"]
)

# -------------------------------------------------
# CARGA DE DATOS
# -------------------------------------------------
@st.cache_data
def cargar_datos():
    cambios_zona = pd.read_csv("app/utils/outputs/reports/04_cambios_por_zona.csv")
    superficies = pd.read_csv("app/utils/outputs/reports/02_superficies_clasificadas.csv")
    estadisticas = pd.read_csv("app/utils/outputs/reports/02_estadisticas_anuales.csv")
    matriz_conf = pd.read_csv("app/utils/outputs/reports/03_matriz_confusion.csv")
    limite = gpd.read_file("app/utils/data/vector/limite_comuna.gpkg")
    red_vial = gpd.read_file("app/utils/data/vector/red_vial.geojson")
    manzanas_censales = gpd.read_file("app/utils/data/vector/manzanas_censales.shp")
    return cambios_zona, superficies, estadisticas, matriz_conf, limite, red_vial, manzanas_censales

cambios_zona, superficies, estadisticas, matriz_conf, limite, red_vial, manzanas_censales = cargar_datos()

# -------------------------------------------------
# LAYOUT PRINCIPAL
# -------------------------------------------------
col1, col2 = st.columns([2, 1])

# -------------------------------------------------
# MAPA INTERACTIVO
# -------------------------------------------------
with col1:
    st.subheader("🗺️ Mapa de referencia territorial")
    st.markdown(
        """
        Este mapa muestra el límite comunal de Viña del Mar y su red vial principal.
        Sirve como referencia espacial para ubicar los cambios detectados en los análisis.
        """
    )

    limite_wgs = limite.to_crs(epsg=4326)
    red_vial_wgs = red_vial.to_crs(epsg=4326)

    centro = [
        limite_wgs.geometry.centroid.y.mean(),
        limite_wgs.geometry.centroid.x.mean()
    ]

    m = folium.Map(location=centro, zoom_start=12, tiles="cartodbpositron")

    # --- LIMPIEZA DE RED VIAL PARA FOLIUM ---
    red_vial_wgs = red_vial_wgs.copy()

    # Convertir todo a string excepto geometría
    for col in red_vial_wgs.columns:
        if col != "geometry":
            red_vial_wgs[col] = red_vial_wgs[col].astype(str)

    # (opcional) quedarte solo con columnas relevantes
    red_vial_wgs = red_vial_wgs[["highway", "name", "geometry"]]


    folium.GeoJson(
        limite_wgs,
        name="Límite comunal",
        style_function=lambda x: {
            "fillOpacity": 0.1,
            "color": "black",
            "weight": 2
        }
    ).add_to(m)

    folium.GeoJson(
        red_vial_wgs,
        name="Red vial",
        style_function=lambda x: {
            "color": "gray",
            "weight": 1
        }
    ).add_to(m)

    folium.GeoJson(
    manzanas_censales,
    name="Manzanas censales",
    style_function=lambda x: {
        "fillColor": "#9D664A00",
        "color": "red",
        "weight": 0.5
    }
).add_to(m)

    folium.LayerControl().add_to(m)
    st_folium(m, height=500, width=800)

# -------------------------------------------------
# MÉTRICAS CLAVE
# -------------------------------------------------
with col2:
    st.subheader("📌 Indicadores acumulados 2019–2025")
    st.caption("Resumen global del periodo completo analizado (no depende de la selección de años).")

    # --- Totales en hectáreas por tipo de cambio ---
    urb_ha = cambios_zona["urbanizacion_ha"].sum()
    perd_veg_ha = cambios_zona["perdida_veg_ha"].sum()
    gan_veg_ha = cambios_zona["ganancia_veg_ha"].sum()
    agua_ha = cambios_zona["nuevo_agua_ha"].sum()

    # --- Cambio neto de vegetación ---
    cambio_neto_veg = gan_veg_ha - perd_veg_ha

    # --- Área total analizada y % con cambios ---
    area_total_analizada = cambios_zona["total_pixeles"].sum() * 0.01
    area_total_cambiada = urb_ha + perd_veg_ha + gan_veg_ha + agua_ha
    pct_territorio_cambiado = 100 * area_total_cambiada / area_total_analizada

    # --- Proceso dominante ---
    totales = {
        "Urbanización": urb_ha,
        "Pérdida de vegetación": perd_veg_ha,
        "Ganancia de vegetación": gan_veg_ha,
        "Nuevo cuerpo de agua": agua_ha
    }
    proceso_dominante = max(totales, key=totales.get)
    valor_dom = totales[proceso_dominante]

    # --- Promedios porcentuales por zona ---
    promedio_urb_pct = cambios_zona["urbanizacion_pct"].mean()
    promedio_perd_veg_pct = cambios_zona["perdida_veg_pct"].mean()
    promedio_gan_veg_pct = cambios_zona["ganancia_veg_pct"].mean()

    # --- Layout de métricas ---
    with st.container():
        st.metric("Urbanización total (ha)", f"{urb_ha:.2f}")

    with st.container():
        st.metric("Pérdida total de vegetación (ha)", f"{perd_veg_ha:.2f}")

    with st.container():
        st.metric("Ganancia total de vegetación (ha)", f"{gan_veg_ha:.2f}")

    with st.container():
        st.metric("Nuevas superficies de agua (ha)", f"{agua_ha:.2f}")

    with st.container():
        st.metric("Cambio neto de vegetación (ha)", f"{cambio_neto_veg:.2f}")

    with st.container():
        st.metric("% del territorio con cambios", f"{pct_territorio_cambiado:.2f} %")

    with st.container():
        st.metric("Urbanización promedio por zona", f"{promedio_urb_pct:.2f} %")

    st.markdown("---")

    with st.container():
        st.metric("Pérdida de vegetación promedio por zona", f"{promedio_perd_veg_pct:.2f} %")

    with st.container():
        st.metric("Ganancia de vegetación promedio por zona", f"{promedio_gan_veg_pct:.2f} %")

# -------------------------------------------------
# GRÁFICOS DINÁMICOS
# -------------------------------------------------
st.subheader("📈 Evolución de superficies por tipo de cobertura")
st.markdown(
    """
    Este gráfico muestra cómo cambian en el tiempo las hectáreas de cada tipo de cobertura. P.ej:

    - Si la línea **Urbano** sube, significa una expansión de la ciudad.
    - Si las líneas de **Vegetación** bajan, significa una pérdida de áreas verdes.
    """
)


fig_sup = px.line(
    superficies,
    x="Año",
    y=["Urbano_Ha", "Veg_Densa_Ha", "Veg_Media_Ha"],
    markers=True,
    labels={"value": "Hectáreas"},
    title="Evolución temporal de coberturas"
)

st.plotly_chart(fig_sup, use_container_width=True)

# -------------------------------------------------
# EVOLUCIÓN DE ÍNDICES
# -------------------------------------------------
st.subheader(f"📉 Evolución anual del índice {indice_sel}")
st.markdown(
    """
    La línea representa el valor promedio anual del índice en toda la comuna.
    Las barras verticales muestran la variabilidad (desviación estándar).

    Cambios sostenidos en el tiempo indican transformaciones reales del paisaje.
    """
)

df_idx = estadisticas[estadisticas["Índice"] == indice_sel]

fig_idx = px.line(
    df_idx,
    x="Año",
    y="Media",
    error_y="Std",
    markers=True,
    labels={"Media": indice_sel},
    title=f"Evolución anual del {indice_sel}"
)

st.plotly_chart(fig_idx, use_container_width=True)

# -------------------------------------------------
# COMPARADOR VISUAL
# -------------------------------------------------
st.subheader("🖼️ Comparación espacial antes / después")
st.markdown(
    """
    Comparación directa del índice seleccionado entre dos años.

    Permite identificar visualmente dónde aumentó o disminuyó la vegetación,
    la urbanización o el suelo desnudo.
    """
)

col3, col4 = st.columns(2)

with col3:
    st.image(
        f"app/utils/outputs/figures/02_mapa_indices_{anio_inicio}.png",
        caption=f"{indice_sel} – {anio_inicio}"
    )

with col4:
    st.image(
        f"app/utils/outputs/figures/02_mapa_indices_{anio_fin}.png",
        caption=f"{indice_sel} – {anio_fin}"
    )

# -------------------------------------------------
# MATRIZ DE CONFUSIÓN
# -------------------------------------------------
st.subheader("✅ Validación del modelo de clasificación")
st.markdown(
    """
    La matriz de confusión compara la **predicción del Método 2 (Clasificación Urbana)**
    con la referencia de **Google Dynamic World**.

    - **Real: Nueva Urbanización** = píxeles que pasaron de no urbano (2019) a urbano (2025) según Dynamic World.  
    - **Pred: Nueva Urbanización** = píxeles detectados como urbanos por nuestro modelo.  

    Valores altos en la diagonal principal indican buena concordancia entre la predicción
    y el dato de referencia.
    """
)

st.dataframe(matriz_conf)

st.image(
    "app/utils/outputs/figures/03_matriz_confusion.png",
    caption="Matriz de confusión – Validación de urbanización"
)


def mostrar_gif(ruta_gif):
    with open(ruta_gif, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode()
    st.markdown(
        f"""
        <img src="data:image/gif;base64,{encoded}" 
            style="width:100%; max-width:1200px;">
        """,
        unsafe_allow_html=True
    )

st.subheader("⏳ Animación temporal del cambio")
st.markdown(
    """
    Secuencia temporal que muestra la evolución del índice a lo largo de los años.
    Útil para detectar tendencias progresivas y no solo diferencias puntuales.
    """
)
mostrar_gif("app/utils/outputs/figures/animacion_NDVI.gif")


# -------------------------------------------------
# DESCARGA DE RESULTADOS
# -------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("⬇️ Descarga de resultados")
st.sidebar.markdown(
    "Puedes descargar los datos procesados para análisis externo en CSV."
)

csv_zonas = cambios_zona.to_csv(index=False)
st.sidebar.download_button(
    "Descargar cambios por zona",
    csv_zonas,
    "cambios_por_zona.csv",
    "text/csv"
)

csv_sup = superficies.to_csv(index=False)
st.sidebar.download_button(
    "Descargar superficies clasificadas",
    csv_sup,
    "superficies_clasificadas.csv",
    "text/csv"
)
