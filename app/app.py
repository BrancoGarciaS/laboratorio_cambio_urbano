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
    """
)

# -------------------------------------------------
# SIDEBAR – CONTROLES
# -------------------------------------------------
st.sidebar.header("⚙️ Configuración")

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
    cambios_zona = pd.read_csv("outputs/reports/04_cambios_por_zona.csv")
    superficies = pd.read_csv("outputs/reports/02_superficies_clasificadas.csv")
    estadisticas = pd.read_csv("outputs/reports/02_estadisticas_anuales.csv")
    matriz_conf = pd.read_csv("outputs/reports/03_matriz_confusion.csv")
    limite = gpd.read_file("data/vector/limite_comuna.gpkg")
    red_vial = gpd.read_file("data/vector/red_vial.geojson")
    return cambios_zona, superficies, estadisticas, matriz_conf, limite, red_vial

cambios_zona, superficies, estadisticas, matriz_conf, limite, red_vial = cargar_datos()

# -------------------------------------------------
# LAYOUT PRINCIPAL
# -------------------------------------------------
col1, col2 = st.columns([2, 1])

# -------------------------------------------------
# MAPA INTERACTIVO
# -------------------------------------------------
with col1:
    st.subheader("🗺️ Mapa de Cambio Urbano")

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

    folium.LayerControl().add_to(m)
    st_folium(m, height=500, width=800)

# -------------------------------------------------
# MÉTRICAS CLAVE
# -------------------------------------------------
with col2:
    st.subheader("📌 Indicadores Clave")

    st.metric(
        "Urbanización total (ha)",
        f"{cambios_zona['urbanizacion_ha'].sum():.2f}"
    )

    st.metric(
        "Pérdida de vegetación (ha)",
        f"{cambios_zona['perdida_veg_ha'].sum():.2f}"
    )

    st.metric(
        "Ganancia de vegetación (ha)",
        f"{cambios_zona['ganancia_veg_ha'].sum():.2f}"
    )

# -------------------------------------------------
# GRÁFICOS DINÁMICOS
# -------------------------------------------------
st.subheader("📈 Evolución de Superficies Clasificadas")

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
st.subheader(f"📉 Evolución del índice {indice_sel}")

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
st.subheader("🖼️ Comparación visual antes / después")

col3, col4 = st.columns(2)

with col3:
    st.image(
        f"outputs/figures/02_mapa_indices_{anio_inicio}.png",
        caption=f"{indice_sel} – {anio_inicio}"
    )

with col4:
    st.image(
        f"outputs/figures/02_mapa_indices_{anio_fin}.png",
        caption=f"{indice_sel} – {anio_fin}"
    )

# -------------------------------------------------
# MATRIZ DE CONFUSIÓN
# -------------------------------------------------
st.subheader("✅ Validación del modelo")

st.dataframe(matriz_conf)

st.image(
    "outputs/figures/03_matriz_confusion.png",
    caption="Matriz de confusión – Cambio urbano"
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
mostrar_gif("outputs/figures/animacion_NDVI.gif")


# -------------------------------------------------
# DESCARGA DE RESULTADOS
# -------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("⬇️ Descarga de resultados")

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
