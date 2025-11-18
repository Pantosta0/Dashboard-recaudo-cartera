import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import calendar
import numpy as np
import sys
from pathlib import Path

# Agregar el directorio utils al path
utils_path = Path(__file__).parent.parent / "utils"
if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

from data_loader import (
    load_excel_with_cache, 
    detect_recaudo_files, 
    process_recaudo_data,
    RECAUDO_CACHE_DIR
)

# Título principal
st.title("💰 Dashboard de Recaudo")
st.markdown("---")

# Estilos responsivos para adaptar la visualización a diferentes pantallas
st.markdown(
    """
    <style>
        /* Estilos para métricas - adaptar tamaño de fuente */
        [data-testid="stMetricValue"] {
            font-size: clamp(1.2rem, 2.5vw, 2rem) !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: clamp(0.85rem, 1.2vw, 1rem) !important;
        }
        
        /* Estilos para tablas - hacer scroll horizontal si es necesario */
        .stDataFrame {
            overflow-x: auto;
        }
        
        /* Estilos para gráficos - asegurar que se adapten */
        .js-plotly-plot {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* Ajustar tamaño de texto en subheaders */
        h3 {
            font-size: clamp(1.1rem, 2vw, 1.5rem) !important;
        }
        
        /* Ajustar tamaño de texto en headers */
        h2 {
            font-size: clamp(1.3rem, 2.5vw, 1.8rem) !important;
        }
        
        /* Ajustar padding de columnas en pantallas pequeñas */
        @media (max-width: 768px) {
            .stMetric {
                padding: 0.5rem !important;
            }
        }
        
        /* Asegurar que los selectboxes se adapten */
        .stSelectbox label {
            font-size: clamp(0.9rem, 1.3vw, 1rem) !important;
        }
        
        /* Ajustar tamaño de texto en expanders */
        .streamlit-expanderHeader {
            font-size: clamp(0.95rem, 1.4vw, 1.1rem) !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Cargar datos
@st.cache_data
def load_data(mes_selected=None, año=None, mes_num=None):
    """
    Carga datos de recaudo para un mes específico.
    Si no se especifica mes, carga el más reciente disponible.
    """
    # Detectar archivos disponibles
    available_files = detect_recaudo_files()
    
    if not available_files:
        st.error("No se encontraron archivos de recaudo. Por favor, coloca archivos con formato 'recaudo-YYYY-MM.xlsx' en data/recaudo/raw/ o en el directorio raíz.")
        return None
    
    # Si se especifica mes, buscar ese archivo
    if mes_selected and año and mes_num:
        selected_file = None
        for mes_str, año_file, mes_file, file_path in available_files:
            if año_file == año and mes_file == mes_num:
                selected_file = file_path
                break
        
        if selected_file is None:
            st.warning(f"No se encontró archivo para {mes_selected}. Usando el más reciente disponible.")
            selected_file = available_files[0][3]
    else:
        # Usar el archivo más reciente
        selected_file = available_files[0][3]
    
    # Cargar con caché
    df = load_excel_with_cache(
        selected_file,
        RECAUDO_CACHE_DIR,
        processing_func=process_recaudo_data
    )
    
    return df

# Detectar archivos disponibles primero
available_files = detect_recaudo_files()

if available_files:
    # Inicializar session state
    if 'recaudo_selected_month' not in st.session_state:
        st.session_state.recaudo_selected_month = available_files[0][0]
        st.session_state.recaudo_selected_year = available_files[0][1]
        st.session_state.recaudo_selected_month_num = available_files[0][2]
    
    # Crear lista de opciones
    meses_opciones = [f"{mes_str}" for mes_str, _, _, _ in available_files]
    
    # Selector de mes en el sidebar
    st.sidebar.header("🔍 Filtros")
    
    if len(meses_opciones) > 1:
        current_index = 0
        if st.session_state.recaudo_selected_month in meses_opciones:
            current_index = meses_opciones.index(st.session_state.recaudo_selected_month)
        
        mes_selected = st.sidebar.selectbox(
            "Seleccionar Mes de Recaudo", 
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
        
        # Recargar si cambió el mes
        if (st.session_state.recaudo_selected_month != mes_selected or
            st.session_state.recaudo_selected_year != año_selected):
            st.session_state.recaudo_selected_month = mes_selected
            st.session_state.recaudo_selected_year = año_selected
            st.session_state.recaudo_selected_month_num = mes_num_selected
            df = load_data(mes_selected, año_selected, mes_num_selected)
        else:
            df = load_data(mes_selected, año_selected, mes_num_selected)
    else:
        mes_selected = meses_opciones[0]
        año_selected = available_files[0][1]
        mes_num_selected = available_files[0][2]
        df = load_data(mes_selected, año_selected, mes_num_selected)
else:
    st.sidebar.header("🔍 Filtros")
    df = load_data()
    mes_selected = "Sin datos disponibles"

if df is not None and not df.empty:
    # Mostrar mes seleccionado
    if available_files:
        st.info(f"📅 **Mes seleccionado: {mes_selected}**")
        st.markdown("---")
    
    # Verificar fechas inválidas y mostrar aviso si existen
    fecha_columns = ['FECHA_VENCIMIENTO', 'FECHA_RECAUDO']
    fechas_invalidas = {}
    
    for col in fecha_columns:
        if col in df.columns:
            # Contar valores NaN o NaT (fechas inválidas)
            invalid_count = df[col].isna().sum()
            if invalid_count > 0:
                fechas_invalidas[col] = invalid_count
    
    # Mostrar aviso si hay fechas inválidas
    if fechas_invalidas:
        st.warning("⚠️ **Advertencia: Fechas inválidas detectadas**")
        for col, count in fechas_invalidas.items():
            st.warning(f"  - **{col}**: {count:,} registro(s) con fecha inválida o vacía (de {len(df):,} total)")
        st.markdown("---")
    
    # Filtro por FUENTE
    if 'FUENTE' in df.columns:
        fuentes = ['Todas'] + sorted([str(x) for x in df['FUENTE'].dropna().unique()])
        fuente_selected = st.sidebar.selectbox("Fuente", fuentes)
    else:
        fuente_selected = 'Todas'
    
    # Filtro por NOMBRE_FUENTE
    if 'NOMBRE_FUENTE' in df.columns:
        nombres_fuentes = ['Todas'] + sorted([str(x) for x in df['NOMBRE_FUENTE'].dropna().unique()])
        nombre_fuente_selected = st.sidebar.selectbox("Nombre Fuente", nombres_fuentes)
    else:
        nombre_fuente_selected = 'Todas'
    
    # Filtro por zona
    if 'ZONA' in df.columns:
        zonas = ['Todas'] + sorted([str(x) for x in df['ZONA'].dropna().unique()])
        zona_selected = st.sidebar.selectbox("Zona", zonas)
    else:
        zona_selected = 'Todas'
    
    # Filtro por cliente
    if 'CLIENTE' in df.columns:
        clientes = ['Todos'] + sorted([str(x) for x in df['CLIENTE'].dropna().unique()])
        cliente_selected = st.sidebar.selectbox("Cliente", clientes)
    else:
        cliente_selected = 'Todos'
    
    # Filtro por rango de fechas de RECAUDO
    if 'FECHA_RECAUDO' in df.columns:
        # Filtrar solo fechas válidas (sin NaN)
        fechas_validas = df['FECHA_RECAUDO'].dropna()
        
        if len(fechas_validas) > 0:
            fecha_min = fechas_validas.min()
            fecha_max = fechas_validas.max()
            
            fecha_min_date = fecha_min.date()
            fecha_max_date = fecha_max.date()
            
            # Por defecto, usar octubre (1 al 31 de octubre)
            # Obtener el año actual o el año de la fecha más reciente
            año_actual = fecha_max_date.year
            fecha_default_min = date(año_actual, 10, 1)
            fecha_default_max = date(año_actual, 10, 31)
            
            # Asegurar que el rango por defecto no exceda las fechas reales
            if fecha_default_min < fecha_min_date:
                fecha_default_min = fecha_min_date
            if fecha_default_max > fecha_max_date:
                fecha_default_max = fecha_max_date
            
            fecha_range = st.sidebar.date_input(
                "Rango de Fechas de Recaudo",
                value=(fecha_default_min, fecha_default_max),
                min_value=fecha_min_date,
                max_value=fecha_max_date
            )
        else:
            fecha_range = None
    else:
        fecha_range = None
    
    # Aplicar filtros
    df_filtered = df.copy()
    
    if fuente_selected != 'Todas' and 'FUENTE' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['FUENTE'].astype(str) == fuente_selected]
    
    if nombre_fuente_selected != 'Todas' and 'NOMBRE_FUENTE' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['NOMBRE_FUENTE'].astype(str) == nombre_fuente_selected]
    
    if zona_selected != 'Todas' and 'ZONA' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['ZONA'].astype(str) == zona_selected]
    
    if cliente_selected != 'Todos' and 'CLIENTE' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['CLIENTE'].astype(str) == cliente_selected]
    
    if fecha_range and len(fecha_range) == 2 and 'FECHA_RECAUDO' in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered['FECHA_RECAUDO'].dt.date >= fecha_range[0]) &
            (df_filtered['FECHA_RECAUDO'].dt.date <= fecha_range[1])
        ]
    
    # Función auxiliar para sumar columnas numéricas
    def sumar_columna(df, columna):
        """Suma los valores de una columna numérica (debería ser float64)"""
        if columna not in df.columns:
            return 0
        try:
            # Las columnas ya deberían ser float64 después de la carga
            # Si no lo son, intentar convertir
            if not pd.api.types.is_numeric_dtype(df[columna]):
                # Convertir a numérico si no lo es
                serie_limpia = df[columna].astype(str).str.replace(',', '', regex=False).str.replace('$', '', regex=False).str.replace(' ', '', regex=False).str.strip()
                df[columna] = pd.to_numeric(serie_limpia, errors='coerce').astype('float64')
            
            # Sumar (incluye valores negativos si existen)
            resultado = df[columna].sum()
            return float(resultado) if pd.notna(resultado) else 0.0
        except Exception as e:
            # En caso de error, intentar método alternativo
            try:
                serie_numerica = pd.to_numeric(df[columna], errors='coerce').astype('float64')
                resultado = serie_numerica.sum()
                return float(resultado) if pd.notna(resultado) else 0.0
            except:
                return 0.0
    
    # Sección de diagnóstico (expandible)
    with st.expander("🔍 Diagnóstico de Datos (click para ver)", expanded=False):
        st.write("**Información de columnas numéricas:**")
        diagnostic_cols = ['SESENTA_DIAS', 'NOVENTA_DIAS', 'MAS_NOVENTA', 'TREINTA_DIAS', 'POR_VENCER']
        for col in diagnostic_cols:
            if col in df_filtered.columns:
                st.write(f"**{col}:**")
                st.write(f"  - Tipo de dato: {df_filtered[col].dtype}")
                st.write(f"  - Valores no nulos: {df_filtered[col].notna().sum()}")
                st.write(f"  - Valores únicos (primeros 10): {df_filtered[col].dropna().unique()[:10].tolist()}")
                # Mostrar suma directa
                suma_directa = df_filtered[col].sum() if pd.api.types.is_numeric_dtype(df_filtered[col]) else "No numérico"
                st.write(f"  - Suma directa: {suma_directa}")
                # Mostrar suma con función
                suma_funcion = sumar_columna(df_filtered, col)
                st.write(f"  - Suma con función: {suma_funcion}")
                st.write("---")
    
    # KPIs principales
    st.header("📊 Indicadores Clave (KPIs)")
    
    # Calcular totales individuales primero
    total_por_vencer = sumar_columna(df_filtered, 'POR_VENCER') if 'POR_VENCER' in df_filtered.columns else 0
    total_30 = sumar_columna(df_filtered, 'TREINTA_DIAS') if 'TREINTA_DIAS' in df_filtered.columns else 0
    total_60 = sumar_columna(df_filtered, 'SESENTA_DIAS') if 'SESENTA_DIAS' in df_filtered.columns else 0
    total_90 = sumar_columna(df_filtered, 'NOVENTA_DIAS') if 'NOVENTA_DIAS' in df_filtered.columns else 0
    total_mas_90 = sumar_columna(df_filtered, 'MAS_NOVENTA') if 'MAS_NOVENTA' in df_filtered.columns else 0
    
    # Total Recaudo (suma de todos los montos)
    total_recaudo = total_por_vencer + total_30 + total_60 + total_90 + total_mas_90
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    # Total de registros
    total_registros = len(df_filtered)
    col1.metric("Total Registros", f"{total_registros:,}")
    
    # Total Recaudo
    col2.metric("Total Recaudo", f"${total_recaudo:,.0f}")
    
    # Total por vencer
    if 'POR_VENCER' in df_filtered.columns:
        col3.metric("Por Vencer", f"${total_por_vencer:,.0f}")
    else:
        col3.metric("Por Vencer", "N/A")
    
    # Total 30 días
    if 'TREINTA_DIAS' in df_filtered.columns:
        col4.metric("30 Días", f"${total_30:,.0f}")
    else:
        col4.metric("30 Días", "N/A")
    
    # Total 60 días
    if 'SESENTA_DIAS' in df_filtered.columns:
        col5.metric("60 Días", f"${total_60:,.0f}")
    else:
        col5.metric("60 Días", "N/A")
    
    # Total 90+ días
    total_90_plus = total_90 + total_mas_90
    if 'NOVENTA_DIAS' in df_filtered.columns and 'MAS_NOVENTA' in df_filtered.columns:
        col6.metric("90+ Días", f"${total_90_plus:,.0f}")
    else:
        col6.metric("90+ Días", "N/A")
    
    st.markdown("---")
    
    # Gráficos principales
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Distribución por Días Vencidos")
        
        # Preparar datos para el gráfico
        categorias = []
        valores = []
        
        if 'POR_VENCER' in df_filtered.columns:
            valor = sumar_columna(df_filtered, 'POR_VENCER')
            if valor > 0:
                categorias.append('Por Vencer')
                valores.append(valor)
        
        if 'TREINTA_DIAS' in df_filtered.columns:
            valor = sumar_columna(df_filtered, 'TREINTA_DIAS')
            if valor > 0:
                categorias.append('30 Días')
                valores.append(valor)
        
        if 'SESENTA_DIAS' in df_filtered.columns:
            valor = sumar_columna(df_filtered, 'SESENTA_DIAS')
            if valor > 0:
                categorias.append('60 Días')
                valores.append(valor)
        
        if 'NOVENTA_DIAS' in df_filtered.columns:
            valor = sumar_columna(df_filtered, 'NOVENTA_DIAS')
            if valor > 0:
                categorias.append('90 Días')
                valores.append(valor)
        
        if 'MAS_NOVENTA' in df_filtered.columns:
            valor = sumar_columna(df_filtered, 'MAS_NOVENTA')
            if valor > 0:
                categorias.append('Más de 90 Días')
                valores.append(valor)
        
        if categorias and valores:
            # Paleta de colores personalizada: verde (bueno) a rojo (malo)
            colores = ['#2ecc71', '#f39c12', '#e67e22', '#e74c3c', '#c0392b']
            fig_pie = px.pie(
                values=valores,
                names=categorias,
                title="Distribución de Cartera por Antigüedad",
                color_discrete_sequence=colores[:len(categorias)]
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.subheader("📊 Distribución por Fuente")
        
        if 'FUENTE' in df_filtered.columns:
            fuente_counts = df_filtered['FUENTE'].value_counts().head(10)
            
            if len(fuente_counts) > 0:
                fig_bar = px.bar(
                    x=fuente_counts.index,
                    y=fuente_counts.values,
                    title="Top 10 Fuentes por Cantidad de Registros",
                    labels={'x': 'Fuente', 'y': 'Cantidad'},
                    color=fuente_counts.values,
                    color_continuous_scale='Blues'
                )
                fig_bar.update_layout(showlegend=False, xaxis_tickangle=-45)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("No hay datos para mostrar")
        else:
            st.info("Columna FUENTE no encontrada")
    
    # Análisis por zona y cliente
    st.markdown("---")
    st.subheader("📍 Distribución por Zona")
    
    if 'ZONA' in df_filtered.columns:
        zona_counts = df_filtered['ZONA'].value_counts().head(10)
        
        if len(zona_counts) > 0:
            fig_zona = px.bar(
                x=zona_counts.index,
                y=zona_counts.values,
                title="Top 10 Zonas por Cantidad de Registros",
                labels={'x': 'Zona', 'y': 'Cantidad'},
                color=zona_counts.values,
                color_continuous_scale='Purples'
            )
            fig_zona.update_layout(showlegend=False)
            st.plotly_chart(fig_zona, use_container_width=True)
    
    # Análisis por cliente
    st.markdown("---")
    st.subheader("👥 Análisis por Cliente")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if 'CLIENTE' in df_filtered.columns:
            # Top clientes por cantidad
            top_clientes = df_filtered['CLIENTE'].value_counts().head(10)
            
            if len(top_clientes) > 0:
                fig_clientes = px.bar(
                    x=top_clientes.values,
                    y=top_clientes.index,
                    orientation='h',
                    title="Top 10 Clientes por Cantidad de Registros",
                    labels={'x': 'Cantidad', 'y': 'Cliente'},
                    color=top_clientes.values,
                    color_continuous_scale='Greens'
                )
                fig_clientes.update_layout(showlegend=False)
                st.plotly_chart(fig_clientes, use_container_width=True)
    
    with col2:
        if 'CLIENTE' in df_filtered.columns and 'DIAS_VENCIDOS' in df_filtered.columns:
            # Promedio de días vencidos por cliente
            if df_filtered['DIAS_VENCIDOS'].dtype in ['int64', 'float64']:
                dias_por_cliente = df_filtered.groupby('CLIENTE')['DIAS_VENCIDOS'].mean().sort_values(ascending=False).head(10)
                
                if len(dias_por_cliente) > 0:
                    fig_dias = px.bar(
                        x=dias_por_cliente.values,
                        y=dias_por_cliente.index,
                        orientation='h',
                        title="Top 10 Clientes por Promedio de Días Vencidos",
                        labels={'x': 'Días Promedio', 'y': 'Cliente'},
                        color=dias_por_cliente.values,
                        color_continuous_scale='Reds'
                    )
                    fig_dias.update_layout(showlegend=False)
                    st.plotly_chart(fig_dias, use_container_width=True)
    
    # Análisis temporal
    st.markdown("---")
    st.subheader("📅 Análisis Temporal")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if 'FECHA_VENCIMIENTO' in df_filtered.columns:
            df_filtered['MES_VENCIMIENTO'] = df_filtered['FECHA_VENCIMIENTO'].dt.to_period('M')
            vencimientos_mes = df_filtered['MES_VENCIMIENTO'].value_counts().sort_index()
            
            if len(vencimientos_mes) > 0:
                fig_temporal = px.line(
                    x=vencimientos_mes.index.astype(str),
                    y=vencimientos_mes.values,
                    title="Registros por Mes de Vencimiento",
                    labels={'x': 'Mes', 'y': 'Cantidad de Registros'},
                    markers=True
                )
                fig_temporal.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_temporal, use_container_width=True)
    
    with col2:
        if 'FECHA_RECAUDO' in df_filtered.columns:
            df_filtered['MES_RECAUDO'] = df_filtered['FECHA_RECAUDO'].dt.to_period('M')
            recaudos_mes = df_filtered['MES_RECAUDO'].value_counts().sort_index()
            
            if len(recaudos_mes) > 0:
                fig_recaudo = px.line(
                    x=recaudos_mes.index.astype(str),
                    y=recaudos_mes.values,
                    title="Registros por Mes de Recaudo",
                    labels={'x': 'Mes', 'y': 'Cantidad de Registros'},
                    markers=True,
                    line_shape='spline'
                )
                fig_recaudo.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_recaudo, use_container_width=True)
    
    # Distribución de días vencidos
    st.markdown("---")
    st.subheader("⏱️ Análisis de Días Vencidos")
    
    if 'DIAS_VENCIDOS' in df_filtered.columns and df_filtered['DIAS_VENCIDOS'].dtype in ['int64', 'float64']:
        col1, col2 = st.columns(2)
        
        with col1:
            # Histograma de días vencidos
            fig_hist = px.histogram(
                df_filtered,
                x='DIAS_VENCIDOS',
                nbins=50,
                title="Distribución de Días Vencidos",
                labels={'DIAS_VENCIDOS': 'Días Vencidos', 'count': 'Frecuencia'}
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        
        with col2:
            # Box plot de días vencidos
            fig_box = px.box(
                df_filtered,
                y='DIAS_VENCIDOS',
                title="Distribución de Días Vencidos (Box Plot)",
                labels={'DIAS_VENCIDOS': 'Días Vencidos'}
            )
            st.plotly_chart(fig_box, use_container_width=True)
    
    # Tabla de datos
    st.markdown("---")
    st.subheader("📋 Tabla de Datos")
    
    # Seleccionar columnas a mostrar
    columnas_disponibles = df_filtered.columns.tolist()
    columnas_seleccionadas = st.multiselect(
        "Seleccionar columnas a mostrar",
        columnas_disponibles,
        default=columnas_disponibles[:10] if len(columnas_disponibles) > 10 else columnas_disponibles
    )
    
    if columnas_seleccionadas:
        df_display = df_filtered[columnas_seleccionadas]
        
        # Paginación
        page_size = st.selectbox("Registros por página", [10, 25, 50, 100], index=1)
        
        total_pages = (len(df_display) - 1) // page_size + 1
        page = st.number_input("Página", min_value=1, max_value=total_pages, value=1)
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        st.dataframe(
            df_display.iloc[start_idx:end_idx],
            use_container_width=True,
            height=400
        )
        
        st.info(f"Mostrando registros {start_idx + 1} a {min(end_idx, len(df_display))} de {len(df_display)} totales")
        
        # Botón de descarga
        csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Descargar datos filtrados como CSV",
            data=csv,
            file_name=f"recaudo_filtrado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    # Estadísticas descriptivas
    st.markdown("---")
    st.subheader("📈 Estadísticas Descriptivas")
    
    if 'DIAS_VENCIDOS' in df_filtered.columns and df_filtered['DIAS_VENCIDOS'].dtype in ['int64', 'float64']:
        stats = df_filtered['DIAS_VENCIDOS'].describe()
        st.dataframe(stats.to_frame().T, use_container_width=True)
    
    # Resumen por fuente
    st.markdown("---")
    st.subheader("🔗 Resumen por Fuente")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if 'FUENTE' in df_filtered.columns:
            fuente_summary = df_filtered.groupby('FUENTE').agg({
                'CLIENTE': 'count' if 'CLIENTE' in df_filtered.columns else 'size'
            }).rename(columns={'CLIENTE': 'Cantidad'})
            
            if 'DIAS_VENCIDOS' in df_filtered.columns and df_filtered['DIAS_VENCIDOS'].dtype in ['int64', 'float64']:
                fuente_summary['Promedio_Dias_Vencidos'] = df_filtered.groupby('FUENTE')['DIAS_VENCIDOS'].mean()
            
            if 'POR_VENCER' in df_filtered.columns and df_filtered['POR_VENCER'].dtype in ['int64', 'float64']:
                fuente_summary['Total_Por_Vencer'] = df_filtered.groupby('FUENTE')['POR_VENCER'].sum()
            
            st.write("**Resumen por FUENTE:**")
            st.dataframe(fuente_summary, use_container_width=True)
    
    with col2:
        if 'NOMBRE_FUENTE' in df_filtered.columns:
            nombre_fuente_summary = df_filtered.groupby('NOMBRE_FUENTE').agg({
                'CLIENTE': 'count' if 'CLIENTE' in df_filtered.columns else 'size'
            }).rename(columns={'CLIENTE': 'Cantidad'})
            
            if 'DIAS_VENCIDOS' in df_filtered.columns and df_filtered['DIAS_VENCIDOS'].dtype in ['int64', 'float64']:
                nombre_fuente_summary['Promedio_Dias_Vencidos'] = df_filtered.groupby('NOMBRE_FUENTE')['DIAS_VENCIDOS'].mean()
            
            if 'POR_VENCER' in df_filtered.columns and df_filtered['POR_VENCER'].dtype in ['int64', 'float64']:
                nombre_fuente_summary['Total_Por_Vencer'] = df_filtered.groupby('NOMBRE_FUENTE')['POR_VENCER'].sum()
            
            st.write("**Resumen por NOMBRE_FUENTE:**")
            st.dataframe(nombre_fuente_summary, use_container_width=True)
    
    # Análisis comparativo FUENTE vs NOMBRE_FUENTE
    if 'FUENTE' in df_filtered.columns and 'NOMBRE_FUENTE' in df_filtered.columns:
        st.markdown("---")
        st.subheader("📊 Análisis Comparativo: FUENTE vs NOMBRE_FUENTE")
        
        comparativo = df_filtered.groupby(['FUENTE', 'NOMBRE_FUENTE']).size().reset_index(name='Cantidad')
        comparativo = comparativo.sort_values('Cantidad', ascending=False).head(20)
        
        if len(comparativo) > 0:
            fig_comparativo = px.sunburst(
                comparativo,
                path=['FUENTE', 'NOMBRE_FUENTE'],
                values='Cantidad',
                title="Distribución: FUENTE → NOMBRE_FUENTE"
            )
            st.plotly_chart(fig_comparativo, use_container_width=True)
            
            st.dataframe(comparativo, use_container_width=True)

else:
    st.error("No se pudo cargar el archivo o está vacío. Por favor, verifica el archivo Test-recaudo.xlsx")

