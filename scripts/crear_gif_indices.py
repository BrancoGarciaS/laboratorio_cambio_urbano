from PIL import Image
import os

# -------------------------------
# CONFIGURACIÓN
# -------------------------------
indice = "NDVI"  # NDVI, NDBI, NDWI, BSI
input_dir = "outputs/figures"
output_gif = f"outputs/figures/animacion_{indice}.gif"

anios = [2019, 2020, 2021, 2022, 2023, 2024, 2025]

imagenes = []

for anio in anios:
    ruta = os.path.join(input_dir, f"02_mapa_indices_{anio}.png")
    img = Image.open(ruta).convert("RGB")
    imagenes.append(img)

# Guardar GIF
imagenes[0].save(
    output_gif,
    save_all=True,
    append_images=imagenes[1:],
    duration=800,  # ms por frame
    loop=0
)

print(f"GIF generado: {output_gif}")
