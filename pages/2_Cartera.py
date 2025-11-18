import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import math
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


def calcular_factor_confianza(cantidad_registros):
    """
    Calcula un factor de confianza basado en la cantidad de registros.
    Zonas con más registros tienen mayor confianza.
    Usa una función logarítmica para suavizar el efecto.
    """
    # Factor mínimo de 0.3 para zonas con muy pocos registros
    # Factor máximo de 1.0 para zonas con muchos registros
    # Usamos logaritmo para suavizar: log10(registros + 1) / log10(100)
    if cantidad_registros <= 0:
        return 0.3
    
    # Normalización: zonas con 100+ registros tienen factor 1.0
    # Zonas con 10 registros tienen factor ~0.7
    # Zonas con 1 registro tienen factor ~0.3
    factor = min(1.0, 0.3 + (math.log10(cantidad_registros + 1) / math.log10(100)) * 0.7)
    return factor


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
    
    # Cargar con caché y deduplicación
    df = load_excel_with_cache(
        selected_file,
        CARTERA_CACHE_DIR,
        processing_func=lambda df: process_cartera_data(df, deduplicate=True),
        header=7
    )
    
    # Agregar columna de empresa si no existe
    if df is not None and 'Cuenta' in df.columns and 'Empresa' not in df.columns:
        df['Empresa'] = df['Cuenta'].apply(clasificar_empresa)
    
    return df

# Detectar archivos disponibles primero
available_files = detect_cartera_files()

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
            index=current_index
        )
        
        # Obtener año y mes del archivo seleccionado
        año_selected = None
        mes_num_selected = None
        for mes_str, año, mes_num, _ in available_files:
            if mes_str == mes_selected:
                año_selected = año
                mes_num_selected = mes_num
                break
        
        # Actualizar session state
        st.session_state.cartera_selected_month = mes_selected
        st.session_state.cartera_selected_year = año_selected
        st.session_state.cartera_selected_month_num = mes_num_selected
        
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
    st.info(f"📅 **Mes seleccionado: {mes_selected}**")
    st.markdown("---")
    
    # Filtrar datos (por ahora todos, pero preparado para filtrado por mes)
    df_filtered = df.copy()
    
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
        "Sin Clasificar",
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
            st.dataframe(df_resumen, use_container_width=True)
            
            # Botón de descarga
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
                marker_color='#2ecc71'
            ))
            fig.add_trace(go.Bar(
                name='Tipo B',
                x=empresas_graf,
                y=indices_b,
                marker_color='#f1c40f'
            ))
            fig.add_trace(go.Bar(
                name='Tipo C',
                x=empresas_graf,
                y=indices_c,
                marker_color='#e67e22'
            ))
            fig.add_trace(go.Bar(
                name='Tipo D',
                x=empresas_graf,
                y=indices_d,
                marker_color='#e74c3c'
            ))
            fig.add_trace(go.Bar(
                name='Tipo E',
                x=empresas_graf,
                y=indices_e,
                marker_color='#c0392b'
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
        
        # Análisis de riesgo por zona (excluyendo Cartera Castigada, Otras y Sin Clasificar)
        st.markdown("---")
        st.subheader("⚠️ Análisis de Riesgo por Zona")
        st.markdown("**Nota:** Este análisis excluye la Cartera Castigada, Otras y Sin Clasificar para evaluar el riesgo potencial de nuevas operaciones de crédito.")
        
        # Filtrar datos excluyendo Cartera Castigada, Otras y Sin Clasificar
        empresas_excluidas = ['Cartera Castigada', 'Otras', 'Sin Clasificar']
        df_sin_castigada = df_filtered[~df_filtered['Empresa'].isin(empresas_excluidas)].copy()
        
        if 'Zona' in df_sin_castigada.columns and not df_sin_castigada.empty:
            # Calcular métricas por zona
            zonas_data = []
            
            for zona in df_sin_castigada['Zona'].dropna().unique():
                df_zona = df_sin_castigada[df_sin_castigada['Zona'] == zona].copy()
                
                if df_zona.empty:
                    continue
                
                total_cuota = df_zona['Total Cuota'].sum() if 'Total Cuota' in df_zona.columns else 0
                por_vencer = df_zona['Por Vencer'].sum() if 'Por Vencer' in df_zona.columns else 0
                dias30 = df_zona['Dias30'].sum() if 'Dias30' in df_zona.columns else 0
                dias60 = df_zona['Dias60'].sum() if 'Dias60' in df_zona.columns else 0
                dias90 = df_zona['Dias90'].sum() if 'Dias90' in df_zona.columns else 0
                dias_mas90 = df_zona['Dias Mas90'].sum() if 'Dias Mas90' in df_zona.columns else 0
                
                # Calcular índices de riesgo
                if total_cuota > 0:
                    indice_corriente = (por_vencer / total_cuota) * 100
                    indice_b = (dias30 / total_cuota) * 100
                    indice_c = (dias60 / total_cuota) * 100
                    indice_d = (dias90 / total_cuota) * 100
                    indice_e = (dias_mas90 / total_cuota) * 100
                    indice_mora_total = ((dias30 + dias60 + dias90 + dias_mas90) / total_cuota) * 100
                else:
                    indice_corriente = indice_b = indice_c = indice_d = indice_e = indice_mora_total = 0
                
                # Calcular score de riesgo (mayor valor = mayor riesgo)
                # Ponderación: Tipo E (más grave) tiene mayor peso
                score_riesgo = (indice_b * 1) + (indice_c * 2) + (indice_d * 3) + (indice_e * 5)
                
                # Calcular factor de confianza basado en cantidad de registros
                cantidad_registros = len(df_zona)
                factor_confianza = calcular_factor_confianza(cantidad_registros)
                
                # Score normalizado: ajusta el score por el factor de confianza
                # Zonas con pocos registros tienen su score reducido
                score_riesgo_normalizado = score_riesgo * factor_confianza
                
                zonas_data.append({
                    'Zona': zona,
                    'Cartera Total': total_cuota,
                    'Por Vencer': por_vencer,
                    'Días 30': dias30,
                    'Días 60': dias60,
                    'Días 90': dias90,
                    'Días +90': dias_mas90,
                    'Índice Corriente (%)': indice_corriente,
                    'Índice Tipo B (%)': indice_b,
                    'Índice Tipo C (%)': indice_c,
                    'Índice Tipo D (%)': indice_d,
                    'Índice Tipo E (%)': indice_e,
                    'Índice Mora Total (%)': indice_mora_total,
                    'Score de Riesgo': score_riesgo,
                    'Score de Riesgo Normalizado': score_riesgo_normalizado,
                    'Factor de Confianza': factor_confianza,
                    'Cantidad Registros': cantidad_registros
                })
            
            if zonas_data:
                df_zonas = pd.DataFrame(zonas_data)
                # Ordenar por score de riesgo normalizado descendente (mayor riesgo primero)
                df_zonas = df_zonas.sort_values('Score de Riesgo Normalizado', ascending=False)
                
                # Mostrar top zonas más riesgosas
                st.markdown("### 🔴 Top Zonas con Mayor Riesgo (Normalizado)")
                st.markdown("**Nota:** El score normalizado ajusta el riesgo según la cantidad de registros para evitar sesgos en zonas con pocos datos.")
                
                # Seleccionar columnas para mostrar
                columnas_display = [
                    'Zona', 'Cartera Total', 'Índice Mora Total (%)', 
                    'Índice Tipo B (%)', 'Índice Tipo C (%)', 
                    'Índice Tipo D (%)', 'Índice Tipo E (%)', 
                    'Score de Riesgo Normalizado', 'Factor de Confianza', 'Cantidad Registros'
                ]
                
                df_display = df_zonas[columnas_display].copy()
                df_display['Cartera Total'] = df_display['Cartera Total'].apply(format_currency)
                df_display['Índice Mora Total (%)'] = df_display['Índice Mora Total (%)'].apply(lambda x: f"{x:.2f}%")
                df_display['Índice Tipo B (%)'] = df_display['Índice Tipo B (%)'].apply(lambda x: f"{x:.2f}%")
                df_display['Índice Tipo C (%)'] = df_display['Índice Tipo C (%)'].apply(lambda x: f"{x:.2f}%")
                df_display['Índice Tipo D (%)'] = df_display['Índice Tipo D (%)'].apply(lambda x: f"{x:.2f}%")
                df_display['Índice Tipo E (%)'] = df_display['Índice Tipo E (%)'].apply(lambda x: f"{x:.2f}%")
                df_display['Score de Riesgo Normalizado'] = df_display['Score de Riesgo Normalizado'].apply(lambda x: f"{x:.2f}")
                df_display['Factor de Confianza'] = df_display['Factor de Confianza'].apply(lambda x: f"{x:.2f}")
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                # Gráficos de riesgo por zona
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 📊 Score de Riesgo Normalizado por Zona")
                    # Todas las zonas ordenadas por riesgo normalizado
                    fig_riesgo = go.Figure()
                    fig_riesgo.add_trace(go.Bar(
                        x=df_zonas['Zona'],
                        y=df_zonas['Score de Riesgo Normalizado'],
                        marker=dict(
                            color=df_zonas['Score de Riesgo Normalizado'],
                            colorscale='Reds',
                            showscale=True,
                            colorbar=dict(title="Score")
                        ),
                        text=[f"{x:.1f}" for x in df_zonas['Score de Riesgo Normalizado']],
                        textposition='outside',
                        hovertemplate='<b>%{x}</b><br>Score Normalizado: %{y:.2f}<br>Factor Confianza: %{customdata[0]:.2f}<br>Cantidad Registros: %{customdata[1]}<extra></extra>',
                        customdata=df_zonas[['Factor de Confianza', 'Cantidad Registros']].values
                    ))
                    fig_riesgo.update_layout(
                        title="Score de Riesgo Normalizado por Zona (ajustado por cantidad de registros)",
                        xaxis_title="Zona",
                        yaxis_title="Score de Riesgo Normalizado",
                        xaxis_tickangle=-45,
                        height=400
                    )
                    st.plotly_chart(fig_riesgo, use_container_width=True)
                
                with col2:
                    st.markdown("#### 📈 Índice de Mora Total por Zona")
                    # Todas las zonas ordenadas por índice de mora
                    fig_mora = go.Figure()
                    fig_mora.add_trace(go.Bar(
                        x=df_zonas['Zona'],
                        y=df_zonas['Índice Mora Total (%)'],
                        marker=dict(
                            color=df_zonas['Índice Mora Total (%)'],
                            colorscale='Oranges',
                            showscale=True,
                            colorbar=dict(title="%")
                        ),
                        text=[f"{x:.1f}%" for x in df_zonas['Índice Mora Total (%)']],
                        textposition='outside'
                    ))
                    fig_mora.update_layout(
                        title="Índice de Mora Total por Zona (ordenadas por mayor riesgo)",
                        xaxis_title="Zona",
                        yaxis_title="Índice de Mora (%)",
                        xaxis_tickangle=-45,
                        height=400
                    )
                    st.plotly_chart(fig_mora, use_container_width=True)
                
                # Gráfico de distribución de índices por zona
                st.markdown("#### 📉 Distribución de Índices de Riesgo por Zona")
                
                fig_indices = go.Figure()
                fig_indices.add_trace(go.Bar(
                    name='Tipo B',
                    x=df_zonas['Zona'],
                    y=df_zonas['Índice Tipo B (%)'],
                    marker_color='#f1c40f'
                ))
                fig_indices.add_trace(go.Bar(
                    name='Tipo C',
                    x=df_zonas['Zona'],
                    y=df_zonas['Índice Tipo C (%)'],
                    marker_color='#e67e22'
                ))
                fig_indices.add_trace(go.Bar(
                    name='Tipo D',
                    x=df_zonas['Zona'],
                    y=df_zonas['Índice Tipo D (%)'],
                    marker_color='#e74c3c'
                ))
                fig_indices.add_trace(go.Bar(
                    name='Tipo E',
                    x=df_zonas['Zona'],
                    y=df_zonas['Índice Tipo E (%)'],
                    marker_color='#c0392b'
                ))
                
                fig_indices.update_layout(
                    barmode='group',
                    title="Distribución de Índices de Riesgo por Zona (%)",
                    xaxis_title="Zona",
                    yaxis_title="Porcentaje (%)",
                    xaxis_tickangle=-45,
                    height=500
                )
                st.plotly_chart(fig_indices, use_container_width=True)
                
                # Botón de descarga
                csv_zonas = df_zonas.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Descargar análisis de riesgo por zona (CSV)",
                    data=csv_zonas,
                    file_name=f"riesgo_zonas_{mes_selected.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No se encontraron datos de zonas para analizar.")
        else:
            if 'Zona' not in df_sin_castigada.columns:
                st.warning("⚠️ La columna 'Zona' no está disponible en los datos.")
            else:
                st.warning("No hay datos disponibles después de filtrar la Cartera Castigada, Otras y Sin Clasificar.")
        
        # Sección de Comparación Temporal
        st.markdown("---")
        st.subheader("📊 Comparación Temporal de Cartera")
        
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
                # Usar session state para mantener la comparación visible
                comparison_key = f"comparison_{año1}_{mes1}_{año2}_{mes2}"
                
                if st.button("🔄 Comparar Períodos", type="primary", key="btn_compare"):
                    with st.spinner("Cargando y comparando períodos..."):
                        df1, df2, periodo1_str, periodo2_str = load_cartera_for_comparison(año1, mes1, año2, mes2)
                        
                        if df1 is not None and df2 is not None:
                            comparison_df = compare_cartera_periods(df1, df2, periodo1_str, periodo2_str, clasificar_empresa_func=clasificar_empresa)
                            
                            if comparison_df is not None and not comparison_df.empty:
                                # Guardar en session state para que persista
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
                        
                        # Mostrar tabla comparativa
                        st.dataframe(comparison_df, use_container_width=True, height=400)
                        
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

