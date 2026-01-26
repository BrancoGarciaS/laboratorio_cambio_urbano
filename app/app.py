import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# Configuración inicial
st.set_page_config(page_title="Laboratorio Cambio Urbano", layout="wide")

# Menú lateral
st.sidebar.title("Navegación")
page = st.sidebar.radio(
    "Selecciona una sección:",
    [
        "Datos",
        "Índices",
        "Detección de Cambios",
        "Análisis Zonal"
    ]
)

# ================================
# 01 - DESCARGAR DATOS
# ================================
if page == "Datos":
    st.header("⬇️ Visualización de datos")


# ================================
# 02 - CÁLCULO DE ÍNDICES
# ================================
elif page == "Índices":
    st.header("📊 Cálculo de Índices")
    st.write("Visualización de índices NDVI, NDBI u otros calculados.")


# ================================
# 03 - DETECCIÓN DE CAMBIOS
# ================================
elif page == "Detección de Cambios":
    st.header("🔍 Detección de Cambios")
    st.write("Resultados de los métodos de detección: diferencia de índices, clasificación urbana, anomalías temporales.")


# ================================
# 04 - ANÁLISIS ZONAL
# ================================
elif page == "Análisis Zonal":
    st.header("🗺️ Análisis Zonal")
    st.write("Estadísticas zonal.")

