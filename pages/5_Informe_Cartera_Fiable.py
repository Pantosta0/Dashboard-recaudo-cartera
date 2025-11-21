import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from fpdf import FPDF
import sys
from pathlib import Path

# Agregar el directorio utils al path
utils_path = Path(__file__).parent.parent / "utils"
if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

from data_loader import load_cartera_fiable_files
from context_builders import build_cartera_fiable_context
from llm import render_llm_assistant

# Título principal
st.title("📊 Informe Integrado de Cartera FIABLE")
st.markdown("---")

# Estilos
st.markdown(
    """
    <style>
        .metric-card {
            background-color: #1f2937;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            border: 1px solid #374151;
        }
        .metric-title {
            font-size: 0.9rem;
            color: #9ca3af;
            margin-bottom: 0.5rem;
        }
        .metric-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #f9fafb;
        }
        .section-header {
            font-size: 1.3rem;
            font-weight: 600;
            margin-top: 2rem;
            margin-bottom: 1rem;
            color: #f9fafb;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Función para formatear moneda
def format_currency(value):
    try:
        return f"${value:,.0f}"
    except (TypeError, ValueError):
        return "$0"

# Función para formatear porcentaje
def format_percentage(value):
    try:
        return f"{value:.2f}%"
    except (TypeError, ValueError):
        return "0.00%"

# Cargar datos
@st.cache_data
def load_fiable_data():
    """Carga los 3 archivos de cartera FIABLE"""
    return load_cartera_fiable_files()

# Cargar datos
with st.spinner("Cargando archivos de cartera FIABLE..."):
    df_colocada, df_financiero, df_proyectadas = load_fiable_data()

# Verificar que se cargaron los archivos
if df_colocada is None and df_financiero is None and df_proyectadas is None:
    st.error("❌ No se encontraron los archivos de cartera FIABLE. Por favor, asegúrate de que los siguientes archivos estén en el directorio:")
    st.write("📁 **Ubicación:** `data/cartera_fiable/raw/`")
    st.write("- Cartera Colocada FIABLE OCTUBRE 2025.xlsx")
    st.write("- Cartera Financiero X edades FIABLE OCTUBRE 2025.xlsx")
    st.write("- Cartera Proyectadas FIABLE OCTUBRE 2025.xlsx")
    st.info("💡 También se buscarán en el directorio raíz como respaldo.")
    st.stop()

# Mostrar información de archivos cargados
st.info("📁 **Archivos cargados:**")
cols_info = st.columns(3)
if df_colocada is not None:
    cols_info[0].success(f"✅ Colocada: {len(df_colocada):,} registros")
else:
    cols_info[0].warning("⚠️ Colocada: No disponible")
    
if df_financiero is not None:
    cols_info[1].success(f"✅ Financiero X edades: {len(df_financiero):,} registros")
else:
    cols_info[1].warning("⚠️ Financiero X edades: No disponible")
    
if df_proyectadas is not None:
    cols_info[2].success(f"✅ Proyectadas: {len(df_proyectadas):,} registros")
else:
    cols_info[2].warning("⚠️ Proyectadas: No disponible")

st.markdown("---")

# ========== RESUMEN EJECUTIVO ==========
st.subheader("📈 Resumen Ejecutivo")

# Calcular métricas principales
if df_financiero is not None:
    total_capital = df_financiero['Capital'].sum() if 'Capital' in df_financiero.columns else 0
    total_cuota = df_financiero['Cuota'].sum() if 'Cuota' in df_financiero.columns else 0
    total_interes = df_financiero['Interes'].sum() if 'Interes' in df_financiero.columns else 0
    total_fianza = df_financiero['Fianza'].sum() if 'Fianza' in df_financiero.columns else 0
    
    # Análisis por edades
    if 'EDADES' in df_financiero.columns:
        # Usar la misma lógica que se usa en el análisis por edades más abajo
        # Primero agrupar por EDADES, luego normalizar (misma función normalize_edad)
        edades_data = df_financiero.groupby('EDADES').agg({
            'Capital': 'sum',
            'Cuota': 'sum',
            'Interes': 'sum'
        }).reset_index()
        
        # Función para normalizar nombres de edades (misma que se usa más abajo)
        def normalize_edad(edad_str):
            edad_str = str(edad_str).strip()
            if 'PorVencer' in edad_str or 'Por Vencer' in edad_str or 'por vencer' in edad_str.lower():
                return 'PorVencer'
            elif edad_str == '+90' or edad_str.startswith('+90') or edad_str.startswith('+ 90'):
                return 'Mas90'
            elif 'Mas90' in edad_str or 'Mas 90' in edad_str or 'Más 90' in edad_str or 'Mas de 90' in edad_str or 'Más de 90' in edad_str:
                return 'Mas90'
            elif edad_str == '30' or '30' in edad_str:
                return '30'
            elif edad_str == '60' or '60' in edad_str:
                return '60'
            elif edad_str == '90' or '90' in edad_str:
                return '90'
            return edad_str
        
        # Normalizar edades
        edades_data['EDADES_NORM'] = edades_data['EDADES'].apply(normalize_edad)
        
        # Agrupar por edades normalizadas y sumar
        edades_agrupadas = edades_data.groupby('EDADES_NORM').agg({
            'Capital': 'sum',
            'Cuota': 'sum',
            'Interes': 'sum'
        }).reset_index()
        
        # Extraer valores por categoría
        por_vencer = edades_agrupadas[edades_agrupadas['EDADES_NORM'] == 'PorVencer']['Capital'].sum() if len(edades_agrupadas[edades_agrupadas['EDADES_NORM'] == 'PorVencer']) > 0 else 0
        dias_30 = edades_agrupadas[edades_agrupadas['EDADES_NORM'] == '30']['Capital'].sum() if len(edades_agrupadas[edades_agrupadas['EDADES_NORM'] == '30']) > 0 else 0
        dias_60 = edades_agrupadas[edades_agrupadas['EDADES_NORM'] == '60']['Capital'].sum() if len(edades_agrupadas[edades_agrupadas['EDADES_NORM'] == '60']) > 0 else 0
        dias_90 = edades_agrupadas[edades_agrupadas['EDADES_NORM'] == '90']['Capital'].sum() if len(edades_agrupadas[edades_agrupadas['EDADES_NORM'] == '90']) > 0 else 0
        mas_90 = edades_agrupadas[edades_agrupadas['EDADES_NORM'] == 'Mas90']['Capital'].sum() if len(edades_agrupadas[edades_agrupadas['EDADES_NORM'] == 'Mas90']) > 0 else 0
    else:
        por_vencer = dias_30 = dias_60 = dias_90 = mas_90 = 0
    
    total_mora = dias_30 + dias_60 + dias_90 + mas_90
    # Calcular todos los índices por edades
    indice_corriente = (por_vencer / total_capital * 100) if total_capital > 0 else 0
    indice_30 = (dias_30 / total_capital * 100) if total_capital > 0 else 0
    indice_60 = (dias_60 / total_capital * 100) if total_capital > 0 else 0
    indice_90 = (dias_90 / total_capital * 100) if total_capital > 0 else 0
    indice_mas_90 = (mas_90 / total_capital * 100) if total_capital > 0 else 0
    indice_mora = (total_mora / total_capital * 100) if total_capital > 0 else 0
else:
    total_capital = total_cuota = total_interes = total_fianza = 0
    por_vencer = dias_30 = dias_60 = dias_90 = mas_90 = 0
    total_mora = 0
    indice_corriente = indice_30 = indice_60 = indice_90 = indice_mas_90 = indice_mora = 0

# Métricas de Cartera Proyectadas
if df_proyectadas is not None:
    total_proyectadas = df_proyectadas['Total'].sum() if 'Total' in df_proyectadas.columns else 0
    por_vencer_proy = df_proyectadas['PorVencer'].sum() if 'PorVencer' in df_proyectadas.columns else 0
    treinta_proy = df_proyectadas['Treinta_Dias'].sum() if 'Treinta_Dias' in df_proyectadas.columns else 0
    sesenta_proy = df_proyectadas['Sesenta_Dias'].sum() if 'Sesenta_Dias' in df_proyectadas.columns else 0
    noventa_proy = df_proyectadas['Noventa_Dias'].sum() if 'Noventa_Dias' in df_proyectadas.columns else 0
    mas_noventa_proy = df_proyectadas['Mas_de_Noventa'].sum() if 'Mas_de_Noventa' in df_proyectadas.columns else 0
    total_mora_proy = treinta_proy + sesenta_proy + noventa_proy + mas_noventa_proy
else:
    total_proyectadas = por_vencer_proy = treinta_proy = sesenta_proy = noventa_proy = mas_noventa_proy = total_mora_proy = 0

# Métricas de Cartera Colocada
if df_colocada is not None:
    total_colocada = df_colocada['ValorCuota'].sum() if 'ValorCuota' in df_colocada.columns else 0
    total_saldo_capital = df_colocada['SaldoCapital'].sum() if 'SaldoCapital' in df_colocada.columns else 0
    total_prestamo = df_colocada['ValorPrestamo'].sum() if 'ValorPrestamo' in df_colocada.columns else 0
    num_creditos = df_colocada['NumeroFactura'].nunique() if 'NumeroFactura' in df_colocada.columns else 0
else:
    total_colocada = total_saldo_capital = total_prestamo = num_creditos = 0

# Mostrar métricas principales
st.markdown("### 💰 Métricas Generales")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "💰 Capital Total",
        format_currency(total_capital),
        help="Capital total de la cartera financiero"
    )

with col2:
    st.metric(
        "📊 Cuota Total",
        format_currency(total_cuota),
        help="Total de cuotas"
    )

with col3:
    st.metric(
        "💵 Interés Total",
        format_currency(total_interes),
        help="Total de intereses"
    )

with col4:
    st.metric(
        "🛡️ Fianza Total",
        format_currency(total_fianza),
        help="Total de fianza"
    )

st.markdown("### 📊 Índices por Edades de Vencimiento")
st.markdown("*Todos los índices suman el 100% del capital total*")

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric(
        "✅ Por Vencer",
        format_percentage(indice_corriente),
        help="Porcentaje de cartera al día"
    )

with col2:
    st.metric(
        "⚠️ 30 Días",
        format_percentage(indice_30),
        help="Porcentaje de cartera con 30 días de vencimiento"
    )

with col3:
    st.metric(
        "⚠️ 60 Días",
        format_percentage(indice_60),
        help="Porcentaje de cartera con 60 días de vencimiento"
    )

with col4:
    st.metric(
        "⚠️ 90 Días",
        format_percentage(indice_90),
        help="Porcentaje de cartera con 90 días de vencimiento"
    )

with col5:
    st.metric(
        "🔴 Más de 90",
        format_percentage(indice_mas_90),
        help="Porcentaje de cartera con más de 90 días de vencimiento"
    )

with col6:
    st.metric(
        "⚠️ Mora Total",
        format_percentage(indice_mora),
        help="Porcentaje total de cartera en mora (30+60+90+Mas90)"
    )

# Verificación: mostrar suma de índices
suma_indices = indice_corriente + indice_30 + indice_60 + indice_90 + indice_mas_90
st.caption(f"📊 **Suma de índices:** {format_percentage(suma_indices)} (debería ser 100%)")

st.markdown("---")

# Asistente Gemini - Posicionado después de métricas para mayor visibilidad
from context_builders import build_cartera_fiable_context
context = build_cartera_fiable_context(
    df_financiero=df_financiero,
    df_proyectadas=df_proyectadas,
    df_colocada=df_colocada,
)
render_llm_assistant(
    "cartera_fiable",
    context,
    default_question="Genera un resumen ejecutivo del informe de cartera FIABLE.",
    presets=[
        "Analiza la salud de la cartera y niveles de mora.",
        "Compara cartera financiero vs proyectadas vs colocada.",
        "Identifica riesgos y recomendaciones prioritarias.",
    ],
)
st.markdown("---")

# ========== ANÁLISIS POR EDADES ==========
st.subheader("📊 Análisis por Edades de Vencimiento")

if df_financiero is not None and 'EDADES' in df_financiero.columns:
    # Gráfico de barras por edades
    edades_data = df_financiero.groupby('EDADES').agg({
        'Capital': 'sum',
        'Cuota': 'sum',
        'Interes': 'sum'
    }).reset_index()
    
    # Función para normalizar nombres de edades
    def normalize_edad(edad_str):
        edad_str = str(edad_str).strip()
        if 'PorVencer' in edad_str or 'Por Vencer' in edad_str or 'por vencer' in edad_str.lower():
            return 'PorVencer'
        elif edad_str == '+90' or edad_str.startswith('+90') or edad_str.startswith('+ 90'):
            return 'Mas90'
        elif 'Mas90' in edad_str or 'Mas 90' in edad_str or 'Más 90' in edad_str or 'Mas de 90' in edad_str or 'Más de 90' in edad_str:
            return 'Mas90'
        elif edad_str == '30' or '30' in edad_str:
            return '30'
        elif edad_str == '60' or '60' in edad_str:
            return '60'
        elif edad_str == '90' or '90' in edad_str:
            return '90'
        return edad_str
    
    # Normalizar edades
    edades_data['EDADES_NORM'] = edades_data['EDADES'].apply(normalize_edad)
    
    # Agrupar por edades normalizadas
    edades_data = edades_data.groupby('EDADES_NORM').agg({
        'Capital': 'sum',
        'Cuota': 'sum',
        'Interes': 'sum'
    }).reset_index()
    edades_data.columns = ['EDADES', 'Capital', 'Cuota', 'Interes']
    
    # Ordenar edades
    orden_edades = ['PorVencer', '30', '60', '90', 'Mas90']
    edades_data['EDADES_ORDER'] = edades_data['EDADES'].apply(
        lambda x: orden_edades.index(x) if x in orden_edades else 999
    )
    edades_data = edades_data.sort_values('EDADES_ORDER')
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de Capital por Edades
        fig_capital = go.Figure()
        fig_capital.add_trace(go.Bar(
            x=edades_data['EDADES'],
            y=edades_data['Capital'],
            marker_color=['#2ecc71' if x == 'PorVencer' else '#f1c40f' if x == '30' else '#e67e22' if x == '60' else '#e74c3c' if x == '90' else '#c0392b' for x in edades_data['EDADES']],
            text=[format_currency(x) for x in edades_data['Capital']],
            textposition='outside'
        ))
        fig_capital.update_layout(
            title="Capital por Edades de Vencimiento",
            xaxis_title="Edades",
            yaxis_title="Capital ($)",
            height=400
        )
        st.plotly_chart(fig_capital, width="stretch")
    
    with col2:
        # Gráfico de Cuota por Edades
        fig_cuota = go.Figure()
        fig_cuota.add_trace(go.Bar(
            x=edades_data['EDADES'],
            y=edades_data['Cuota'],
            marker_color=['#2ecc71' if x == 'PorVencer' else '#f1c40f' if x == '30' else '#e67e22' if x == '60' else '#e74c3c' if x == '90' else '#c0392b' for x in edades_data['EDADES']],
            text=[format_currency(x) for x in edades_data['Cuota']],
            textposition='outside'
        ))
        fig_cuota.update_layout(
            title="Cuota por Edades de Vencimiento",
            xaxis_title="Edades",
            yaxis_title="Cuota ($)",
            height=400
        )
        st.plotly_chart(fig_cuota, width="stretch")
    
    # Tabla resumen por edades
    st.markdown("### 📋 Resumen por Edades")
    resumen_edades = edades_data[['EDADES', 'Capital', 'Cuota', 'Interes']].copy()
    resumen_edades['Capital'] = resumen_edades['Capital'].apply(format_currency)
    resumen_edades['Cuota'] = resumen_edades['Cuota'].apply(format_currency)
    resumen_edades['Interes'] = resumen_edades['Interes'].apply(format_currency)
    resumen_edades.columns = ['Edades', 'Capital', 'Cuota', 'Interés']
    st.dataframe(resumen_edades, width="stretch", hide_index=True)

# ========== ANÁLISIS DE CARTERA PROYECTADAS ==========
if df_proyectadas is not None:
    st.markdown("---")
    st.subheader("📈 Análisis de Cartera Proyectadas")
    
    # Métricas de cartera proyectadas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Proyectadas", format_currency(total_proyectadas))
    with col2:
        st.metric("Por Vencer", format_currency(por_vencer_proy))
    with col3:
        st.metric("30 Días", format_currency(treinta_proy))
    with col4:
        st.metric("60+ Días", format_currency(sesenta_proy + noventa_proy + mas_noventa_proy))
    
    # Gráfico de distribución por edades (Proyectadas)
    if 'Total' in df_proyectadas.columns:
        fig_proy = go.Figure()
        edades_proy = ['PorVencer', 'Treinta_Dias', 'Sesenta_Dias', 'Noventa_Dias', 'Mas_de_Noventa']
        valores_proy = [por_vencer_proy, treinta_proy, sesenta_proy, noventa_proy, mas_noventa_proy]
        labels_proy = ['Por Vencer', '30 Días', '60 Días', '90 Días', 'Más de 90']
        
        fig_proy.add_trace(go.Bar(
            x=labels_proy,
            y=valores_proy,
            marker_color=['#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#c0392b'],
            text=[format_currency(x) for x in valores_proy],
            textposition='outside'
        ))
        fig_proy.update_layout(
            title="Distribución de Cartera Proyectadas por Edades",
            xaxis_title="Edades",
            yaxis_title="Monto ($)",
            height=400
        )
        st.plotly_chart(fig_proy, width="stretch")
    
    # Análisis por calificación
    if 'Calificacion' in df_proyectadas.columns:
        st.markdown("### 📊 Análisis por Calificación")
        calif_data = df_proyectadas.groupby('Calificacion').agg({
            'Total': 'sum',
            'PorVencer': 'sum',
            'Treinta_Dias': 'sum',
            'Sesenta_Dias': 'sum',
            'Noventa_Dias': 'sum',
            'Mas_de_Noventa': 'sum'
        }).reset_index()
        
        fig_calif = go.Figure()
        fig_calif.add_trace(go.Bar(
            x=calif_data['Calificacion'],
            y=calif_data['Total'],
            text=[format_currency(x) for x in calif_data['Total']],
            textposition='outside'
        ))
        fig_calif.update_layout(
            title="Cartera por Calificación",
            xaxis_title="Calificación",
            yaxis_title="Total ($)",
            height=400
        )
        st.plotly_chart(fig_calif, width="stretch")

# ========== ANÁLISIS DE CARTERA COLOCADA ==========
if df_colocada is not None:
    st.markdown("---")
    st.subheader("💼 Análisis de Cartera Colocada")
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Valor Total Cuotas", format_currency(total_colocada))
    with col2:
        st.metric("📊 Saldo Capital", format_currency(total_saldo_capital))
    with col3:
        st.metric("💵 Valor Préstamo", format_currency(total_prestamo))
    with col4:
        st.metric("📝 Número de Créditos", f"{num_creditos:,}")
    
    # Análisis por producto
    if 'Producto' in df_colocada.columns:
        st.markdown("### 📦 Análisis por Producto")
        producto_data = df_colocada.groupby('Producto').agg({
            'ValorCuota': 'sum',
            'SaldoCapital': 'sum',
            'ValorPrestamo': 'sum',
            'NumeroFactura': 'nunique'
        }).reset_index()
        producto_data.columns = ['Producto', 'Valor Cuotas', 'Saldo Capital', 'Valor Préstamo', 'Número Créditos']
        
        fig_producto = go.Figure()
        fig_producto.add_trace(go.Bar(
            x=producto_data['Producto'],
            y=producto_data['Valor Cuotas'],
            text=[format_currency(x) for x in producto_data['Valor Cuotas']],
            textposition='outside'
        ))
        fig_producto.update_layout(
            title="Valor de Cuotas por Producto",
            xaxis_title="Producto",
            yaxis_title="Valor ($)",
            height=400,
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig_producto, width="stretch")
        
        st.dataframe(producto_data, width="stretch", hide_index=True)
    
    # Análisis por cuenta
    if 'NombreCuentaCartera' in df_colocada.columns:
        st.markdown("### 🏢 Análisis por Cuenta")
        cuenta_data = df_colocada.groupby('NombreCuentaCartera').agg({
            'ValorCuota': 'sum',
            'SaldoCapital': 'sum',
            'NumeroFactura': 'nunique'
        }).reset_index()
        cuenta_data = cuenta_data.sort_values('ValorCuota', ascending=False)
        cuenta_data.columns = ['Cuenta', 'Valor Cuotas', 'Saldo Capital', 'Número Créditos']
        
        fig_cuenta = go.Figure()
        fig_cuenta.add_trace(go.Bar(
            x=cuenta_data['Cuenta'],
            y=cuenta_data['Valor Cuotas'],
            text=[format_currency(x) for x in cuenta_data['Valor Cuotas']],
            textposition='outside'
        ))
        fig_cuenta.update_layout(
            title="Valor de Cuotas por Cuenta",
            xaxis_title="Cuenta",
            yaxis_title="Valor ($)",
            height=500,
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig_cuenta, width="stretch")

# ========== TABLA COMPARATIVA ==========
st.markdown("---")
st.subheader("📊 Tabla Comparativa General")

# Crear tabla comparativa
comparison_data = {
    'Métrica': [
        'Capital Total',
        'Cuota Total',
        'Interés Total',
        'Fianza Total',
        'Por Vencer',
        '30 Días',
        '60 Días',
        '90 Días',
        'Más de 90',
        'Total Mora',
        'Índice Corriente (%)',
        'Índice Mora (%)'
    ],
    'Cartera Financiero': [
        format_currency(total_capital),
        format_currency(total_cuota),
        format_currency(total_interes),
        format_currency(total_fianza),
        format_currency(por_vencer),
        format_currency(dias_30),
        format_currency(dias_60),
        format_currency(dias_90),
        format_currency(mas_90),
        format_currency(total_mora),
        format_percentage(indice_corriente),
        format_percentage(indice_mora)
    ],
    'Cartera Proyectadas': [
        format_currency(total_proyectadas),
        '-',
        '-',
        '-',
        format_currency(por_vencer_proy),
        format_currency(treinta_proy),
        format_currency(sesenta_proy),
        format_currency(noventa_proy),
        format_currency(mas_noventa_proy),
        format_currency(total_mora_proy),
        format_percentage((por_vencer_proy / total_proyectadas * 100) if total_proyectadas > 0 else 0),
        format_percentage((total_mora_proy / total_proyectadas * 100) if total_proyectadas > 0 else 0)
    ]
}

df_comparison = pd.DataFrame(comparison_data)
st.dataframe(df_comparison, width="stretch", hide_index=True)

# Botón de descarga
csv = df_comparison.to_csv(index=False).encode('utf-8-sig')
st.download_button(
    label="📥 Descargar tabla comparativa como CSV",
    data=csv,
    file_name=f"informe_cartera_fiable_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime="text/csv"
)

st.markdown("---")
st.markdown("**Informe generado el:** " + datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

