import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from pathlib import Path
import sys

# Agregar utils al path
utils_path = Path(__file__).parent.parent / "utils"
if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

from data_loader import load_all_fiable_pipeline

PIPELINE_STATES = [
    "CREADO",
    "APROBADO",
    "RECHAZADO",
]

EXCLUDED_STATES = {"SOLICITADO", "EN ANALISIS", "EXCEPCIONADO", "REPROCESO", "PRE-LEGALIZADO"}

STATE_COLORS = [
    "#3498db",
    "#2ecc71",
    "#e74c3c",
]


def summarize_states(df, state_col='ESTADO_AGRUPADO'):
    total_registros = len(df)
    counts_raw = df[state_col].value_counts()
    cantidades = []
    porcentajes = []

    for estado in PIPELINE_STATES:
        if estado == "CREADO":
            valor = total_registros
            porcentaje = 100.0 if total_registros else 0.0
        else:
            valor = counts_raw.get(estado, 0)
            porcentaje = (valor / total_registros * 100) if total_registros else 0.0
        cantidades.append(valor)
        porcentajes.append(round(porcentaje, 1))

    summary = pd.DataFrame({
        'Estado': PIPELINE_STATES,
        'Cantidad': cantidades,
        '% del total': porcentajes
    })
    return summary, total_registros


st.title("🔄 Pipeline Créditos Fiable")
st.markdown("Análisis de estados de crédito, comparaciones mensuales y acumulados YTD.")

df = load_all_fiable_pipeline()
if df is None or df.empty:
    st.error("No se encontraron datos de Fiable en caché. Verifica `data/pipeline/raw`.")
    st.stop()

# Filtros básicos
st.sidebar.header("🔍 Filtros")
estado_options = [estado for estado in PIPELINE_STATES if estado in df['ESTADO_NORMALIZADO'].unique()]
estado_filter = st.sidebar.multiselect("Estado", estado_options, default=None)

asesores = sorted([x for x in df['ASESOR'].dropna().unique()]) if 'ASESOR' in df.columns else []
asesor_filter = st.sidebar.multiselect("Asesor", asesores) if asesores else []

estaciones = sorted([x for x in df['ESTACION'].dropna().unique()]) if 'ESTACION' in df.columns else []
estacion_filter = st.sidebar.multiselect("Estación", estaciones) if estaciones else []

productos = sorted([x for x in df['PRODUCTO'].dropna().unique()]) if 'PRODUCTO' in df.columns else []
producto_filter = st.sidebar.multiselect("Producto", productos) if productos else []

if 'FECHA' in df.columns and df['FECHA'].notna().any():
    min_date = df['FECHA'].min().date()
    max_date = df['FECHA'].max().date()
    fecha_rango = st.sidebar.date_input(
        "Rango de fechas (FECHA)",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
else:
    fecha_rango = None

df_filtered = df.copy()
df_filtered = df_filtered[~df_filtered['ESTADO_NORMALIZADO'].isin(EXCLUDED_STATES)]

if estado_filter:
    df_filtered = df_filtered[df_filtered['ESTADO_NORMALIZADO'].isin(estado_filter)]

if asesor_filter and 'ASESOR' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['ASESOR'].isin(asesor_filter)]

if estacion_filter and 'ESTACION' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['ESTACION'].isin(estacion_filter)]

if producto_filter and 'PRODUCTO' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['PRODUCTO'].isin(producto_filter)]

if fecha_rango and len(fecha_rango) == 2 and 'FECHA' in df_filtered.columns:
    start_date, end_date = fecha_rango
    if isinstance(start_date, date) and isinstance(end_date, date):
        df_filtered = df_filtered[
            (df_filtered['FECHA'].dt.date >= start_date) &
            (df_filtered['FECHA'].dt.date <= end_date)
        ]

if df_filtered.empty:
    st.warning("No hay registros que coincidan con los filtros seleccionados.")
    st.stop()

df_filtered = df_filtered.copy()
df_filtered['ESTADO_AGRUPADO'] = df_filtered['ESTADO_NORMALIZADO'].replace({'LEGALIZADO': 'APROBADO'})

periodos_disponibles = sorted(df_filtered['MES_PERIODO'].dropna().unique(), reverse=True)

if 'FECHA' in df_filtered.columns and df_filtered['FECHA'].notna().any():
    min_fecha = df_filtered['FECHA'].min().date()
    max_fecha = df_filtered['FECHA'].max().date()
else:
    today = date.today()
    min_fecha = today
    max_fecha = today

selected_date = st.sidebar.date_input(
    "Mes de análisis",
    value=max_fecha,
    min_value=min_fecha,
    max_value=max_fecha
)
if isinstance(selected_date, tuple):
    selected_date = selected_date[0]

periodo_actual = pd.Timestamp(selected_date).to_period('M') if selected_date else None

if periodos_disponibles and periodo_actual not in periodos_disponibles:
    st.warning("El mes seleccionado no tiene registros; se mostrará el periodo más reciente disponible.")
    periodo_actual = periodos_disponibles[0]
    selected_date = periodo_actual.to_timestamp().date()

periodo_actual_label = periodo_actual.strftime('%B %Y') if periodo_actual is not None else "Todos los registros"

comparar_toggle = st.sidebar.checkbox(
    "Comparar con otro mes",
    value=True if len(periodos_disponibles) > 1 else False
)
periodo_comparacion = None
periodo_comparacion_label = None
if comparar_toggle and len(periodos_disponibles) > 1:
    prev_month_date = (selected_date.replace(day=1) - timedelta(days=1))
    if prev_month_date < min_fecha:
        prev_month_date = min_fecha
    compare_date = st.sidebar.date_input(
        "Mes a comparar",
        value=prev_month_date,
        min_value=min_fecha,
        max_value=max_fecha
    )
    if isinstance(compare_date, tuple):
        compare_date = compare_date[0]
    if compare_date != selected_date:
        periodo_comparacion = pd.Timestamp(compare_date).to_period('M')
        if periodos_disponibles and periodo_comparacion not in periodos_disponibles:
            st.warning("El mes de comparación no tiene registros; se omitirá.")
            periodo_comparacion = None
        else:
            periodo_comparacion_label = periodo_comparacion.strftime('%B %Y')

if periodo_actual:
    df_periodo = df_filtered[df_filtered['MES_PERIODO'] == periodo_actual]
else:
    df_periodo = df_filtered.copy()

if periodo_comparacion:
    df_comparacion = df_filtered[df_filtered['MES_PERIODO'] == periodo_comparacion]
else:
    df_comparacion = pd.DataFrame(columns=df_filtered.columns)

st.info(f"Analizando periodo: **{periodo_actual_label}**"
        f"{'' if not periodo_comparacion_label else f' vs {periodo_comparacion_label}'}")

summary_actual, total_actual = summarize_states(df_periodo)
summary_actual = summary_actual.set_index('Estado')

if not df_comparacion.empty:
    summary_comp, total_comp = summarize_states(df_comparacion)
    summary_comp = summary_comp.set_index('Estado')
    summary_actual['Comparación'] = summary_comp['Cantidad']
    summary_actual['Variación'] = summary_actual['Cantidad'] - summary_actual['Comparación']
else:
    summary_actual['Comparación'] = 0
    summary_actual['Variación'] = summary_actual['Cantidad']

col_label_actual = f"Cantidad ({periodo_actual_label})" if periodo_actual_label else "Cantidad"
col_label_comparacion = (
    f"Cantidad ({periodo_comparacion_label})"
    if periodo_comparacion_label else
    "Comparación"
)
summary_display = summary_actual.rename(columns={'Cantidad': col_label_actual})
if 'Comparación' in summary_display.columns:
    summary_display = summary_display.rename(columns={'Comparación': col_label_comparacion})

st.subheader("📊 Distribución por estado")
col_total, col_delta = st.columns(2)
col_total.metric("Total registros periodo", f"{int(total_actual):,}")
if not df_comparacion.empty:
    delta_total = total_actual - total_comp
    col_delta.metric("Variación total vs mes anterior", f"{delta_total:+,}", f"{(delta_total / total_comp * 100):+.1f}%" if total_comp else None)
else:
    col_delta.metric("Variación total vs mes anterior", f"{total_actual:+,}", None)

st.dataframe(summary_display, use_container_width=True)

# Métrica de aprobados (incluye legalizados) vs creados en el mes
aprobados_periodo = (df_periodo['ESTADO_AGRUPADO'] == 'APROBADO').sum()
pct_aprobado_periodo = (aprobados_periodo / len(df_periodo) * 100) if len(df_periodo) else 0
col_leg_mes_1, col_leg_mes_2 = st.columns(2)
col_leg_mes_1.metric("Aprobados (mes)", f"{aprobados_periodo:,}")
col_leg_mes_2.metric("% Aprobados vs creados (mes)", f"{pct_aprobado_periodo:.1f}%")

fig_estados = px.bar(
    summary_actual.reset_index(),
    x='Estado',
    y='Cantidad',
    color='Estado',
    color_discrete_sequence=STATE_COLORS,
    title="Estados en el periodo seleccionado"
)
st.plotly_chart(fig_estados, use_container_width=True)

# YTD vs YTD previo
if periodo_actual:
    selected_year = periodo_actual.year
    selected_month = periodo_actual.month
else:
    selected_year = df_filtered['AÑO'].dropna().max()
    selected_month = df_filtered['MES'].dropna().max()

if pd.notna(selected_year) and pd.notna(selected_month):
    df_ytd = df_filtered[
        (df_filtered['AÑO'] == selected_year) &
        (df_filtered['MES'] <= selected_month)
    ]
    df_ytd_prev = df_filtered[
        (df_filtered['AÑO'] == selected_year - 1) &
        (df_filtered['MES'] <= selected_month)
    ]

    ytd_actual = len(df_ytd)
    ytd_prev = len(df_ytd_prev)

    st.markdown("---")
    st.subheader("📆 Año corrido vs año anterior")
    col_ytd1, col_ytd2, col_ytd3 = st.columns(3)
    delta_ytd = ytd_actual - ytd_prev
    delta_pct_total = (delta_ytd / ytd_prev * 100) if ytd_prev else 0
    col_ytd1.metric(f"YTD {int(selected_year)}", f"{ytd_actual:,}", f"{delta_ytd:+,}")
    col_ytd2.metric(f"YTD {int(selected_year - 1)}", f"{ytd_prev:,}")
    col_ytd3.metric("Δ % YTD", f"{delta_pct_total:+.1f}{'%' if ytd_prev else ''}")

    aprobados_ytd = (df_ytd['ESTADO_AGRUPADO'] == 'APROBADO').sum()
    aprobados_ytd_prev = (df_ytd_prev['ESTADO_AGRUPADO'] == 'APROBADO').sum()
    pct_aprobado_ytd = (aprobados_ytd / ytd_actual * 100) if ytd_actual else 0
    pct_aprobado_ytd_prev = (aprobados_ytd_prev / ytd_prev * 100) if ytd_prev else 0
    delta_aprobados = aprobados_ytd - aprobados_ytd_prev
    delta_pct_aprobados = pct_aprobado_ytd - pct_aprobado_ytd_prev

    col_legal1, col_legal2, col_legal3 = st.columns(3)
    col_legal1.metric(
        f"Aprobados YTD {int(selected_year)}",
        f"{aprobados_ytd:,}",
        f"{delta_aprobados:+,}"
    )
    col_legal2.metric(f"Aprobados YTD {int(selected_year - 1)}", f"{aprobados_ytd_prev:,}")
    delta_pct_aprobados_count = (delta_aprobados / aprobados_ytd_prev * 100) if aprobados_ytd_prev else 0
    col_legal3.metric("Δ Aprobados YTD", f"{delta_aprobados:+,}", f"{delta_pct_aprobados_count:+.1f}%")

    col_pct1, col_pct2, col_pct3 = st.columns(3)
    col_pct1.metric(
        f"% Aprobados vs creados YTD {int(selected_year)}",
        f"{pct_aprobado_ytd:.1f}%",
        f"{delta_pct_aprobados:+.1f} pp"
    )
    col_pct2.metric(f"% Aprobados vs creados YTD {int(selected_year - 1)}", f"{pct_aprobado_ytd_prev:.1f}%")
    col_pct3.metric("Δ puntos porcentuales", f"{delta_pct_aprobados:+.1f} pp")

# Evolución mensual
st.markdown("---")
st.subheader("📈 Evolución mensual de créditos")
monthly = (
    df_filtered.dropna(subset=['MES_PERIODO'])
    .groupby(['MES_PERIODO', 'ESTADO_AGRUPADO'])
    .size()
    .reset_index(name='Cantidad')
)
if not monthly.empty:
    # Reemplazar serie de CREADO por el total de créditos del mes
    monthly_totals = (
        df_filtered.dropna(subset=['MES_PERIODO'])
        .groupby('MES_PERIODO')
        .size()
        .reset_index(name='Cantidad')
        .assign(ESTADO_AGRUPADO='CREADO')
    )
    monthly = monthly[monthly['ESTADO_AGRUPADO'] != 'CREADO']
    monthly = pd.concat([monthly, monthly_totals], ignore_index=True)

    monthly['Mes'] = monthly['MES_PERIODO'].dt.strftime('%Y-%m')
    fig_monthly = px.line(
        monthly,
        x='Mes',
        y='Cantidad',
        color='ESTADO_AGRUPADO',
        markers=True,
        title="Tendencia mensual por estado"
    )
    fig_monthly.update_layout(xaxis={'categoryorder': 'category ascending'})

    trend_data = monthly[monthly['ESTADO_AGRUPADO'] == 'APROBADO'].sort_values('MES_PERIODO')
    if not trend_data.empty:
        trend_data = trend_data.copy()
        trend_data['Trend'] = trend_data['Cantidad'].rolling(window=3, min_periods=1).mean()
        fig_monthly.add_trace(
            go.Scatter(
                x=trend_data['Mes'],
                y=trend_data['Trend'],
                mode='lines',
                name='Tendencia Aprobados (media 3M)',
                line=dict(color='#2ecc71', dash='dash'),
            )
        )

    st.plotly_chart(fig_monthly, use_container_width=True)

# Tabla detallada
st.markdown("---")
st.subheader("📋 Registros filtrados")
cols_display = ['FECHA', 'ESTADO_AGRUPADO', 'CLIENTE', 'ASESOR', 'PRODUCTO', 'ESTACION', 'CONSECUTIVO', 'IDENTIFICACION']
cols_existing = [col for col in cols_display if col in df_filtered.columns]
st.dataframe(df_filtered[cols_existing], use_container_width=True, height=400)

csv_download = df_filtered.to_csv(index=False).encode('utf-8-sig')
st.download_button(
    label="📥 Descargar CSV filtrado",
    data=csv_download,
    file_name="fiable_pipeline_filtrado.csv",
    mime="text/csv"
)

