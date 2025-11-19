import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime
import os
import re
import locale

# Configurar locale para español (meses en español)
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
    except:
        pass  # Si no se puede configurar, usar inglés

# Configuración de directorios
DATA_DIR = Path("data")
CARTERA_RAW_DIR = DATA_DIR / "cartera" / "raw"
CARTERA_CACHE_DIR = DATA_DIR / "cartera" / "cache"
RECAUDO_RAW_DIR = DATA_DIR / "recaudo" / "raw"
RECAUDO_CACHE_DIR = DATA_DIR / "recaudo" / "cache"
PIPELINE_RAW_DIR = DATA_DIR / "pipeline" / "raw"
PIPELINE_CACHE_DIR = DATA_DIR / "pipeline" / "cache"

# Crear directorios si no existen
for dir_path in [CARTERA_RAW_DIR, CARTERA_CACHE_DIR, RECAUDO_RAW_DIR, RECAUDO_CACHE_DIR, PIPELINE_RAW_DIR, PIPELINE_CACHE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

def get_excel_files(directory, pattern="*.xlsx"):
    """Obtiene lista de archivos Excel en un directorio"""
    if not directory.exists():
        return []
    return sorted(directory.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)

def get_cache_path(raw_file, cache_dir):
    """Genera la ruta del archivo cacheado (Parquet)"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_name = raw_file.stem + ".parquet"
    return cache_dir / cache_name

def is_cache_valid(raw_file, cache_file):
    """Verifica si el caché es válido (más reciente que el archivo original)"""
    if not cache_file.exists():
        return False
    return cache_file.stat().st_mtime >= raw_file.stat().st_mtime

def load_excel_with_cache(excel_path, cache_dir, processing_func=None, **read_excel_kwargs):
    """
    Carga un archivo Excel usando caché Parquet si está disponible y es válido.
    
    Args:
        excel_path: Ruta al archivo Excel
        cache_dir: Directorio donde guardar el caché Parquet
        processing_func: Función opcional para procesar el DataFrame después de cargar
        **read_excel_kwargs: Argumentos adicionales para pd.read_excel
    
    Returns:
        DataFrame procesado
    """
    excel_path = Path(excel_path)
    cache_path = get_cache_path(excel_path, cache_dir)
    
    # Si el caché existe y es válido, cargar desde Parquet
    if is_cache_valid(excel_path, cache_path):
        try:
            df = pd.read_parquet(cache_path)
            # El caché ya contiene datos procesados, no aplicar processing_func nuevamente
            # para evitar procesamiento doble que podría corromper los datos
            return df
        except Exception as e:
            st.warning(f"Error al cargar caché, recargando desde Excel: {e}")
    
    # Cargar desde Excel
    try:
        df = pd.read_excel(excel_path, **read_excel_kwargs)
        
        # Aplicar función de procesamiento si existe
        if processing_func:
            df = processing_func(df)
        
        # Guardar en caché
        try:
            # Asegurar que las columnas de tipo object (strings) se mantengan como strings
            # Parquet puede tener problemas con columnas object que pandas intenta convertir
            df_for_cache = df.copy()
            for col in df_for_cache.columns:
                if df_for_cache[col].dtype == 'object':
                    # Convertir a string explícitamente, manteniendo NaN como NaN
                    # Usar convert_dtypes para preservar tipos pero asegurar que object sea string
                    df_for_cache[col] = df_for_cache[col].astype('string')  # StringDtype de pandas
            
            # Guardar en Parquet con pyarrow que maneja mejor los tipos de datos
            df_for_cache.to_parquet(
                cache_path, 
                index=False, 
                compression='snappy',
                engine='pyarrow'
            )
        except Exception as e:
            # Si falla con string dtype, intentar con conversión más simple
            try:
                df_for_cache = df.copy()
                for col in df_for_cache.columns:
                    if df_for_cache[col].dtype == 'object':
                        # Convertir a string, reemplazando NaN con string vacío
                        df_for_cache[col] = df_for_cache[col].fillna('').astype(str)
                
                df_for_cache.to_parquet(
                    cache_path, 
                    index=False, 
                    compression='snappy',
                    engine='pyarrow'
                )
            except Exception as e2:
                st.warning(f"No se pudo guardar el caché: {e2}")
        
        return df
    except Exception as e:
        st.error(f"Error al cargar el archivo Excel: {e}")
        return None

def parse_filename_date(filename):
    """
    Extrae año y mes del nombre de archivo con patrón: nombre-YYYY-MM.xlsx o nombre-YYYY-M.xlsx
    Retorna (año, mes) o None si no coincide
    """
    # Patrón: nombre-YYYY-MM.xlsx o nombre-YYYY-M.xlsx (acepta 1 o 2 dígitos para el mes)
    pattern = r'(\d{4})-(\d{1,2})'
    match = re.search(pattern, filename.stem)
    
    if match:
        año = int(match.group(1))
        mes = int(match.group(2))
        if 1 <= mes <= 12:
            return (año, mes)
    return None

def detect_cartera_files():
    """
    Detecta archivos de cartera disponibles.
    Busca archivos con patrón: cartera-YYYY-MM.xlsx
    Retorna lista de tuplas (mes_str, año, mes_num, archivo_path)
    """
    files = []
    meses_es = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    # Buscar en el directorio de cartera/raw
    if CARTERA_RAW_DIR.exists():
        pattern_files = get_excel_files(CARTERA_RAW_DIR, "cartera-*.xlsx")
        for file in pattern_files:
            date_info = parse_filename_date(file)
            if date_info:
                año, mes = date_info
                # Formatear mes en español
                mes_str = f"{meses_es[mes-1]} {año}"
                files.append((mes_str, año, mes, file))
    else:
        # Si el directorio no existe, intentar crearlo
        try:
            CARTERA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        except:
            pass
    
    # Buscar en el directorio raíz (compatibilidad hacia atrás)
    root_files = get_excel_files(Path("."), "cartera-*.xlsx")
    for file in root_files:
        date_info = parse_filename_date(file)
        if date_info:
            año, mes = date_info
            # Formatear mes en español (consistente con el resto)
            mes_str = f"{meses_es[mes-1]} {año}"
            # Evitar duplicados
            if not any(f[3] == file for f in files):
                files.append((mes_str, año, mes, file))
    
    return sorted(files, key=lambda x: (x[1], x[2]), reverse=True)

def detect_recaudo_files():
    """
    Detecta archivos de recaudo disponibles por mes.
    Busca archivos con patrón: recaudo-YYYY-MM.xlsx
    Retorna lista de tuplas (mes_str, año, mes_num, archivo_path)
    """
    files = []
    meses_es = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    # Buscar en el directorio de recaudo/raw
    pattern_files = get_excel_files(RECAUDO_RAW_DIR, "recaudo-*.xlsx")
    for file in pattern_files:
        date_info = parse_filename_date(file)
        if date_info:
            año, mes = date_info
            # Formatear mes en español
            mes_str = f"{meses_es[mes-1]} {año}"
            files.append((mes_str, año, mes, file))
    
    # Buscar en el directorio raíz (compatibilidad hacia atrás)
    root_files = get_excel_files(Path("."), "recaudo-*.xlsx")
    for file in root_files:
        date_info = parse_filename_date(file)
        if date_info:
            año, mes = date_info
            # Formatear mes en español (consistente con el resto)
            mes_str = f"{meses_es[mes-1]} {año}"
            # Evitar duplicados
            if not any(f[3] == file for f in files):
                files.append((mes_str, año, mes, file))
    
    return sorted(files, key=lambda x: (x[1], x[2]), reverse=True)


def detect_fiable_pipeline_files():
    """
    Detecta archivos de pipeline Fiable disponibles.
    Busca archivos con patrón: fiable-creditos-YYYY.xlsx o fiable-creditos-YYYY-MM.xlsx
    Retorna lista de tuplas (periodo_str, año, mes, archivo_path)
    """
    files = []
    meses_es = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    pattern_files = get_excel_files(PIPELINE_RAW_DIR, "fiable-creditos-*.xls")
    for file in pattern_files:
        match = re.search(r'(\d{4})(?:-(\d{1,2}))?', file.stem)
        if match:
            año = int(match.group(1))
            mes = int(match.group(2)) if match.group(2) else None
            if mes and 1 <= mes <= 12:
                periodo_str = f"{meses_es[mes-1]} {año}"
            else:
                periodo_str = f"Año {año}"
            files.append((periodo_str, año, mes, file))

    # Compatibilidad: buscar en raíz
    root_files = get_excel_files(Path("."), "fiable-creditos-*.xls")
    for file in root_files:
        match = re.search(r'(\d{4})(?:-(\d{1,2}))?', file.stem)
        if match:
            año = int(match.group(1))
            mes = int(match.group(2)) if match.group(2) else None
            if mes and 1 <= mes <= 12:
                periodo_str = f"{meses_es[mes-1]} {año}"
            else:
                periodo_str = f"Año {año}"
            if not any(existing[3] == file for existing in files):
                files.append((periodo_str, año, mes, file))

    return sorted(files, key=lambda x: (x[1], x[2] if x[2] is not None else 0), reverse=True)

# Funciones de procesamiento específicas
def process_cartera_data(df, deduplicate=True):
    """
    Procesa los datos de cartera después de cargar.
    
    Args:
        df: DataFrame con los datos de cartera
        deduplicate: Si True, elimina duplicados basados en Razón Social + Placa + Vencimiento
    """
    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip()
    
    # Convertir columnas numéricas
    numeric_columns = ['Por Vencer', 'Dias30', 'Dias60', 'Dias90', 'Dias Mas90', 'Total Cuota', 'Mora', 'Dias Vencidos']
    for col in numeric_columns:
        if col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                serie_limpia = df[col].astype(str).str.replace(',', '', regex=False).str.replace('$', '', regex=False).str.replace(' ', '', regex=False).str.strip()
                df[col] = pd.to_numeric(serie_limpia, errors='coerce').fillna(0)
    
    # Convertir fecha de vencimiento
    if 'Vencimiento' in df.columns:
        df['Vencimiento'] = pd.to_datetime(df['Vencimiento'], errors='coerce')
    
    # DEDUPLICACIÓN: Basada en Razón Social + Placa + Vencimiento
    if deduplicate:
        initial_count = len(df)
        
        # Buscar la columna de Razón Social (diferentes variaciones posibles)
        razon_social_col = None
        possible_razon_names = [
            'Razon Social', 'Razón Social', 'RazonSocial', 'RazónSocial',
            'Razon_Social', 'Razón_Social', 'Razon Social', 'Razón Social',
            'Nombre', 'Nombre Cliente', 'Cliente', 'Nombre Completo',
            'Razon', 'Razón', 'Social', 'Nombre de Cliente'
        ]
        
        for name in possible_razon_names:
            if name in df.columns:
                razon_social_col = name
                break
        
        # Buscar la columna de Placa (diferentes variaciones posibles)
        placa_col = None
        possible_placa_names = [
            'Placa', 'PLACA', 'placa', 'Placa Vehiculo', 'Placa Vehículo',
            'Placa Vehiculo', 'Placa del Vehiculo', 'Placa del Vehículo',
            'Numero Placa', 'Número Placa', 'Numero de Placa', 'Número de Placa'
        ]
        
        for name in possible_placa_names:
            if name in df.columns:
                placa_col = name
                break
        
        # Verificar que tenemos todas las columnas necesarias
        missing_cols = []
        if 'Vencimiento' not in df.columns:
            missing_cols.append('Vencimiento')
        if not razon_social_col:
            missing_cols.append('Razón Social')
        if not placa_col:
            missing_cols.append('Placa')
        
        if not missing_cols:
            # Todas las columnas están presentes
            key_columns = ['Vencimiento', razon_social_col, placa_col]
            
            # Normalizar columnas de texto para comparación (eliminar espacios extra, convertir a mayúsculas)
            df['_razon_social_normalized'] = df[razon_social_col].astype(str).str.strip().str.upper()
            df['_placa_normalized'] = df[placa_col].astype(str).str.strip().str.upper()
            
            # Crear clave única normalizada
            df['_unique_key'] = (
                df['Vencimiento'].astype(str) + '_' + 
                df['_razon_social_normalized'] + '_' +
                df['_placa_normalized']
            )
            
            # Contar duplicados antes
            duplicates_before = df.duplicated(subset=['_unique_key'], keep=False).sum()
            
            if duplicates_before > 0:
                # Si hay duplicados, mantener el último registro (más reciente)
                # Si hay una columna de fecha de actualización, usarla
                date_cols = [c for c in df.columns if any(x in c.lower() for x in ['fecha actualiz', 'date actualiz', 'corte', 'fecha corte', 'fecha modif'])]
                
                if date_cols:
                    # Ordenar por fecha de actualización descendente
                    df = df.sort_values(by=date_cols[0], ascending=False, na_position='last')
                
                # Eliminar duplicados manteniendo el primero (más reciente si hay fecha)
                df = df.drop_duplicates(subset=['_unique_key'], keep='first')
                
                # Limpiar columnas temporales
                df = df.drop(columns=['_razon_social_normalized', '_placa_normalized', '_unique_key'], errors='ignore')
                
                duplicates_removed = initial_count - len(df)
                if duplicates_removed > 0:
                    # Solo mostrar si hay muchos duplicados (más del 1% del total)
                    if duplicates_removed > initial_count * 0.01:
                        st.info(f"🔍 **Deduplicación aplicada**: Se encontraron {duplicates_before} registros duplicados (misma Razón Social + Placa + Fecha de Vencimiento). Se mantuvieron {len(df)} registros únicos.")
            else:
                # Limpiar columnas temporales si no hubo duplicados
                df = df.drop(columns=['_razon_social_normalized', '_placa_normalized', '_unique_key'], errors='ignore')
        else:
            # Faltan columnas necesarias
            missing_str = ', '.join(missing_cols)
            st.warning(f"⚠️ **Advertencia**: No se pueden aplicar deduplicación. Faltan las siguientes columnas: {missing_str}")
            
            # Intentar deduplicación parcial si tenemos al menos Vencimiento
            if 'Vencimiento' in df.columns:
                duplicates_before = df.duplicated(subset=['Vencimiento'], keep=False).sum()
                if duplicates_before > 0:
                    df = df.drop_duplicates(subset=['Vencimiento'], keep='last')
                    st.info(f"🔍 **Deduplicación parcial**: Se eliminaron duplicados basados solo en Fecha de Vencimiento (faltan Razón Social y/o Placa).")
    
    return df

def process_recaudo_data(df):
    """Procesa los datos de recaudo después de cargar"""
    # Convertir columnas de fecha
    date_columns = ['FECHA_VENCIMIENTO', 'FECHA_RECAUDO']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Convertir columnas numéricas
    numeric_columns = ['POR_VENCER', 'TREINTA_DIAS', 'SESENTA_DIAS', 'NOVENTA_DIAS', 'MAS_NOVENTA', 'DIAS_VENCIDOS']
    for col in numeric_columns:
        if col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                serie_limpia = df[col].astype(str).str.replace(',', '', regex=False).str.replace('$', '', regex=False).str.replace(' ', '', regex=False).str.strip()
                df[col] = pd.to_numeric(serie_limpia, errors='coerce').astype('float64')
    
    return df


def process_fiable_pipeline_data(df):
    """
    Procesa los datos del pipeline Fiable para estandarizar columnas y tipos.
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()

    rename_map = {
        'estado': 'ESTADO',
        'fecha': 'FECHA',
        'asesor': 'ASESOR',
        'consecutivo': 'CONSECUTIVO',
        'identificacion': 'IDENTIFICACION',
        'cliente': 'CLIENTE',
        'estacion': 'ESTACION',
        'fechanalisis': 'FECHA_ANALISIS',
        'producto': 'PRODUCTO',
    }
    df = df.rename(columns=rename_map)

    required_cols = ['ESTADO', 'FECHA']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.warning(f"Faltan columnas requeridas en Fiable: {', '.join(missing_cols)}")
        for col in missing_cols:
            df[col] = None

    # Convertir fechas
    for fecha_col in ['FECHA', 'FECHA_ANALISIS']:
        if fecha_col in df.columns:
            df[fecha_col] = pd.to_datetime(df[fecha_col], errors='coerce')

    # Normalizar textos
    text_cols = ['ASESOR', 'CONSECUTIVO', 'IDENTIFICACION', 'CLIENTE', 'ESTACION', 'PRODUCTO', 'ESTADO']
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    estados_referencia = {
        'creado': 'CREADO',
        'aprobado': 'APROBADO',
        'en analisis': 'EN ANALISIS',
        'en análisis': 'EN ANALISIS',
        'excepcionado': 'EXCEPCIONADO',
        'legalizado': 'LEGALIZADO',
        'pre-legalizado': 'PRE-LEGALIZADO',
        'pre legalizado': 'PRE-LEGALIZADO',
        'rechazado': 'RECHAZADO',
        'reproceso': 'REPROCESO',
        'solicitado': 'SOLICITADO',
    }

    if 'ESTADO' in df.columns:
        estados_limpios = (
            df['ESTADO']
            .str.lower()
            .str.replace('á', 'a', regex=False)
            .str.replace('é', 'e', regex=False)
            .str.replace('í', 'i', regex=False)
            .str.replace('ó', 'o', regex=False)
            .str.replace('ú', 'u', regex=False)
        )
        df['ESTADO_NORMALIZADO'] = estados_limpios.map(estados_referencia).fillna(df['ESTADO'].str.upper())
    else:
        df['ESTADO_NORMALIZADO'] = 'SIN ESTADO'

    if 'FECHA' in df.columns:
        df['AÑO'] = df['FECHA'].dt.year
        df['MES'] = df['FECHA'].dt.month
        df['MES_PERIODO'] = df['FECHA'].dt.to_period('M')
    else:
        df['AÑO'] = None
        df['MES'] = None
        df['MES_PERIODO'] = None

    df['MES_LABEL'] = df['FECHA'].dt.strftime('%B %Y') if 'FECHA' in df.columns else None

    return df


def load_all_fiable_pipeline():
    """
    Carga y combina todos los archivos de pipeline Fiable disponibles.
    """
    files = detect_fiable_pipeline_files()
    if not files:
        return None

    dataframes = []
    for periodo_str, año, mes, file_path in files:
        df = load_excel_with_cache(
            file_path,
            PIPELINE_CACHE_DIR,
            processing_func=process_fiable_pipeline_data
        )
        if df is not None and not df.empty:
            df = df.copy()
            df['ARCHIVO_ORIGEN'] = file_path.name
            df['PERIODO_ARCHIVO'] = periodo_str
            dataframes.append(df)

    if not dataframes:
        return None

    return pd.concat(dataframes, ignore_index=True)


def load_cartera_for_comparison(año1, mes1, año2, mes2):
    """
    Carga dos períodos de cartera para comparación.
    Retorna (df1, df2, periodo1_str, periodo2_str)
    """
    available_files = detect_cartera_files()
    
    # Buscar archivos
    file1 = None
    file2 = None
    
    for mes_str, año, mes, file_path in available_files:
        if año == año1 and mes == mes1:
            file1 = file_path
        if año == año2 and mes == mes2:
            file2 = file_path
    
    if file1 is None:
        st.error(f"No se encontró archivo para {datetime(año1, mes1, 1).strftime('%B %Y')}")
        return None, None, None, None
    if file2 is None:
        st.error(f"No se encontró archivo para {datetime(año2, mes2, 1).strftime('%B %Y')}")
        return None, None, None, None
    
    # Cargar ambos archivos (sin deduplicación para mantener totales como antes)
    df1 = load_excel_with_cache(
        file1, CARTERA_CACHE_DIR,
        processing_func=lambda df: process_cartera_data(df, deduplicate=False),
        header=7
    )
    
    df2 = load_excel_with_cache(
        file2, CARTERA_CACHE_DIR,
        processing_func=lambda df: process_cartera_data(df, deduplicate=False),
        header=7
    )
    
    periodo1_str = datetime(año1, mes1, 1).strftime('%B %Y')
    periodo2_str = datetime(año2, mes2, 1).strftime('%B %Y')
    
    return df1, df2, periodo1_str, periodo2_str


def compare_cartera_periods(df1, df2, periodo1_str, periodo2_str, clasificar_empresa_func=None):
    """
    Compara dos períodos de cartera y retorna métricas comparativas.
    
    Args:
        df1: DataFrame del primer período
        df2: DataFrame del segundo período
        periodo1_str: Nombre del primer período (ej: "Octubre 2024")
        periodo2_str: Nombre del segundo período (ej: "Noviembre 2024")
        clasificar_empresa_func: Función para clasificar empresas por cuenta (opcional)
    
    Returns:
        DataFrame con métricas comparativas
    """
    if df1 is None or df2 is None or df1.empty or df2.empty:
        return None
    
    # Agregar columna de empresa si no existe y tenemos la función
    if clasificar_empresa_func:
        if 'Cuenta' in df1.columns and 'Empresa' not in df1.columns:
            df1['Empresa'] = df1['Cuenta'].apply(clasificar_empresa_func)
        if 'Cuenta' in df2.columns and 'Empresa' not in df2.columns:
            df2['Empresa'] = df2['Cuenta'].apply(clasificar_empresa_func)
    
    # Calcular métricas por empresa para ambos períodos
    empresas = set()
    if 'Empresa' in df1.columns:
        empresas.update(df1['Empresa'].unique())
    if 'Empresa' in df2.columns:
        empresas.update(df2['Empresa'].unique())
    
    comparison_data = []
    
    for empresa in sorted(empresas):
        df1_emp = df1[df1['Empresa'] == empresa] if 'Empresa' in df1.columns else pd.DataFrame()
        df2_emp = df2[df2['Empresa'] == empresa] if 'Empresa' in df2.columns else pd.DataFrame()
        
        # Métricas período 1
        total1 = df1_emp['Total Cuota'].sum() if 'Total Cuota' in df1_emp.columns and not df1_emp.empty else 0
        por_vencer1 = df1_emp['Por Vencer'].sum() if 'Por Vencer' in df1_emp.columns and not df1_emp.empty else 0
        dias30_1 = df1_emp['Dias30'].sum() if 'Dias30' in df1_emp.columns and not df1_emp.empty else 0
        dias60_1 = df1_emp['Dias60'].sum() if 'Dias60' in df1_emp.columns and not df1_emp.empty else 0
        dias90_1 = df1_emp['Dias90'].sum() if 'Dias90' in df1_emp.columns and not df1_emp.empty else 0
        dias_mas90_1 = df1_emp['Dias Mas90'].sum() if 'Dias Mas90' in df1_emp.columns and not df1_emp.empty else 0
        
        # Métricas período 2
        total2 = df2_emp['Total Cuota'].sum() if 'Total Cuota' in df2_emp.columns and not df2_emp.empty else 0
        por_vencer2 = df2_emp['Por Vencer'].sum() if 'Por Vencer' in df2_emp.columns and not df2_emp.empty else 0
        dias30_2 = df2_emp['Dias30'].sum() if 'Dias30' in df2_emp.columns and not df2_emp.empty else 0
        dias60_2 = df2_emp['Dias60'].sum() if 'Dias60' in df2_emp.columns and not df2_emp.empty else 0
        dias90_2 = df2_emp['Dias90'].sum() if 'Dias90' in df2_emp.columns and not df2_emp.empty else 0
        dias_mas90_2 = df2_emp['Dias Mas90'].sum() if 'Dias Mas90' in df2_emp.columns and not df2_emp.empty else 0
        
        # Calcular variaciones
        var_total = total2 - total1
        var_porcentaje = (var_total / total1 * 100) if total1 > 0 else (100 if total2 > 0 else 0)
        
        # Calcular índices para ambos períodos
        indice_corriente1 = (por_vencer1 / total1 * 100) if total1 > 0 else 0
        indice_corriente2 = (por_vencer2 / total2 * 100) if total2 > 0 else 0
        indice_mora1 = ((dias30_1 + dias60_1 + dias90_1 + dias_mas90_1) / total1 * 100) if total1 > 0 else 0
        indice_mora2 = ((dias30_2 + dias60_2 + dias90_2 + dias_mas90_2) / total2 * 100) if total2 > 0 else 0
        
        comparison_data.append({
            'Empresa': empresa,
            f'Total {periodo1_str}': total1,
            f'Total {periodo2_str}': total2,
            'Variación Total': var_total,
            'Variación %': var_porcentaje,
            f'Índice Corriente {periodo1_str} (%)': indice_corriente1,
            f'Índice Corriente {periodo2_str} (%)': indice_corriente2,
            f'Índice Mora {periodo1_str} (%)': indice_mora1,
            f'Índice Mora {periodo2_str} (%)': indice_mora2,
            f'Por Vencer {periodo1_str}': por_vencer1,
            f'Por Vencer {periodo2_str}': por_vencer2,
            f'Días 30 {periodo1_str}': dias30_1,
            f'Días 30 {periodo2_str}': dias30_2,
            f'Días 60 {periodo1_str}': dias60_1,
            f'Días 60 {periodo2_str}': dias60_2,
            f'Días 90 {periodo1_str}': dias90_1,
            f'Días 90 {periodo2_str}': dias90_2,
            f'Días +90 {periodo1_str}': dias_mas90_1,
            f'Días +90 {periodo2_str}': dias_mas90_2,
        })
    
    return pd.DataFrame(comparison_data)

