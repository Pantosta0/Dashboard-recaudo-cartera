import streamlit as st
from pathlib import Path
import sys

# Agregar utils al path
utils_path = Path(__file__).parent / "utils"
if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

from data_loader import (
    clear_cache_dirs,
    CARTERA_CACHE_DIR,
    RECAUDO_CACHE_DIR,
    PIPELINE_CACHE_DIR,
    COLOCACION_CACHE_DIR,
    CARTERA_FIABLE_CACHE_DIR,
)

# Configuración de la página
st.set_page_config(
    page_title="Dashboard Organización Botero",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configurar navegación multi-página
APP_DIR = Path(__file__).parent
PAGES_DIR = APP_DIR / "pages"
PAGE_CACHE_MAPPING = {
    (PAGES_DIR / "1_Recaudo.py").resolve(): [RECAUDO_CACHE_DIR],
    (PAGES_DIR / "2_Cartera.py").resolve(): [CARTERA_CACHE_DIR],
    (PAGES_DIR / "3_Pipeline.py").resolve(): [PIPELINE_CACHE_DIR],
    (PAGES_DIR / "4_Colocacion_Fiable.py").resolve(): [COLOCACION_CACHE_DIR],
    (PAGES_DIR / "5_Informe_Cartera_Fiable.py").resolve(): [CARTERA_FIABLE_CACHE_DIR],
}


def _get_current_page_cache_dirs(page_obj):
    page_source = getattr(page_obj, "_page", None)
    if page_source is None:
        return None, None
    if isinstance(page_source, str):
        page_source = Path(page_source)
    if not isinstance(page_source, Path):
        return None, None
    resolved_path = page_source.resolve()
    return resolved_path, PAGE_CACHE_MAPPING.get(resolved_path)

pages = {
    "": [
        st.Page("pages/1_Recaudo.py", title="Recaudo", icon="💰", default=True),
        st.Page("pages/2_Cartera.py", title="Cartera", icon="📊"),
        st.Page("pages/3_Pipeline.py", title="Pipeline Fiable", icon="🔄"),
        st.Page("pages/4_Colocacion_Fiable.py", title="Colocación Fiable", icon="📦"),
        st.Page("pages/5_Informe_Cartera_Fiable.py", title="Informe Cartera FIABLE", icon="📋"),
    ]
}

page = st.navigation(pages)

st.sidebar.markdown("---")
current_page_title = getattr(page, "title", "esta página")
if st.sidebar.button("🧹 Limpiar caché de esta página", width="stretch"):
    page_path, cache_dirs = _get_current_page_cache_dirs(page)
    if cache_dirs:
        removed, errors = clear_cache_dirs(cache_dirs)
        if removed:
            st.sidebar.success(
                f"Se eliminaron {len(removed)} elementos de la caché de {current_page_title}."
            )
        else:
            st.sidebar.info("No se encontraron archivos para eliminar en la caché de esta página.")
        if errors:
            st.sidebar.warning(
                f"No se pudieron borrar {len(errors)} elementos. Revisa la consola/logs."
            )
    elif page_path is None:
        st.sidebar.warning("No se pudo determinar la página actual para limpiar su caché.")
    else:
        st.sidebar.info("Esta página no tiene cachés configurados para limpiar.")

page.run()
