import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import sys

# Agregar carpeta utils al path
utils_path = Path(__file__).parent.parent / "utils"
if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

from data_loader import load_all_colocacion_fiable

MONTH_NAMES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def format_currency(value, decimals=2):
    if pd.isna(value):
        return "—"
    formatted = f"{value:,.{decimals}f}"
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"${formatted}"


def build_summary(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if group_col not in df.columns:
        return pd.DataFrame(columns=[group_col, "Unidades", "Total COP"])
    summary = (
        df.groupby(group_col)
        .agg(
            Unidades=("TOTALFAC", lambda x: len(x) - (x < 0).sum() * 2),  # Restar 2 por cada negativo
            Total_COP=("TOTALFAC", "sum"),  # Sumar todos (los negativos ya reducen el total)
        )
        .reset_index()
    )
    summary["Total_COP"] = summary["Total_COP"].fillna(0.0)
    summary = summary.sort_values("Unidades", ascending=False)
    return summary


st.title("📦 Colocación Fiable")
st.markdown(
    "Comparativo de unidades vendidas (registros) y valor facturado (`TOTALFAC`) "
    "a partir de los archivos consolidados por año."
)

df = load_all_colocacion_fiable()
if df is None or df.empty:
    st.error(
        "No se encontraron archivos en `data/colocacion/raw`. "
        "Ubica allí los Excel de colocación (uno por año o mes) y vuelve a intentar."
    )
    st.stop()

if "TOTALFAC" not in df.columns:
    st.error("La columna `TotalFac` es obligatoria para calcular los montos.")
    st.stop()

st.sidebar.header("🔍 Filtros")

if "ANIO" not in df.columns or "MES" not in df.columns:
    st.error("El dataset debe incluir las columnas `AÑO` y `MES` para calcular el YTD.")
    st.stop()

years_available = sorted([int(x) for x in df["ANIO"].dropna().unique().tolist()])
if not years_available:
    st.error("No se detectaron años disponibles en los datos de colocación.")
    st.stop()

selected_year = st.sidebar.selectbox(
    "Año objetivo (YTD)",
    years_available,
    index=len(years_available) - 1,
)

months_in_year = (
    df[df["ANIO"] == selected_year]["MES"]
    .dropna()
    .astype(int)
    .unique()
    .tolist()
)
months_in_year = sorted(months_in_year)

if not months_in_year:
    st.error(f"No hay meses registrados para el año {selected_year}.")
    st.stop()

selected_month = st.sidebar.select_slider(
    "Mes corte YTD",
    options=months_in_year,
    format_func=lambda x: MONTH_NAMES.get(int(x), str(x)),
    value=months_in_year[-1],
)

df_filtered = df.copy()

if "CENTRO_COSTO" in df.columns:
    centro_options = sorted(df["CENTRO_COSTO"].dropna().unique().tolist())
    centro_filter = st.sidebar.multiselect("Centro de costo", centro_options)
    if centro_filter:
        df_filtered = df_filtered[df_filtered["CENTRO_COSTO"].isin(centro_filter)]

if "VENDEDOR" in df.columns:
    vendedor_options = sorted(df["VENDEDOR"].dropna().unique().tolist())
    vendedor_filter = st.sidebar.multiselect("Vendedor", vendedor_options)
    if vendedor_filter:
        df_filtered = df_filtered[df_filtered["VENDEDOR"].isin(vendedor_filter)]

if "MODALIDAD_VENTA" in df.columns:
    modalidad_options = sorted(df["MODALIDAD_VENTA"].dropna().unique().tolist())
    modalidad_filter = st.sidebar.multiselect("Modalidad de venta", modalidad_options)
    if modalidad_filter:
        df_filtered = df_filtered[df_filtered["MODALIDAD_VENTA"].isin(modalidad_filter)]

if "BODEGA" in df.columns:
    bodega_options = sorted(df["BODEGA"].dropna().unique().tolist())
    bodega_filter = st.sidebar.multiselect("Bodega", bodega_options)
    if bodega_filter:
        df_filtered = df_filtered[df_filtered["BODEGA"].isin(bodega_filter)]

if "FECHA_DOCUMENTO" in df.columns and df["FECHA_DOCUMENTO"].notna().any():
    min_date = df["FECHA_DOCUMENTO"].min().date()
    max_date = df["FECHA_DOCUMENTO"].max().date()
    date_range = st.sidebar.date_input(
        "Rango de fecha documento",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df_filtered[
            (df_filtered["FECHA_DOCUMENTO"].dt.date >= start_date)
            & (df_filtered["FECHA_DOCUMENTO"].dt.date <= end_date)
        ]

years_to_keep = {selected_year, selected_year - 1}
df_filtered = df_filtered[df_filtered["ANIO"].isin(years_to_keep)]

if df_filtered.empty:
    st.warning("No hay registros con los filtros actualizados.")
    st.stop()

df_ytd_current = df_filtered[
    (df_filtered["ANIO"] == selected_year)
    & df_filtered["MES"].notna()
    & (df_filtered["MES"] <= selected_month)
]
df_ytd_prev = df_filtered[
    (df_filtered["ANIO"] == selected_year - 1)
    & df_filtered["MES"].notna()
    & (df_filtered["MES"] <= selected_month)
]

if df_ytd_current.empty:
    st.warning(
        f"No hay datos para {MONTH_NAMES.get(selected_month, selected_month)} {selected_year} con los filtros aplicados."
    )
    st.stop()

period_label = f"{MONTH_NAMES.get(selected_month, selected_month)} {selected_year}"
st.info(
    f"Análisis YTD acumulado hasta **{period_label}**. "
    f"Se contrasta con el mismo periodo de {selected_year - 1}."
)

# Contar todos los registros menos 2 por cada TotalFac negativo (devoluciones)
total_unidades = len(df_ytd_current) - (df_ytd_current["TOTALFAC"] < 0).sum() * 2
total_cop = df_ytd_current["TOTALFAC"].sum(skipna=True)  # Incluir todos (los negativos reducen el total)
ticket_promedio = total_cop / total_unidades if total_unidades else 0
total_unidades_prev = len(df_ytd_prev) - (df_ytd_prev["TOTALFAC"] < 0).sum() * 2
total_cop_prev = df_ytd_prev["TOTALFAC"].sum(skipna=True)  # Incluir todos

col1, col2, col3 = st.columns(3)
col1.metric("Unidades (registros)", f"{total_unidades:,}")
col2.metric("Total COP", format_currency(total_cop, decimals=2))
col3.metric("Ticket promedio", format_currency(ticket_promedio, decimals=2))

st.markdown("---")
st.subheader("📅 Mes seleccionado vs mes anterior")

# Primero calcular los valores del mes actual
df_month_current = df_filtered[
    (df_filtered["ANIO"] == selected_year) & (df_filtered["MES"] == selected_month)
]
# Contar todos los registros menos 2 por cada TotalFac negativo (devoluciones)
month_units = len(df_month_current) - (df_month_current["TOTALFAC"] < 0).sum() * 2
month_total = df_month_current["TOTALFAC"].sum(skipna=True)  # Incluir todos (los negativos reducen el total)
month_ticket = month_total / month_units if month_units else 0

# Comparar con el mes anterior del mismo año
prev_month = selected_month - 1
prev_month_year = selected_year
if prev_month < 1:
    prev_month = 12
    prev_month_year = selected_year - 1

df_month_prev_same_year = df_filtered[
    (df_filtered["ANIO"] == prev_month_year) & (df_filtered["MES"] == prev_month)
]

month_prev_units = len(df_month_prev_same_year) - (df_month_prev_same_year["TOTALFAC"] < 0).sum() * 2 if not df_month_prev_same_year.empty else 0
month_prev_total = df_month_prev_same_year["TOTALFAC"].sum(skipna=True) if not df_month_prev_same_year.empty else 0
month_prev_ticket = month_prev_total / month_prev_units if month_prev_units else 0

prev_month_label = f"{MONTH_NAMES.get(prev_month, prev_month)} {prev_month_year}"

delta_prev_units = month_units - month_prev_units
delta_prev_total = month_total - month_prev_total
delta_prev_ticket = month_ticket - month_prev_ticket
pct_prev_units = (delta_prev_units / month_prev_units * 100) if month_prev_units > 0 else 0
pct_prev_total = (delta_prev_total / month_prev_total * 100) if month_prev_total > 0 else 0
pct_prev_ticket = (delta_prev_ticket / month_prev_ticket * 100) if month_prev_ticket > 0 else 0

col_prev1, col_prev2, col_prev3 = st.columns(3)
col_prev1.metric(
    f"Unidades {period_label}",
    f"{month_units:,}",
    f"{delta_prev_units:+,} ({pct_prev_units:+.1f}%)" if month_prev_units else None,
)
col_prev2.metric(
    f"Total COP {period_label}",
    format_currency(month_total, decimals=2),
    f"{format_currency(delta_prev_total, decimals=2)} ({pct_prev_total:+.1f}%)" if month_prev_total else None,
)
col_prev3.metric(
    f"Ticket promedio {period_label}",
    format_currency(month_ticket, decimals=2),
    f"{format_currency(delta_prev_ticket, decimals=2)} ({pct_prev_ticket:+.1f}%)" if month_prev_ticket else None,
)

if not df_month_prev_same_year.empty:
    compare_prev_df = pd.DataFrame(
        {
            "Mes": [period_label, prev_month_label],
            "Unidades": [int(month_units), int(month_prev_units)],
            "Total COP": [month_total, month_prev_total],
        }
    )
    col_chart_prev1, col_chart_prev2 = st.columns(2)
    with col_chart_prev1:
        fig_prev_units = px.bar(
            compare_prev_df,
            x="Mes",
            y="Unidades",
            text_auto=".0f",
            title="Unidades: mes actual vs mes anterior",
            color="Mes",
            color_discrete_sequence=["#3498db", "#95a5a6"],
        )
        fig_prev_units.update_layout(yaxis_tickformat=".0f", xaxis_tickformat=".0f", showlegend=False)
        st.plotly_chart(fig_prev_units, use_container_width=True)
    with col_chart_prev2:
        fig_prev_total = px.bar(
            compare_prev_df,
            x="Mes",
            y="Total COP",
            text_auto=",.0f",
            title="Total COP: mes actual vs mes anterior",
            color="Mes",
            color_discrete_sequence=["#2ecc71", "#95a5a6"],
        )
        fig_prev_total.update_layout(yaxis_tickformat=",", showlegend=False)
        st.plotly_chart(fig_prev_total, use_container_width=True)
else:
    st.info(f"No hay datos para {prev_month_label} con los filtros actuales.")

st.markdown("---")
st.subheader("📅 Mes seleccionado vs mismo mes año anterior")

df_month_prev = df_filtered[
    (df_filtered["ANIO"] == selected_year - 1) & (df_filtered["MES"] == selected_month)
]
# Contar todos los registros menos 2 por cada TotalFac negativo (devoluciones)
month_units_prev = len(df_month_prev) - (df_month_prev["TOTALFAC"] < 0).sum() * 2
month_total_prev = df_month_prev["TOTALFAC"].sum(skipna=True)  # Incluir todos (los negativos reducen el total)
month_ticket_prev = month_total_prev / month_units_prev if month_units_prev else 0

delta_month_units = month_units - month_units_prev
delta_month_total = month_total - month_total_prev
delta_ticket = month_ticket - month_ticket_prev
pct_month_units = (delta_month_units / month_units_prev * 100) if month_units_prev > 0 else 0
pct_month_total = (delta_month_total / month_total_prev * 100) if month_total_prev > 0 else 0
pct_ticket = (delta_ticket / month_ticket_prev * 100) if month_ticket_prev > 0 else 0

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric(
    f"Unidades {period_label}",
    f"{month_units:,}",
    f"{delta_month_units:+,} ({pct_month_units:+.1f}%)" if month_units_prev else None,
)
col_m2.metric(
    f"Total COP {period_label}",
    format_currency(month_total, decimals=2),
    f"{format_currency(delta_month_total, decimals=2)} ({pct_month_total:+.1f}%)" if month_total_prev else None,
)
col_m3.metric(
    f"Ticket promedio {period_label}",
    format_currency(month_ticket, decimals=2),
    f"{format_currency(delta_ticket, decimals=2)} ({pct_ticket:+.1f}%)" if month_ticket_prev else None,
)

if not df_month_prev.empty:
    compare_df = pd.DataFrame(
        {
            "Año": [selected_year, selected_year - 1],
            "Unidades": [int(month_units), int(month_units_prev)],
            "Total COP": [month_total, month_total_prev],
        }
    )
    compare_df["Año"] = compare_df["Año"].astype(str)
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        fig_month_units = px.bar(
            compare_df,
            x="Año",
            y="Unidades",
            text_auto=".0f",
            title="Unidades por mes (actual vs año anterior)",
            color="Año",
            color_continuous_scale="Blues",
        )
        fig_month_units.update_layout(xaxis_tickformat=".0f", yaxis_tickformat=".0f")
        st.plotly_chart(fig_month_units, use_container_width=True)
    with col_chart2:
        fig_month_total = px.bar(
            compare_df,
            x="Año",
            y="Total COP",
            text_auto=",.0f",
            title="Total COP por mes (actual vs año anterior)",
            color="Año",
            color_continuous_scale="Greens",
        )
        fig_month_total.update_layout(yaxis_tickformat=",")
        st.plotly_chart(fig_month_total, use_container_width=True)
else:
    st.info("No hay datos del mismo mes para el año anterior con los filtros actuales.")

st.markdown("---")

df_analysis = df_ytd_current.copy()

# Comparación configurable
dimension_options = []
if "ANIO" in df_analysis.columns:
    dimension_options.append(("Año", "ANIO"))
if "MES_NOMBRE" in df_analysis.columns and df_analysis["MES_NOMBRE"].notna().any():
    dimension_options.append(("Mes", "MES_NOMBRE"))
if "PERIODO_LABEL" in df_analysis.columns and df_analysis["PERIODO_LABEL"].notna().any():
    dimension_options.append(("Periodo (YYYY-MM)", "PERIODO_LABEL"))
if "CENTRO_COSTO" in df_analysis.columns:
    dimension_options.append(("Centro de costo", "CENTRO_COSTO"))
if "VENDEDOR" in df_analysis.columns:
    dimension_options.append(("Vendedor", "VENDEDOR"))
if "MODALIDAD_VENTA" in df_analysis.columns:
    dimension_options.append(("Modalidad de venta", "MODALIDAD_VENTA"))
if "BODEGA" in df_analysis.columns:
    dimension_options.append(("Bodega", "BODEGA"))
if "PRODUCTO" in df_analysis.columns:
    dimension_options.append(("Producto", "PRODUCTO"))
if "TIPO_PRODUCTO" in df_analysis.columns:
    dimension_options.append(("Tipo de producto", "TIPO_PRODUCTO"))

if not dimension_options:
    st.error("No hay columnas disponibles para agrupar y comparar.")
    st.stop()

dimension_labels = [label for label, _ in dimension_options]
selected_dimension_label = st.selectbox("Agrupar por", dimension_labels, index=0)
group_col = dict(dimension_options)[selected_dimension_label]

# Si se agrupa por año, construir resumen con ambos años
if group_col == "ANIO" and not df_ytd_prev.empty:
    # Combinar datos de ambos años para el resumen
    df_both_years = pd.concat([df_analysis, df_ytd_prev], ignore_index=True)
    summary_current = build_summary(df_both_years, group_col)
    summary_prev = None  # Ya está incluido en summary_current
    include_prev_month = True
else:
    summary_current = build_summary(df_analysis, group_col)
    # Incluir año anterior cuando se agrupa por mes/período
    should_include_prev = (
        not df_ytd_prev.empty 
        and group_col in {"MES_NOMBRE", "PERIODO_LABEL"}
    )
    summary_prev = (
        build_summary(df_ytd_prev, group_col)
        if should_include_prev
        else None
    )
    include_prev_month = summary_prev is not None and not summary_prev.empty

st.subheader("📦 Comparativo de unidades")
top_units = summary_current.sort_values("Unidades", ascending=False).head(20)

if include_prev_month:
    if group_col == "ANIO":
        # Cuando se agrupa por año, summary_current ya tiene ambos años
        chart_units_df = summary_current.copy()
        # Asegurar que el año sea entero
        chart_units_df[group_col] = chart_units_df[group_col].astype(int)
        chart_units_df["Serie"] = chart_units_df[group_col].astype(str)
        # Asegurar que las unidades sean enteras
        chart_units_df["Unidades"] = chart_units_df["Unidades"].astype(int)
    else:
        # Para otros agrupamientos, combinar ambos resúmenes
        chart_units_df = pd.concat(
            [
                summary_current.assign(Serie=str(selected_year)),
                summary_prev.assign(Serie=str(selected_year - 1)),
            ],
            ignore_index=True,
        )
        # Asegurar que las unidades sean enteras
        chart_units_df["Unidades"] = chart_units_df["Unidades"].astype(int)
    fig_units = px.bar(
        chart_units_df,
        x="Unidades",
        y=group_col,
        orientation="h",
        text_auto=".0f",
        title=f"Top {len(top_units)} por unidades ({selected_dimension_label})",
        color="Serie",
        barmode="group",
    )
    if group_col == "ANIO":
        fig_units.update_layout(
            yaxis_title=selected_dimension_label,
            xaxis_title="Unidades",
            yaxis=dict(type="category", tickmode="linear", dtick=1)
        )
    else:
        fig_units.update_layout(yaxis_title=selected_dimension_label, xaxis_title="Unidades")
else:
    # Asegurar que las unidades sean enteras
    top_units["Unidades"] = top_units["Unidades"].astype(int)
    fig_units = px.bar(
        top_units,
        x="Unidades",
        y=group_col,
        orientation="h",
        text_auto=".0f",
        title=f"Top {len(top_units)} por unidades ({selected_dimension_label})",
        color="Unidades",
        color_continuous_scale="Blues",
    )
    fig_units.update_layout(yaxis_title=selected_dimension_label, xaxis_title="Unidades")

# Asegurar que el eje X siempre muestre enteros
fig_units.update_layout(xaxis_tickformat=".0f")
st.plotly_chart(fig_units, use_container_width=True)

# Mostrar tabla o métricas según el agrupamiento
if group_col == "ANIO" and include_prev_month:
    # Cuando se agrupa por año, mostrar métricas con porcentajes
    summary_current_year = summary_current[summary_current[group_col] == selected_year].copy()
    summary_prev_year = summary_current[summary_current[group_col] == selected_year - 1].copy()
    
    units_current = summary_current_year["Unidades"].iloc[0] if not summary_current_year.empty else 0
    units_prev = summary_prev_year["Unidades"].iloc[0] if not summary_prev_year.empty else 0
    cop_current = summary_current_year["Total_COP"].iloc[0] if not summary_current_year.empty else 0
    cop_prev = summary_prev_year["Total_COP"].iloc[0] if not summary_prev_year.empty else 0
    
    delta_units_year = units_current - units_prev
    delta_cop_year = cop_current - cop_prev
    pct_units_year = (delta_units_year / units_prev * 100) if units_prev > 0 else 0
    pct_cop_year = (delta_cop_year / cop_prev * 100) if cop_prev > 0 else 0
    
    col_year1, col_year2 = st.columns(2)
    col_year1.metric(
        f"Unidades {selected_year}",
        f"{int(units_current):,}",
        f"{delta_units_year:+,} ({pct_units_year:+.1f}%)" if units_prev > 0 else None,
    )
    col_year2.metric(
        f"Total COP {selected_year}",
        format_currency(cop_current, decimals=2),
        f"{format_currency(delta_cop_year, decimals=2)} ({pct_cop_year:+.1f}%)" if cop_prev > 0 else None,
    )
else:
    # Para otros agrupamientos, mostrar tabla
    summary_display = summary_current.rename(
        columns={
            "ANIO": "Año",
            "Unidades": "Unidades",
            "Total_COP": "Total COP",
        }
    ).copy()
    if "Total COP" in summary_display.columns:
        summary_display["Total COP"] = summary_display["Total COP"].apply(lambda x: format_currency(x, decimals=2))
    
    st.dataframe(summary_display, use_container_width=True)

st.markdown("---")
st.subheader("💵 Comparativo por valor (COP)")
top_money = summary_current.sort_values("Total_COP", ascending=False).head(20)

if include_prev_month:
    if group_col == "ANIO":
        # Cuando se agrupa por año, summary_current ya tiene ambos años
        chart_money_df = summary_current.copy()
        # Asegurar que el año sea entero
        chart_money_df[group_col] = chart_money_df[group_col].astype(int)
        chart_money_df["Serie"] = chart_money_df[group_col].astype(str)
    else:
        # Para otros agrupamientos, combinar ambos resúmenes
        chart_money_df = pd.concat(
            [
                summary_current.assign(Serie=str(selected_year)),
                summary_prev.assign(Serie=str(selected_year - 1)),
            ],
            ignore_index=True,
        )
    fig_money = px.bar(
        chart_money_df,
        x="Total_COP",
        y=group_col,
        orientation="h",
        text_auto=",.0f",
        title=f"Top {len(top_money)} por dinero ({selected_dimension_label})",
        color="Serie",
        barmode="group",
    )
    if group_col == "ANIO":
        fig_money.update_layout(
            yaxis_title=selected_dimension_label,
            xaxis_title="Total COP",
            yaxis=dict(type="category", tickmode="linear", dtick=1)
        )
    else:
        fig_money.update_layout(yaxis_title=selected_dimension_label, xaxis_title="Total COP")
else:
    fig_money = px.bar(
        top_money,
        x="Total_COP",
        y=group_col,
        orientation="h",
        text_auto=",.0f",
        title=f"Top {len(top_money)} por dinero ({selected_dimension_label})",
        color="Total_COP",
        color_continuous_scale="Greens",
    )
    fig_money.update_layout(yaxis_title=selected_dimension_label, xaxis_title="Total COP")
st.plotly_chart(fig_money, use_container_width=True)

st.markdown("---")
st.subheader("🏢 Centros de costo destacados")

if "CENTRO_COSTO" in df_analysis.columns:
    def summarize_centros(df_source: pd.DataFrame) -> pd.DataFrame:
        return (
            df_source.groupby("CENTRO_COSTO")
            .agg(
                Unidades=("TOTALFAC", lambda x: len(x) - (x < 0).sum() * 2),
                Total_COP=("TOTALFAC", "sum"),
            )
            .reset_index()
        )

    centro_summary_current = summarize_centros(df_analysis)
    has_prev_centros = not df_ytd_prev.empty and "CENTRO_COSTO" in df_ytd_prev.columns
    centro_summary_prev = summarize_centros(df_ytd_prev) if has_prev_centros else pd.DataFrame(columns=centro_summary_current.columns)

    top_curr_units = centro_summary_current.sort_values("Unidades", ascending=False).head(10)
    top_curr_money = centro_summary_current.sort_values("Total_COP", ascending=False).head(10)

    top_curr_units_fmt = top_curr_units.copy()
    top_curr_units_fmt["Total_COP"] = top_curr_units_fmt["Total_COP"].apply(lambda x: format_currency(x, decimals=2))
    top_curr_money_fmt = top_curr_money.copy()
    top_curr_money_fmt["Total_COP"] = top_curr_money_fmt["Total_COP"].apply(lambda x: format_currency(x, decimals=2))

    if has_prev_centros:
        col_units_curr, col_units_prev = st.columns(2)
    else:
        col_units_curr = st.container()
        col_units_prev = None

    with col_units_curr:
        st.caption(f"Top centros por unidades {selected_year}")
        st.dataframe(top_curr_units_fmt, use_container_width=True, hide_index=True)

    if has_prev_centros:
        top_prev_units = centro_summary_prev.sort_values("Unidades", ascending=False).head(10)
        top_prev_units_fmt = top_prev_units.copy()
        top_prev_units_fmt["Total_COP"] = top_prev_units_fmt["Total_COP"].apply(lambda x: format_currency(x, decimals=2))
        with col_units_prev:
            st.caption(f"Top centros por unidades {selected_year - 1}")
            st.dataframe(top_prev_units_fmt, use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos de centros de costo para el año anterior con los filtros actuales.")

    if has_prev_centros:
        col_money_curr, col_money_prev = st.columns(2)
    else:
        col_money_curr = st.container()
        col_money_prev = None

    with col_money_curr:
        st.caption(f"Top centros por dinero {selected_year}")
        st.dataframe(top_curr_money_fmt, use_container_width=True, hide_index=True)

    if has_prev_centros:
        top_prev_money = centro_summary_prev.sort_values("Total_COP", ascending=False).head(10)
        top_prev_money_fmt = top_prev_money.copy()
        top_prev_money_fmt["Total_COP"] = top_prev_money_fmt["Total_COP"].apply(lambda x: format_currency(x, decimals=2))
        with col_money_prev:
            st.caption(f"Top centros por dinero {selected_year - 1}")
            st.dataframe(top_prev_money_fmt, use_container_width=True, hide_index=True)
else:
    st.info("El archivo no incluye `Centro Costo`, por lo que no es posible ranquearlo.")

st.markdown("---")
st.subheader("📥 Descarga")

csv_bytes = df_analysis.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Descargar registros filtrados",
    data=csv_bytes,
    file_name="colocacion_fiable_filtrado.csv",
    mime="text/csv",
)

