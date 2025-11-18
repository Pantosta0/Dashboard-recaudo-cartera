# Dashboard de Recaudo

Dashboard interactivo en Streamlit para visualizar y analizar datos de recaudo.

## Características

- 📊 **KPIs principales**: Indicadores clave de recaudo
- 📈 **Visualizaciones interactivas**: Gráficos de distribución, análisis temporal y por cliente
- 🔍 **Filtros avanzados**: Por zona, cliente, fuente y rango de fechas
- 📋 **Tabla de datos**: Visualización y descarga de datos filtrados
- 📅 **Análisis temporal**: Tendencias por mes de vencimiento y recaudo
- 👥 **Análisis por cliente**: Top clientes y días vencidos promedio

## Instalación

1. Instala las dependencias:
```bash
py -m pip install -r requirements.txt
```

## Uso

Ejecuta el dashboard con:
```bash
streamlit run app.py
```

El dashboard se abrirá automáticamente en tu navegador.

## Estructura de Datos

El archivo Excel debe contener las siguientes columnas (en este orden):
- FUENTE
- NOMBRE_FUENTE
- FECHA_VENCIMIENTO
- FECHA_RECAUDO
- DIAS_VENCIDOS
- CLIENTE
- NOMBRE
- CUENTA
- FACTURA
- ZONA
- DOCUMENTO
- POR_VENCER
- TREINTA_DIAS
- SESENTA_DIAS
- NOVENTA_DIAS
- MAS_NOVENTA

