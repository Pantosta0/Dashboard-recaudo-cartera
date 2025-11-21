# Dashboard de Recaudo, Cartera y Pipeline

Aplicación multipágina construida con Streamlit para analizar los frentes de recaudo, cartera y pipeline de créditos Fiable. Incluye métricas clave, visualizaciones interactivas, filtros avanzados y utilidades de descarga (CSV y PDF) para apoyar la toma de decisiones.

---

## Requisitos previos

- Python 3.10+ (probado con 3.13)
- pip actualizado (`py -m pip install --upgrade pip`)
- Acceso a los archivos de datos (`.xlsx` / `.xls`) con la nomenclatura descrita abajo

### Instalación rápida

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
```

> También puedes reutilizar un entorno existente; solo asegúrate de que `streamlit`, `pandas`, `plotly`, `pyarrow` y `fpdf` estén instalados con las versiones mínimas definidas en `requirements.txt`.

---

## Ejecutar el dashboard

```powershell
streamlit run app.py
```

La aplicación abrirá el navegador por defecto. Usa `Ctrl+C` en la terminal para detener el servidor. Si necesitas recargar datos cacheados, borra los `.parquet` dentro de `data/**/cache/` o ejecuta `streamlit run app.py --server.headless true` tras eliminar los cachés.

---

## Asistente Gemini (resúmenes y Q&A)

El dashboard puede describir los datos visibles en cada página y responder preguntas usando Google Gemini.

1. Instala las dependencias con `pip install -r requirements.txt` (incluye `google-generativeai`).
2. Configura la clave en `.streamlit/secrets.toml`:

   ```toml
   GEMINI_API_KEY = "tu_clave_de_google_ai_studio"
   # Opcional: GEMINI_MODEL = "gemini-1.5-flash"
   ```

3. Reinicia `streamlit run app.py`.
4. Abre el panel **🤖 Asistente Gemini** en cualquier página para pedir un resumen o hacer preguntas. Usa el modo **Simulación** dentro del panel para probar sin consumir tokens.

---

## Páginas y funcionalidades

- **Recaudo (`pages/1_Recaudo.py`):**
  - KPIs de montos (`POR_VENCER`, `30/60/90/+90 días`) y número de registros.
  - Filtros por fuente, nombre de fuente, zona, cliente y rangos de fechas.
  - Gráficos Plotly (distribución por días vencidos, fuentes, zonas y clientes).
  - Análisis temporal (vencimiento y recaudo), diagnóstico de datos, histograma/boxplot de días vencidos y tabla exportable (CSV).

- **Cartera (`pages/2_Cartera.py`):**
  - Clasificación automática por empresa según número de cuenta.
  - Tarjetas con KPIs, índices (Corriente, B, C, D, E) y desglose por bucket.
  - Resumen general con descarga en CSV y PDF generado con `FPDF`.
  - Comparaciones entre meses (tablas y gráficos) y alertas cuando faltan archivos.

- **Pipeline Fiable (`pages/3_Pipeline.py`):**
  - Lectura consolidada de `fiable-creditos-YYYY[-MM].xls`.
  - Filtros por estado, asesor, estación, producto y rango de fechas.
  - Comparación de periodos, métricas YTD, evolución mensual y tabla exportable.
  - Estados excluidos configurables para limpiar datos ruidosos.
- **Colocación Fiable (`pages/4_Colocacion_Fiable.py`):**
  - Lectura de Excel ubicados en `data/colocacion/raw/` con datos anuales/mensuales.
  - KPIs de unidades (recuento de registros) y dinero (`TotalFac`) con ticket promedio.
  - Comparaciones dinámicas por año, mes, centro de costo, vendedor, bodega, producto, etc.
  - Rankings por centro de costo (unidades/COP) y descarga del dataset filtrado.

Cada página aprovecha caching de Streamlit (`@st.cache_data`) y los auxiliares de `utils/data_loader.py` para acelerar recargas.

---

## Ingesta de datos

| Fuente    | Carpeta esperada                                  | Patrón de archivo             | Columnas clave |
|-----------|---------------------------------------------------|-------------------------------|----------------|
| Recaudo   | `data/recaudo/raw/`                               | `recaudo-YYYY-MM.xlsx`        | `FUENTE`, `NOMBRE_FUENTE`, `FECHA_VENCIMIENTO`, `FECHA_RECAUDO`, `DIAS_VENCIDOS`, `POR_VENCER`, `TREINTA_DIAS`, `SESENTA_DIAS`, `NOVENTA_DIAS`, `MAS_NOVENTA`, `CLIENTE`, `ZONA`, etc. |
| Cartera   | `data/cartera/raw/`                               | `cartera-YYYY-MM.xlsx`        | `Cuenta`, `Total Cuota`, `Por Vencer`, `Dias30/60/90/Mas90`, `Vencimiento`, `Razon Social`, `Placa`, `Dias Vencidos`. |
| Pipeline  | `data/pipeline/raw/`                              | `fiable-creditos-YYYY[-MM].xls` | `ESTADO_NORMALIZADO`, `FECHA`, `ASESOR`, `PRODUCTO`, `ESTACION`, `CLIENTE`, `MES_PERIODO`, `AÑO`, `MES`. |
| Colocación Fiable | `data/colocacion/raw/`                         | Libre (`*.xls`, `*.xlsx`) por año/mes | `Tipo`, `Nro Factura`, `Fecha Documento`, `AÑO`, `MES`, `Centro Costo`, `Vendedor`, `Modalidadventa`, `Bodega`, `TotalFac`, `Cantidad`, etc. |

Observaciones:

- Los archivos también se pueden colocar en la raíz del proyecto; el `data_loader` los detectará (mantén la nomenclatura).
- Al cargarse un Excel, se genera un `.parquet` en `data/**/cache/` con el mismo nombre. Se reutiliza siempre que el Excel no haya cambiado (mismo timestamp). Borra el archivo de caché si quieres forzar reprocesamiento.
- Para mantener el rendimiento, evita archivos gigantes y procura limpiar columnas innecesarias antes de subirlos.

### Validaciones automáticas

- Conversión de fechas (`FECHA_VENCIMIENTO`, `FECHA_RECAUDO`, `Vencimiento`, etc.).
- Limpieza de columnas numéricas (remoción de `$`, comas y espacios).
- Deduplicación opcional en cartera (Razón Social + Placa + Vencimiento).
- Alertas en Streamlit cuando faltan columnas o existen fechas inválidas.

---

## Estructura recomendada

```
Recaudo-streamlit-test/
├─ app.py
├─ pages/
│  ├─ 1_Recaudo.py
│  ├─ 2_Cartera.py
│  ├─ 3_Pipeline.py
│  └─ 4_Colocacion_Fiable.py
├─ utils/
│  └─ data_loader.py
├─ data/
│  ├─ cartera/{raw,cache}
│  ├─ recaudo/{raw,cache}
│  ├─ pipeline/{raw,cache}
│  └─ colocacion/{raw,cache}
├─ requirements.txt
└─ README.md
```

---

## Desarrollo y mantenimiento

- Usa una rama propia y describe los cambios en commits atómicos.
- Antes de abrir PR, valida que `streamlit run app.py` funciona con los datos de ejemplo.
- Si modificas `data_loader`, agrega notas aquí sobre nuevas columnas o reglas.
- Para depurar, puedes ejecutar `streamlit run pages/1_Recaudo.py --server.headless true` para cargar solo una página durante el desarrollo.

