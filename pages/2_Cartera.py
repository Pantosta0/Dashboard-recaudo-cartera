import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import sys
from pathlib import Path

# Agregar el directorio utils al path
utils_path = Path(__file__).parent.parent / "utils"
if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

from data_loader import (
    load_excel_with_cache, 
    detect_cartera_files, 
    process_cartera_data,
    CARTERA_CACHE_DIR,
    CARTERA_RAW_DIR,
    load_cartera_for_comparison,
    compare_cartera_periods
)

# Título principal
st.title("📊 Informe de Cartera")
st.markdown("---")

# Estilos responsivos para las tarjetas de empresa
st.markdown(
    """
    <style>
        .company-card {
            background-color: #111827;
            border-radius: 16px;
            border: 1px solid #1f2937;
            padding: 1.25rem;
            margin-bottom: 1.5rem;
            min-height: 420px;
            height: 100%;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        .company-title {
            font-size: clamp(1rem, 1.5vw, 1.6rem);
            margin: 0;
            font-weight: 600;
        }
        .company-subtitle {
            font-size: clamp(0.85rem, 1.2vw, 1rem);
            color: #d1d5db;
        }
        .company-value {
            font-size: clamp(1.2rem, 2vw, 2.1rem);
            font-weight: 700;
            color: #f9fafb;
        }
        .indice-grid {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }
        .indice-card {
            border-radius: 12px;
            padding: 0.55rem;
            font-weight: 600;
            font-size: clamp(0.85rem, 1.2vw, 1rem);
            text-align: center;
            color: white;
        }
        .breakdown-title {
            font-weight: 600;
            font-size: clamp(0.9rem, 1.2vw, 1.05rem);
            margin-top: 0.5rem;
        }
        .breakdown-list {
            list-style: none;
            padding: 0;
            margin: 0;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
            font-size: clamp(0.8rem, 1.1vw, 0.95rem);
        }
        .breakdown-list li {
            display: flex;
            justify-content: space-between;
            gap: 0.5rem;
        }
        .breakdown-list span {
            color: #d1d5db;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Función para clasificar empresas por cuenta
def clasificar_empresa(cuenta):
    """Clasifica la empresa basándose en el número de cuenta"""
    if pd.isna(cuenta):
        return "Sin Clasificar"
    
    try:
        # Intentar convertir a entero primero (si es float)
        if isinstance(cuenta, float):
            cuenta_str = str(int(cuenta))
        else:
            cuenta_str = str(cuenta).strip()
        
        # Eliminar puntos, espacios u otros caracteres
        cuenta_str = cuenta_str.replace('.', '').replace(' ', '').replace(',', '')
        
        # Soluciones Integrales: 137010001-137010006 y 137010999
        if cuenta_str in ["137010001", "137010002", "137010003", "137010004", "137010005", "137010006", "137010999"]:
            return "Soluciones Integrales"
        
        # Grupo Estrategico: 130505010
        if cuenta_str == "130505010":
            return "Grupo Estrategico"
        
        # Finaliados: 130505011
        if cuenta_str == "130505011":
            return "Finaliados"
        
        # AGM: 130505012
        if cuenta_str == "130505012":
            return "AGM"
        
        # Motofacil: 130505013
        if cuenta_str == "130505013":
            return "Motofacil"
        
        # Motored: 130505014
        if cuenta_str == "130505014":
            return "Motored"
        
        # Cartera Castigada: 139905000-139905005
        try:
            cuenta_num = int(cuenta_str)
            if 139905000 <= cuenta_num <= 139905005:
                return "Cartera Castigada"
        except:
            pass
        
    except Exception:
        pass
    
    return "Otras"

# Función auxiliar para limpiar y convertir valores numéricos
def limpiar_numerico(serie):
    """Limpia y convierte una serie a numérico"""
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors='coerce').fillna(0)
    else:
        serie_limpia = serie.astype(str).str.replace(',', '', regex=False).str.replace('$', '', regex=False).str.replace(' ', '', regex=False).str.strip()
        return pd.to_numeric(serie_limpia, errors='coerce').fillna(0)


COLOR_INDICES = {
    "Corriente": "#2ecc71",
    "Tipo B": "#f1c40f",
    "Tipo C": "#e67e22",
    "Tipo D": "#e74c3c",
    "Tipo E": "#c0392b",
}


def get_color_indice(indice_tipo):
    return COLOR_INDICES.get(indice_tipo, "#95a5a6")


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def format_currency(value):
    try:
        return f"${value:,.0f}"
    except (TypeError, ValueError):
        return "$0"


def generar_pdf(resumen_data, mes):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Encabezado
    pdf.set_fill_color(17, 24, 39)
    pdf.rect(0, 0, 210, 35, "F")
    pdf.set_xy(10, 10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Informe de Cartera", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Mes: {mes}", ln=True)
    pdf.ln(8)
    pdf.set_text_color(0, 0, 0)

    for empresa in resumen_data:
        # Tarjeta principal
        pdf.set_fill_color(31, 41, 55)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, f"{empresa['Empresa']}", ln=True, fill=True)

        # Valores generales
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 11)
        pdf.ln(1)
        generales = [
            ("Cartera Total", format_currency(empresa["Cartera Total"])),
            ("Por Vencer", format_currency(empresa["Por Vencer"])),
            ("Días 30", format_currency(empresa["Días 30"])),
            ("Días 60", format_currency(empresa["Días 60"])),
            ("Días 90", format_currency(empresa["Días 90"])),
            ("Días +90", format_currency(empresa["Días +90"])),
        ]
        for label, value in generales:
            pdf.cell(0, 6, f"{label}: {value}", ln=True)

        # Índices con colores
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 10)
        indices = [
            ("Índice Corriente", "Índice Corriente (%)", "Corriente"),
            ("Índice Tipo B", "Índice Tipo B (%)", "Tipo B"),
            ("Índice Tipo C", "Índice Tipo C (%)", "Tipo C"),
            ("Índice Tipo D", "Índice Tipo D (%)", "Tipo D"),
            ("Índice Tipo E", "Índice Tipo E (%)", "Tipo E"),
        ]
        for label, key, color_key in indices:
            rgb = hex_to_rgb(COLOR_INDICES[color_key])
            pdf.set_fill_color(*rgb)
            pdf.set_text_color(255, 255, 255)
            valor = f"{empresa[key]}%"
            pdf.cell(0, 6, f"{label}: {valor}", ln=True, fill=True)

        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)
        pdf.set_draw_color(229, 231, 235)
        pdf.set_line_width(0.3)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

    return pdf.output(dest="S").encode("latin-1")

# Cargar datos
@st.cache_data
def load_cartera_data(año=None, mes_num=None):
    """
    Carga datos de cartera para un mes específico.
    Si no se especifica mes, carga el más reciente disponible.
    Nota: Los parámetros año y mes_num se usan como clave de caché.
    """
    # Detectar archivos disponibles
    available_files = detect_cartera_files()
    
    if not available_files:
        st.error("No se encontraron archivos de cartera. Por favor, coloca archivos con formato 'cartera-YYYY-MM.xlsx' en data/cartera/raw/ o en el directorio raíz.")
        return None
    
    # Si se especifica mes, buscar ese archivo
    if año and mes_num:
        selected_file = None
        for mes_str, año_file, mes_file, file_path in available_files:
            if año_file == año and mes_file == mes_num:
                selected_file = file_path
                break
        
        if selected_file is None:
            st.warning(f"No se encontró archivo para {año}-{mes_num:02d}. Usando el más reciente disponible.")
            selected_file = available_files[0][3]
    else:
        # Usar el archivo más reciente
        selected_file = available_files[0][3]
    
    # Cargar con caché (sin deduplicación para mantener totales como antes)
    df = load_excel_with_cache(
        selected_file,
        CARTERA_CACHE_DIR,
        processing_func=lambda df: process_cartera_data(df, deduplicate=False),
        header=7
    )
    
    # Agregar columna de empresa si no existe
    if df is not None and 'Cuenta' in df.columns and 'Empresa' not in df.columns:
        df['Empresa'] = df['Cuenta'].apply(clasificar_empresa)
    
    return df

# Detectar archivos disponibles primero
available_files = detect_cartera_files()

# Información de depuración (solo en modo desarrollo)
if len(available_files) == 0:
    st.warning(f"⚠️ **No se encontraron archivos de cartera.**")
    st.info(f"📁 **Buscando en:** `{CARTERA_RAW_DIR}` y directorio raíz")
    st.info(f"📋 **Patrón esperado:** `cartera-YYYY-MM.xlsx` (ej: `cartera-2024-10.xlsx`)")
    
    # Mostrar archivos que existen en el directorio
    if CARTERA_RAW_DIR.exists():
        all_files = list(CARTERA_RAW_DIR.glob("*.xlsx"))
        if all_files:
            st.write("**Archivos encontrados en el directorio (que no coinciden con el patrón):**")
            for f in all_files:
                st.write(f"- {f.name}")
        else:
            st.write("**No hay archivos .xlsx en el directorio.**")
    else:
        st.write(f"**El directorio `{CARTERA_RAW_DIR}` no existe.**")

if available_files:
    # Inicializar session state para el mes seleccionado
    if 'cartera_selected_month' not in st.session_state:
        st.session_state.cartera_selected_month = available_files[0][0]
        st.session_state.cartera_selected_year = available_files[0][1]
        st.session_state.cartera_selected_month_num = available_files[0][2]
    
    # Crear lista de opciones para el selector
    meses_opciones = [f"{mes_str}" for mes_str, _, _, _ in available_files]
    
    st.sidebar.header("🔍 Filtros")
    
    # Seleccionar mes
    if len(meses_opciones) > 1:
        current_index = 0
        if st.session_state.cartera_selected_month in meses_opciones:
            current_index = meses_opciones.index(st.session_state.cartera_selected_month)
        
        mes_selected = st.sidebar.selectbox(
            "Seleccionar Mes", 
            meses_opciones,
            index=current_index,
            key="selectbox_mes_cartera"
        )
        
        # Obtener año y mes del archivo seleccionado
        año_selected = None
        mes_num_selected = None
        for mes_str, año, mes_num, _ in available_files:
            if mes_str == mes_selected:
                año_selected = año
                mes_num_selected = mes_num
                break
        
        # Verificar si cambió el mes y recargar si es necesario
        if (st.session_state.cartera_selected_month != mes_selected or 
            st.session_state.cartera_selected_year != año_selected):
            # Actualizar session state
            st.session_state.cartera_selected_month = mes_selected
            st.session_state.cartera_selected_year = año_selected
            st.session_state.cartera_selected_month_num = mes_num_selected
            # Limpiar caché de la función para forzar recarga
            load_cartera_data.clear()
            # Recargar página para aplicar cambios
            st.rerun()
        
        # Cargar datos (el caché se invalida automáticamente con año y mes_num)
        df = load_cartera_data(año_selected, mes_num_selected)
    else:
        mes_selected = meses_opciones[0]
        año_selected = available_files[0][1]
        mes_num_selected = available_files[0][2]
        st.session_state.cartera_selected_month = mes_selected
        st.session_state.cartera_selected_year = año_selected
        st.session_state.cartera_selected_month_num = mes_num_selected
        df = load_cartera_data(año_selected, mes_num_selected)
else:
    st.sidebar.header("🔍 Filtros")
    df = load_cartera_data()
    mes_selected = "Sin datos disponibles"

if df is not None and not df.empty:
    # Mostrar información del archivo cargado para depuración
    file_info = None
    for mes_str, año, mes_num, file_path in available_files:
        if mes_str == mes_selected:
            file_info = file_path
            break
    
    st.info(f"📅 **Mes seleccionado: {mes_selected}** (Archivo: {file_info.name if file_info else 'N/A'})")
    st.markdown("---")
    
    # Filtrar datos (por ahora todos, pero preparado para filtrado por mes)
    df_filtered = df.copy()
    
    # Eliminar completamente los registros de "Sin Clasificar"
    if 'Empresa' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Empresa'] != 'Sin Clasificar'].copy()
    
    # Calcular métricas por empresa en el orden solicitado
    empresas = df_filtered['Empresa'].unique() if 'Empresa' in df_filtered.columns else []
    orden_preferido = [
        "Soluciones Integrales",
        "Finaliados",
        "Grupo Estrategico",
        "AGM",
        "Motofacil",
        "Motored",
        "Cartera Castigada",
        "Otras",
    ]
    empresas_presentes = [e for e in orden_preferido if e in empresas]
    otras_empresas = sorted([e for e in empresas if e not in orden_preferido])
    empresas_ordenadas = [e for e in empresas_presentes + otras_empresas if e]
    
    if len(empresas_ordenadas) == 0:
        st.warning("No se encontraron empresas clasificadas en los datos.")
    else:
        def obtener_metricas(df_empresa):
            total_cuota = df_empresa['Total Cuota'].sum() if 'Total Cuota' in df_empresa.columns else 0
            por_vencer = df_empresa['Por Vencer'].sum() if 'Por Vencer' in df_empresa.columns else 0
            dias30 = df_empresa['Dias30'].sum() if 'Dias30' in df_empresa.columns else 0
            dias60 = df_empresa['Dias60'].sum() if 'Dias60' in df_empresa.columns else 0
            dias90 = df_empresa['Dias90'].sum() if 'Dias90' in df_empresa.columns else 0
            dias_mas90 = df_empresa['Dias Mas90'].sum() if 'Dias Mas90' in df_empresa.columns else 0
            
            if total_cuota > 0:
                indice_corriente = (por_vencer / total_cuota) * 100
                indice_b = (dias30 / total_cuota) * 100
                indice_c = (dias60 / total_cuota) * 100
                indice_d = (dias90 / total_cuota) * 100
                indice_e = (dias_mas90 / total_cuota) * 100
            else:
                indice_corriente = indice_b = indice_c = indice_d = indice_e = 0
            
            return {
                "total": total_cuota,
                "por_vencer": por_vencer,
                "dias30": dias30,
                "dias60": dias60,
                "dias90": dias90,
                "dias_mas90": dias_mas90,
                "indices": [
                    ("Índice Corriente", indice_corriente, "Corriente"),
                    ("Índice Tipo B", indice_b, "Tipo B"),
                    ("Índice Tipo C", indice_c, "Tipo C"),
                    ("Índice Tipo D", indice_d, "Tipo D"),
                    ("Índice Tipo E", indice_e, "Tipo E"),
                ],
            }
        
        cards_per_row = 3 if len(empresas_ordenadas) >= 3 else len(empresas_ordenadas)
        cards_per_row = max(cards_per_row, 1)
        
        for start in range(0, len(empresas_ordenadas), cards_per_row):
            subset = empresas_ordenadas[start:start + cards_per_row]
            row_cols = st.columns(len(subset))
            
            for empresa, col in zip(subset, row_cols):
                with col:
                    df_empresa = df_filtered[df_filtered['Empresa'] == empresa].copy()
                    
                    if df_empresa.empty:
                        st.info("Sin datos")
                        continue
                    
                    metricas = obtener_metricas(df_empresa)
                    indice_cards_html = "".join(
                        [
                            f'<div class="indice-card" style="background-color: {get_color_indice(tipo)};">{label}: {valor:.2f}%</div>'
                            for label, valor, tipo in metricas["indices"]
                        ]
                    )
                    breakdown_data = [
                        ("Por Vencer", metricas["por_vencer"]),
                        ("Días 30", metricas["dias30"]),
                        ("Días 60", metricas["dias60"]),
                        ("Días 90", metricas["dias90"]),
                        ("Días +90", metricas["dias_mas90"]),
                    ]
                    breakdown_html = "".join(
                        [
                            f'<li><span>{label}</span><strong>{format_currency(valor)}</strong></li>'
                            for label, valor in breakdown_data
                        ]
                    )
                    
                    card_html = f"""
                        <div class="company-card">
                            <div>
                                <p class="company-title">🏢 {empresa}</p>
                                <p class="company-subtitle">Cartera Total Actual</p>
                                <p class="company-value">{format_currency(metricas["total"])}</p>
                            </div>
                            <div class="indice-grid">
                                {indice_cards_html}
                            </div>
                            <div>
                                <p class="breakdown-title">Desglose</p>
                                <ul class="breakdown-list">
                                    {breakdown_html}
                                </ul>
                            </div>
                        </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Resumen general en tabla
        st.subheader("📋 Resumen General por Empresa")
        
        resumen_data = []
        for empresa in empresas_ordenadas:
            df_empresa = df_filtered[df_filtered['Empresa'] == empresa].copy()
            
            if len(df_empresa) == 0:
                continue
            
            total_cuota = df_empresa['Total Cuota'].sum() if 'Total Cuota' in df_empresa.columns else 0
            por_vencer = df_empresa['Por Vencer'].sum() if 'Por Vencer' in df_empresa.columns else 0
            dias30 = df_empresa['Dias30'].sum() if 'Dias30' in df_empresa.columns else 0
            dias60 = df_empresa['Dias60'].sum() if 'Dias60' in df_empresa.columns else 0
            dias90 = df_empresa['Dias90'].sum() if 'Dias90' in df_empresa.columns else 0
            dias_mas90 = df_empresa['Dias Mas90'].sum() if 'Dias Mas90' in df_empresa.columns else 0
            
            if total_cuota > 0:
                indice_corriente = (por_vencer / total_cuota) * 100
                indice_b = (dias30 / total_cuota) * 100
                indice_c = (dias60 / total_cuota) * 100
                indice_d = (dias90 / total_cuota) * 100
                indice_e = (dias_mas90 / total_cuota) * 100
            else:
                indice_corriente = indice_b = indice_c = indice_d = indice_e = 0
            
            resumen_data.append({
                'Empresa': empresa,
                'Cartera Total': total_cuota,
                'Índice Corriente (%)': f"{indice_corriente:.2f}",
                'Índice Tipo B (%)': f"{indice_b:.2f}",
                'Índice Tipo C (%)': f"{indice_c:.2f}",
                'Índice Tipo D (%)': f"{indice_d:.2f}",
                'Índice Tipo E (%)': f"{indice_e:.2f}",
                'Por Vencer': por_vencer,
                'Días 30': dias30,
                'Días 60': dias60,
                'Días 90': dias90,
                'Días +90': dias_mas90
            })
        
        if resumen_data:
            df_resumen = pd.DataFrame(resumen_data)
            
            # Crear una copia para mostrar con valores formateados
            df_resumen_display = df_resumen.copy()
            
            # Formatear columnas monetarias para visualización
            columnas_monetarias = ['Cartera Total', 'Por Vencer', 'Días 30', 'Días 60', 'Días 90', 'Días +90']
            for col in columnas_monetarias:
                if col in df_resumen_display.columns:
                    df_resumen_display[col] = df_resumen_display[col].apply(format_currency)
            
            st.dataframe(df_resumen_display, use_container_width=True)
            
            # Botón de descarga (usar el DataFrame original con valores numéricos)
            csv = df_resumen.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 Descargar resumen como CSV",
                data=csv,
                file_name=f"resumen_cartera_{mes_selected.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

            pdf_bytes = generar_pdf(resumen_data, mes_selected)
            st.download_button(
                label="📄 Descargar informe en PDF",
                data=pdf_bytes,
                file_name=f"informe_cartera_{mes_selected.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )
        
        # Gráfico comparativo
        st.markdown("---")
        st.subheader("📊 Comparación de Índices por Empresa")
        
        if resumen_data:
            # Preparar datos para gráfico
            empresas_graf = [r['Empresa'] for r in resumen_data]
            indices_corriente = [float(r['Índice Corriente (%)']) for r in resumen_data]
            indices_b = [float(r['Índice Tipo B (%)']) for r in resumen_data]
            indices_c = [float(r['Índice Tipo C (%)']) for r in resumen_data]
            indices_d = [float(r['Índice Tipo D (%)']) for r in resumen_data]
            indices_e = [float(r['Índice Tipo E (%)']) for r in resumen_data]
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                name='Corriente',
                x=empresas_graf,
                y=indices_corriente,
                marker_color='#2ecc71',
                text=[f"{valor:.2f}%" for valor in indices_corriente],
                textposition='inside'
            ))
            fig.add_trace(go.Bar(
                name='Tipo B',
                x=empresas_graf,
                y=indices_b,
                marker_color='#f1c40f',
                text=[f"{valor:.2f}%" for valor in indices_b],
                textposition='inside'
            ))
            fig.add_trace(go.Bar(
                name='Tipo C',
                x=empresas_graf,
                y=indices_c,
                marker_color='#e67e22',
                text=[f"{valor:.2f}%" for valor in indices_c],
                textposition='inside'
            ))
            fig.add_trace(go.Bar(
                name='Tipo D',
                x=empresas_graf,
                y=indices_d,
                marker_color='#e74c3c',
                text=[f"{valor:.2f}%" for valor in indices_d],
                textposition='inside'
            ))
            fig.add_trace(go.Bar(
                name='Tipo E',
                x=empresas_graf,
                y=indices_e,
                marker_color='#c0392b',
                text=[f"{valor:.2f}%" for valor in indices_e],
                textposition='inside'
            ))
            
            fig.update_layout(
                barmode='group',
                title="Distribución de Índices por Empresa (%)",
                xaxis_title="Empresa",
                yaxis_title="Porcentaje (%)",
                xaxis_tickangle=-45,
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Sección de Comparación Temporal
        st.markdown("---")
        st.subheader("📊 Comparación Temporal de Cartera")
        
        # Mostrar información de depuración
        if len(available_files) < 2:
            st.warning(f"⚠️ **Se necesitan al menos 2 archivos de cartera para realizar comparaciones temporales.**")
            st.info(f"📁 **Archivos detectados: {len(available_files)}**")
            if len(available_files) > 0:
                st.write("**Archivos encontrados:**")
                for mes_str, año, mes_num, file_path in available_files:
                    st.write(f"- {mes_str} ({file_path.name})")
            st.info(f"📋 **Patrón esperado:** `cartera-YYYY-MM.xlsx` o `cartera-YYYY-M.xlsx` (ej: `cartera-2024-10.xlsx` o `cartera-2024-9.xlsx`)")
        
        if len(available_files) > 1:
            st.markdown("Compara la cartera entre dos períodos diferentes (mes vs mes, año vs año, etc.)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Período 1 (Base)**")
                periodo1_opciones = [f"{mes_str}" for mes_str, _, _, _ in available_files]
                periodo1_selected = st.selectbox("Seleccionar Período 1", periodo1_opciones, index=0, key="periodo1")
                
                # Obtener año y mes del período 1
                año1 = None
                mes1 = None
                for mes_str, año, mes_num, _ in available_files:
                    if mes_str == periodo1_selected:
                        año1 = año
                        mes1 = mes_num
                        break
            
            with col2:
                st.markdown("**Período 2 (Comparación)**")
                periodo2_opciones = [f"{mes_str}" for mes_str, _, _, _ in available_files]
                periodo2_selected = st.selectbox("Seleccionar Período 2", periodo2_opciones, index=min(1, len(periodo2_opciones)-1), key="periodo2")
                
                # Obtener año y mes del período 2
                año2 = None
                mes2 = None
                for mes_str, año, mes_num, _ in available_files:
                    if mes_str == periodo2_selected:
                        año2 = año
                        mes2 = mes_num
                        break
            
            if año1 and mes1 and año2 and mes2:
                # Normalizar orden para comparar siempre periodo más antiguo vs más reciente
                periodos_seleccionados = [
                    {
                        "año": año1,
                        "mes": mes1,
                        "label": periodo1_selected,
                        "key": "p1",
                    },
                    {
                        "año": año2,
                        "mes": mes2,
                        "label": periodo2_selected,
                        "key": "p2",
                    },
                ]
                periodos_ordenados = sorted(periodos_seleccionados, key=lambda p: (p["año"], p["mes"]))
                periodo_base = periodos_ordenados[0]
                periodo_comp = periodos_ordenados[1]
                comparison_key = f"comparison_{periodos_ordenados[0]['año']}_{periodos_ordenados[0]['mes']}_{periodos_ordenados[1]['año']}_{periodos_ordenados[1]['mes']}"
                
                if st.button("🔄 Comparar Períodos", type="primary", key="btn_compare"):
                    with st.spinner("Cargando y comparando períodos..."):
                        df1, df2, periodo1_str, periodo2_str = load_cartera_for_comparison(
                            periodo_base["año"], periodo_base["mes"], periodo_comp["año"], periodo_comp["mes"]
                        )
                        if df1 is not None and df2 is not None:
                            comparison_df = compare_cartera_periods(
                                df1,
                                df2,
                                periodo1_str,
                                periodo2_str,
                                clasificar_empresa_func=clasificar_empresa
                            )
                            if comparison_df is not None and not comparison_df.empty:
                                st.session_state[comparison_key] = {
                                    'df': comparison_df,
                                    'periodo1': periodo1_str,
                                    'periodo2': periodo2_str
                                }
                
                # Mostrar comparación si existe en session state
                if comparison_key in st.session_state:
                    comparison_data = st.session_state[comparison_key]
                    comparison_df = comparison_data['df']
                    periodo1_str = comparison_data['periodo1']
                    periodo2_str = comparison_data['periodo2']
                    
                    if comparison_df is not None and not comparison_df.empty:
                        st.markdown(f"### 📈 Comparación: {periodo1_str} vs {periodo2_str}")
                        
                        # Mostrar tabla comparativa sin columnas de variación
                        cols_to_hide = {'Variación Total', 'Variación %'}
                        table_columns = [col for col in comparison_df.columns if col not in cols_to_hide]
                        st.dataframe(
                            comparison_df[table_columns],
                            use_container_width=True,
                            height=400
                        )

                        # Comparación detallada por cartera
                        st.subheader("📂 Comparación detallada por cartera")
                        
                        def format_delta(value):
                            if pd.isna(value) or value == 0:
                                return None
                            sign = "+" if value > 0 else "-"
                            formatted = format_currency(abs(value))
                            return f"{sign}{formatted}"
                        
                        def format_delta_pct(value):
                            if pd.isna(value) or value == 0:
                                return None
                            return f"{value:+.2f} pp"
                        
                        metric_fields = [
                            ("Cartera Total", f"Total {periodo1_str}", f"Total {periodo2_str}"),
                            ("Por Vencer", f"Por Vencer {periodo1_str}", f"Por Vencer {periodo2_str}"),
                            ("Días 30", f"Días 30 {periodo1_str}", f"Días 30 {periodo2_str}"),
                            ("Días 60", f"Días 60 {periodo1_str}", f"Días 60 {periodo2_str}"),
                            ("Días 90", f"Días 90 {periodo1_str}", f"Días 90 {periodo2_str}"),
                            ("Días +90", f"Días +90 {periodo1_str}", f"Días +90 {periodo2_str}"),
                        ]
                        morosity_labels = {"Días 30", "Días 60", "Días 90", "Días +90"}
                        
                        indice_corriente_fields = [
                            ("Índice Corriente", f"Índice Corriente {periodo1_str} (%)", f"Índice Corriente {periodo2_str} (%)"),
                        ]
                        indice_mora_fields = [
                            ("Índice Mora", f"Índice Mora {periodo1_str} (%)", f"Índice Mora {periodo2_str} (%)"),
                            ("Índice Tipo B", f"Índice Tipo B {periodo1_str} (%)", f"Índice Tipo B {periodo2_str} (%)"),
                            ("Índice Tipo C", f"Índice Tipo C {periodo1_str} (%)", f"Índice Tipo C {periodo2_str} (%)"),
                            ("Índice Tipo D", f"Índice Tipo D {periodo1_str} (%)", f"Índice Tipo D {periodo2_str} (%)"),
                            ("Índice Tipo E", f"Índice Tipo E {periodo1_str} (%)", f"Índice Tipo E {periodo2_str} (%)"),
                        ]
                        
                        for _, row in comparison_df.iterrows():
                            empresa = row['Empresa']
                            with st.expander(f"📁 {empresa}", expanded=False):
                                col_p1, col_p2 = st.columns(2)
                                
                                with col_p1:
                                    st.markdown(f"**{periodo1_str}**")
                                    for label, col1, _ in metric_fields:
                                        valor = row.get(col1, 0) or 0
                                        st.metric(label, format_currency(valor))
                                
                                with col_p2:
                                    st.markdown(f"**{periodo2_str}**")
                                    for label, col1, col2 in metric_fields:
                                        valor1 = row.get(col1, 0) or 0
                                        valor2 = row.get(col2, 0) or 0
                                        delta = valor2 - valor1
                                        st.metric(
                                            label,
                                            format_currency(valor2),
                                            delta=format_delta(delta),
                                            delta_color="inverse" if label in morosity_labels else "normal",
                                        )
                                
                                st.markdown("**Índices (%)**")
                                col_idx1, col_idx2 = st.columns(2)
                                with col_idx1:
                                    for label, col1, _ in indice_corriente_fields:
                                        valor = row.get(col1, 0) or 0
                                        st.metric(f"{label} {periodo1_str}", f"{valor:.2f}%")
                                with col_idx2:
                                    for label, col1, col2 in indice_corriente_fields:
                                        valor1 = row.get(col1, 0) or 0
                                        valor2 = row.get(col2, 0) or 0
                                        delta = valor2 - valor1
                                        st.metric(
                                            f"{label} {periodo2_str}",
                                            f"{valor2:.2f}%",
                                            delta=format_delta_pct(delta)
                                        )

                                st.markdown("**Índices de mora por tipo (%)**")
                                col_mora1, col_mora2 = st.columns(2)
                                with col_mora1:
                                    for label, col1, _ in indice_mora_fields:
                                        valor = row.get(col1, 0) or 0
                                        st.metric(f"{label} {periodo1_str}", f"{valor:.2f}%")
                                with col_mora2:
                                    for label, col1, col2 in indice_mora_fields:
                                        valor1 = row.get(col1, 0) or 0
                                        valor2 = row.get(col2, 0) or 0
                                        delta = valor2 - valor1
                                        st.metric(
                                            f"{label} {periodo2_str}",
                                            f"{valor2:.2f}%",
                                            delta=format_delta_pct(delta),
                                            delta_color="inverse"
                                        )
                        
                        # Gráfico de variación
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            fig_var = go.Figure()
                            fig_var.add_trace(go.Bar(
                                name=f'Total {periodo1_str}',
                                x=comparison_df['Empresa'],
                                y=comparison_df[f'Total {periodo1_str}'],
                                marker_color='#3498db'
                            ))
                            fig_var.add_trace(go.Bar(
                                name=f'Total {periodo2_str}',
                                x=comparison_df['Empresa'],
                                y=comparison_df[f'Total {periodo2_str}'],
                                marker_color='#2ecc71'
                            ))
                            fig_var.update_layout(
                                title=f"Comparación de Cartera Total: {periodo1_str} vs {periodo2_str}",
                                xaxis_title="Empresa",
                                yaxis_title="Cartera Total",
                                barmode='group',
                                xaxis_tickangle=-45,
                                height=500
                            )
                            st.plotly_chart(fig_var, use_container_width=True)
                        
                        with col2:
                            # Gráfico de variación porcentual
                            fig_var_pct = go.Figure()
                            colors = ['#e74c3c' if x < 0 else '#2ecc71' for x in comparison_df['Variación %']]
                            fig_var_pct.add_trace(go.Bar(
                                x=comparison_df['Empresa'],
                                y=comparison_df['Variación %'],
                                marker_color=colors,
                                text=[f"{x:.2f}%" for x in comparison_df['Variación %']],
                                textposition='outside'
                            ))
                            fig_var_pct.update_layout(
                                title=f"Variación Porcentual: {periodo1_str} vs {periodo2_str}",
                                xaxis_title="Empresa",
                                yaxis_title="Variación (%)",
                                xaxis_tickangle=-45,
                                height=500
                            )
                            fig_var_pct.add_hline(y=0, line_dash="dash", line_color="gray")
                            st.plotly_chart(fig_var_pct, use_container_width=True)
                        
                        # Gráfico de índices comparativos
                        st.markdown("### 📊 Comparación de Índices")
                        fig_indices_comp = go.Figure()
                        fig_indices_comp.add_trace(go.Bar(
                            name=f'Índice Corriente {periodo1_str}',
                            x=comparison_df['Empresa'],
                            y=comparison_df[f'Índice Corriente {periodo1_str} (%)'],
                            marker_color='#3498db'
                        ))
                        fig_indices_comp.add_trace(go.Bar(
                            name=f'Índice Corriente {periodo2_str}',
                            x=comparison_df['Empresa'],
                            y=comparison_df[f'Índice Corriente {periodo2_str} (%)'],
                            marker_color='#2ecc71'
                        ))
                        fig_indices_comp.add_trace(go.Bar(
                            name=f'Índice Mora {periodo1_str}',
                            x=comparison_df['Empresa'],
                            y=comparison_df[f'Índice Mora {periodo1_str} (%)'],
                            marker_color='#e67e22'
                        ))
                        fig_indices_comp.add_trace(go.Bar(
                            name=f'Índice Mora {periodo2_str}',
                            x=comparison_df['Empresa'],
                            y=comparison_df[f'Índice Mora {periodo2_str} (%)'],
                            marker_color='#e74c3c'
                        ))
                        fig_indices_comp.update_layout(
                            title="Comparación de Índices Corriente y Mora",
                            xaxis_title="Empresa",
                            yaxis_title="Porcentaje (%)",
                            barmode='group',
                            xaxis_tickangle=-45,
                            height=500
                        )
                        st.plotly_chart(fig_indices_comp, use_container_width=True)
                        
                        # Botón de descarga
                        csv_comparison = comparison_df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 Descargar comparación como CSV",
                            data=csv_comparison,
                            file_name=f"comparacion_cartera_{periodo1_str.replace(' ', '_')}_vs_{periodo2_str.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
        else:
            st.info("💡 Se necesitan al menos 2 archivos de cartera para realizar comparaciones temporales.")

else:
    st.error("No se pudo cargar el archivo o está vacío. Por favor, verifica el archivo Test-cartera.xlsx")

