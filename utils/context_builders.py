from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


def _coerce_numeric(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0.0)
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace(" ", "", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def _sum_columns(df: pd.DataFrame, columns: Iterable[str]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    if df is None:
        return totals
    for col in columns:
        if col in df.columns:
            totals[col] = float(_coerce_numeric(df[col]).sum())
    return totals


def _row_sum(df: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    if df is None:
        return pd.Series(dtype="float64")
    available = [c for c in columns if c in df.columns]
    if not available:
        return pd.Series(0.0, index=df.index)
    numeric_df = df[available].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return numeric_df.sum(axis=1)


def _top_categories(
    df: pd.DataFrame,
    column: str,
    values: Optional[pd.Series] = None,
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    if df is None or column not in df.columns:
        return []
    series = df[column].fillna("Sin dato").astype(str)
    if values is None:
        summary = series.value_counts().head(top_n)
        return [{"label": idx, "value": int(val)} for idx, val in summary.items()]
    grouped = (
        pd.DataFrame({"label": series, "value": values})
        .groupby("label")["value"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
    )
    return [{"label": idx, "value": float(val)} for idx, val in grouped.items()]


def build_recaudo_context(
    df: Optional[pd.DataFrame],
    *,
    period_label: Optional[str],
    filters: Dict[str, Any],
    kpis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    df = df if df is not None else pd.DataFrame()
    aging_cols = ["POR_VENCER", "TREINTA_DIAS", "SESENTA_DIAS", "NOVENTA_DIAS", "MAS_NOVENTA"]
    totals = kpis or _sum_columns(df, aging_cols)
    totals.setdefault("Total registros", int(len(df)))
    totals.setdefault("Total Recaudo", sum(totals.get(col, 0.0) for col in aging_cols))
    value_series = _row_sum(df, aging_cols)

    fecha_min = (
        df["FECHA_RECAUDO"].min().date().isoformat()
        if "FECHA_RECAUDO" in df.columns and df["FECHA_RECAUDO"].notna().any()
        else None
    )
    fecha_max = (
        df["FECHA_RECAUDO"].max().date().isoformat()
        if "FECHA_RECAUDO" in df.columns and df["FECHA_RECAUDO"].notna().any()
        else None
    )

    return {
        "page": "Recaudo",
        "period": period_label,
        "records": int(len(df)),
        "filters": filters,
        "metrics": totals,
        "top_segments": {
            "fuentes": _top_categories(df, "FUENTE", value_series),
            "zonas": _top_categories(df, "ZONA", value_series),
            "clientes": _top_categories(df, "CLIENTE", value_series),
        },
        "date_range": {"min": fecha_min, "max": fecha_max},
    }


def build_cartera_context(
    df: Optional[pd.DataFrame],
    *,
    period_label: Optional[str],
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    df = df if df is not None else pd.DataFrame()
    columns = ["Total Cuota", "Por Vencer", "Dias30", "Dias60", "Dias90", "Dias Mas90"]
    totals = _sum_columns(df, columns)
    total_cuota = totals.get("Total Cuota", sum(totals.values()) or 1.0)

    indices = {
        "Corriente": (totals.get("Por Vencer", 0.0) / total_cuota) * 100 if total_cuota else 0,
        "B (30)": (totals.get("Dias30", 0.0) / total_cuota) * 100 if total_cuota else 0,
        "C (60)": (totals.get("Dias60", 0.0) / total_cuota) * 100 if total_cuota else 0,
        "D (90)": (totals.get("Dias90", 0.0) / total_cuota) * 100 if total_cuota else 0,
        "E (+90)": (totals.get("Dias Mas90", 0.0) / total_cuota) * 100 if total_cuota else 0,
    }

    value_series = _row_sum(df, columns)

    razon_col = next((c for c in ["Razon Social", "Razón Social", "Cliente", "Nombre"] if c in df.columns), None)

    return {
        "page": "Cartera",
        "period": period_label,
        "records": int(len(df)),
        "filters": filters,
        "metrics": totals,
        "indices": indices,
        "top_segments": {
            "empresa": _top_categories(df, "Empresa", value_series),
            "cliente": _top_categories(df, razon_col, value_series) if razon_col else [],
        },
    }


def build_pipeline_context(
    df_filtered: pd.DataFrame,
    *,
    period_label: str,
    comparison_label: Optional[str],
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    df = df_filtered if df_filtered is not None else pd.DataFrame()
    state_col = "ESTADO_NORMALIZADO"
    state_counts = (
        df[state_col].value_counts().to_dict()
        if state_col in df.columns
        else {}
    )

    trend = []
    if "MES_PERIODO" in df.columns:
        monthly = (
            df.groupby("MES_PERIODO")
            .size()
            .sort_index(ascending=False)
            .head(6)
            .reset_index(name="registros")
        )
        trend = [
            {"periodo": str(row["MES_PERIODO"]), "registros": int(row["registros"])}
            for _, row in monthly.iterrows()
        ]

    return {
        "page": "Pipeline Fiable",
        "period": period_label,
        "comparison": comparison_label,
        "records": int(len(df)),
        "filters": filters,
        "metrics": {"conteo_por_estado": state_counts},
        "top_segments": {
            "asesores": _top_categories(df, "ASESOR"),
            "productos": _top_categories(df, "PRODUCTO"),
            "estaciones": _top_categories(df, "ESTACION"),
        },
        "trend": trend,
    }


def build_colocacion_context(
    df_ytd: pd.DataFrame,
    *,
    df_ytd_prev: Optional[pd.DataFrame],
    period_label: str,
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    df = df_ytd if df_ytd is not None else pd.DataFrame()
    prev = df_ytd_prev if df_ytd_prev is not None else pd.DataFrame()

    totalfac_current = _coerce_numeric(df["TOTALFAC"]) if "TOTALFAC" in df.columns else pd.Series(dtype=float)
    totalfac_prev = _coerce_numeric(prev["TOTALFAC"]) if "TOTALFAC" in prev.columns else pd.Series(dtype=float)

    unidades = len(df) - (totalfac_current < 0).sum() * 2 if not totalfac_current.empty else len(df)
    monto = float(totalfac_current.sum()) if not totalfac_current.empty else 0.0
    unidades_prev = len(prev) - (totalfac_prev < 0).sum() * 2 if not totalfac_prev.empty else len(prev)
    monto_prev = float(totalfac_prev.sum()) if not totalfac_prev.empty else 0.0

    return {
        "page": "Colocación Fiable",
        "period": period_label,
        "records": unidades,
        "filters": filters,
        "metrics": {
            "unidades": unidades,
            "total_cop": monto,
            "ticket_promedio": (monto / unidades) if unidades else 0.0,
            "variacion_unidades": unidades - unidades_prev,
            "variacion_total_cop": monto - monto_prev,
        },
        "top_segments": {
            "centros_costo": _top_categories(df, "CENTRO_COSTO"),
            "vendedores": _top_categories(df, "VENDEDOR", _coerce_numeric(df["TOTALFAC"]) if "TOTALFAC" in df.columns else None),
            "modalidad": _top_categories(df, "MODALIDAD_VENTA"),
            "bodega": _top_categories(df, "BODEGA"),
        },
    }


def build_cartera_fiable_context(
    *,
    df_financiero: Optional[pd.DataFrame],
    df_proyectadas: Optional[pd.DataFrame],
    df_colocada: Optional[pd.DataFrame],
) -> Dict[str, Any]:
    financiero = df_financiero if df_financiero is not None else pd.DataFrame()
    proyectadas = df_proyectadas if df_proyectadas is not None else pd.DataFrame()
    colocada = df_colocada if df_colocada is not None else pd.DataFrame()

    metrics = {
        "capital_total": float(_coerce_numeric(financiero.get("Capital", pd.Series(dtype=float))).sum()) if not financiero.empty else 0.0,
        "cuota_total": float(_coerce_numeric(financiero.get("Cuota", pd.Series(dtype=float))).sum()) if not financiero.empty else 0.0,
        "interes_total": float(_coerce_numeric(financiero.get("Interes", pd.Series(dtype=float))).sum()) if not financiero.empty else 0.0,
        "fianza_total": float(_coerce_numeric(financiero.get("Fianza", pd.Series(dtype=float))).sum()) if not financiero.empty else 0.0,
        "proyectadas_total": float(_coerce_numeric(proyectadas.get("Total", pd.Series(dtype=float))).sum()) if not proyectadas.empty else 0.0,
        "colocada_valor_cuota": float(_coerce_numeric(colocada.get("ValorCuota", pd.Series(dtype=float))).sum()) if not colocada.empty else 0.0,
        "colocada_saldo_capital": float(_coerce_numeric(colocada.get("SaldoCapital", pd.Series(dtype=float))).sum()) if not colocada.empty else 0.0,
        "colocada_creditos": int(colocada["NumeroFactura"].nunique()) if "NumeroFactura" in colocada.columns else 0,
    }

    edad_col = "EDADES"
    aging = []
    if edad_col in financiero.columns:
        grouped = (
            financiero.groupby(edad_col)
            .agg({"Capital": "sum"})
            .reset_index()
            .sort_values("Capital", ascending=False)
        )
        aging = [
            {"edad": row[edad_col], "capital": float(row["Capital"])}
            for _, row in grouped.head(6).iterrows()
        ]

    return {
        "page": "Informe Cartera FIABLE",
        "metrics": metrics,
        "aging_breakdown": aging,
        "colocada_top_productos": _top_categories(colocada, "Producto", _coerce_numeric(colocada["ValorCuota"]) if "ValorCuota" in colocada.columns else None),
    }


__all__ = [
    "build_recaudo_context",
    "build_cartera_context",
    "build_pipeline_context",
    "build_colocacion_context",
    "build_cartera_fiable_context",
]


