import streamlit as st
from pathlib import Path
import sys

# Agregar utils al path
utils_path = Path(__file__).parent / "utils"
if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

from data_loader import clear_all_cache_dirs

# Configuración de la página
st.set_page_config(
    page_title="Dashboard Organización Botero",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configurar navegación multi-página
st.sidebar.markdown("---")
if st.sidebar.button("🧹 Limpiar cachés", use_container_width=True):
    removed, errors = clear_all_cache_dirs()
    if removed:
        st.sidebar.success(f"Se eliminaron {len(removed)} elementos de caché.")
    else:
        st.sidebar.info("No se encontraron archivos en las carpetas de caché.")
    if errors:
        st.sidebar.warning(f"No se pudieron borrar {len(errors)} elementos. Revisa la consola/logs.")

pages = {
    "": [
        st.Page("pages/1_Recaudo.py", title="Recaudo", icon="💰", default=True),
        st.Page("pages/2_Cartera.py", title="Cartera", icon="📊"),
        st.Page("pages/3_Pipeline.py", title="Pipeline Fiable", icon="🔄"),
        st.Page("pages/4_Colocacion_Fiable.py", title="Colocación Fiable", icon="📦"),
    ]
}

page = st.navigation(pages)
page.run()
