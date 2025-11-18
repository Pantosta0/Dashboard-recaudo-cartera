import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de Recaudo y Cartera",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configurar navegación multi-página
pages = {
    "": [
        st.Page("pages/1_Recaudo.py", title="Recaudo", icon="💰", default=True),
        st.Page("pages/2_Cartera.py", title="Cartera", icon="📊"),
    ]
}

page = st.navigation(pages)
page.run()
