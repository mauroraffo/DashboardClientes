import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import numpy as np
import io
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode

import streamlit as st

# 1. LISTA DE CONTRASEÑAS (Directo en el código)
# Puedes poner todas las que quieras aquí
CLAVES_VALIDAS = ["XE07089"]

# 2. INTERFAZ DE LOGIN
password = st.sidebar.text_input("Ingresa la contraseña:", type="password")

# 3. LÓGICA DE BLOQUEO
if password not in CLAVES_VALIDAS:
    st.error("🔒 El acceso está bloqueado. Ingresa una contraseña válida en la barra lateral.")
    st.stop()  # <--- ESTO ES LA CLAVE: Detiene la ejecución aquí si la clave está mal.

# --- 4. TU CÓDIGO DE LA APP VA A PARTIR DE AQUÍ ---
st.success(f"¡Bienvenido! Accediste con la clave: {password}")

st.title("Mi Dashboard de Ventas")
# Aquí pones tus gráficos, pandas, métricas, etc.
st.write("Si estás leyendo esto, es que pusiste la contraseña correcta.")



# --------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA
# --------------------------------------------------------------------------


st.set_page_config(page_title="Dashboard Clientes", layout="wide", page_icon="🌍")

st.title("🌍 Inteligencia de Clientes: Sell Out & Zonas")
st.markdown("---")

# Rutas Dinámicas
CARPETA_ACTUAL = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# 2. FUNCIONES DE CARGA DE DATOS
# --------------------------------------------------------------------------
@st.cache_data
def cargar_sell_out_neuma():
    """Carga el Sell Out buscando encabezados y forzando la columna CAI."""
    ruta_folder = os.path.join(CARPETA_ACTUAL, "Actualizar archivos", "Neuma Stock - Sell Out")
    archivo_encontrado = None
    
    # 1. Buscar el archivo
    if os.path.exists(ruta_folder):
        for f in os.listdir(ruta_folder):
            if ("Sell Out" in f or "SO" in f or f.endswith(".xlsx") or f.endswith(".csv")) and not f.startswith("~$"):
                archivo_encontrado = os.path.join(ruta_folder, f)
                break
    
    if archivo_encontrado:
        try:
            es_csv = archivo_encontrado.lower().endswith(".csv")
            
            # Función "Cazador de Encabezados"
            def leer_con_header_dinamico(path, is_csv):
                if is_csv:
                    df_raw = pd.read_csv(path, header=None, nrows=15)
                else:
                    xl = pd.ExcelFile(path)
                    hoja = "Sell Out" if "Sell Out" in xl.sheet_names else xl.sheet_names[0]
                    df_raw = pd.read_excel(path, sheet_name=hoja, header=None, nrows=15)

                fila_header = 0
                for i, row in df_raw.iterrows():
                    fila_texto = row.astype(str).str.upper().tolist()
                    if "CAI" in fila_texto or "FECHA" in fila_texto or "CLIENTE" in fila_texto or "CANTIDAD" in fila_texto:
                        fila_header = i
                        break
                
                if is_csv: return pd.read_csv(path, header=fila_header)
                else: return pd.read_excel(path, sheet_name=hoja, header=fila_header)

            df = leer_con_header_dinamico(archivo_encontrado, es_csv)
            
            # 2. Limpieza de columnas
            df.columns = [str(c).upper().strip() for c in df.columns]
            
            correcciones = {
                'ANO': 'AÑO', 'YEAR': 'AÑO', 'MONTH': 'MES', 'DATE': 'FECHA',
                'NOMBRE CLIENTE': 'CLIENTE', 'CUSTOMER': 'CLIENTE',
                'CODIGO': 'CAI', 'MATERIAL': 'CAI', 'ARTICULO': 'CAI' 
            }
            renames_final = {}
            for k, v in correcciones.items():
                if k in df.columns and v not in df.columns:
                    renames_final[k] = v
                elif k in df.columns and v in df.columns:
                    continue 
            
            if renames_final:
                df.rename(columns=renames_final, inplace=True)

            # 3. Validaciones finales
            if 'CLIENTE' in df.columns: 
                df['CLIENTE'] = df['CLIENTE'].astype(str).str.strip().str.upper().apply(lambda x: x[:-1] if x.endswith('.') else x)
            
            if 'FECHA' in df.columns:
                df['FECHA_DT'] = pd.to_datetime(df['FECHA'], errors='coerce')
            elif 'AÑO' in df.columns and 'MES' in df.columns:
                df['AÑO'] = pd.to_numeric(df['AÑO'], errors='coerce').fillna(0).astype(int)
                df['MES'] = pd.to_numeric(df['MES'], errors='coerce').fillna(1).astype(int)
                df['FECHA_DT'] = pd.to_datetime(df[['AÑO', 'MES']].assign(DAY=1), errors='coerce')
            
            if 'CAI' not in df.columns:
                candidato = next((c for c in df.columns if c.startswith("COD") or c.startswith("MAT")), None)
                if candidato:
                    df.rename(columns={candidato: 'CAI'}, inplace=True)
                else:
                    st.error(f"❌ No se detectó la columna CAI. Columnas leídas: {list(df.columns)}")
                    st.stop()

            return df

        except Exception as e:
            st.error(f"Error procesando archivo: {e}")
            return None
            
    st.warning("⚠️ Carpeta vacía o sin archivos válidos.")
    return None

@st.cache_data
def cargar_maestro_zonas_seguro():
    """Carga el archivo de zonas y FILTRA columnas peligrosas."""
    posibles_rutas = [
        os.path.join(CARPETA_ACTUAL, "Actualizar archivos", "Sell Out Zonas.xlsx"),
        os.path.join(CARPETA_ACTUAL, "Sell Out Zonas.xlsx"),
        "Sell Out Zonas.xlsx"
    ]
    
    archivo_path = None
    for r in posibles_rutas:
        if os.path.exists(r):
            archivo_path = r
            break
    
    if archivo_path:
        try:
            xl = pd.ExcelFile(archivo_path)
            sheet = 'Sell Out' if 'Sell Out' in xl.sheet_names else xl.sheet_names[0]
            df_z = pd.read_excel(xl, sheet_name=sheet)
            df_z.columns = [str(c).strip().upper() for c in df_z.columns]
            
            if 'AM' in df_z.columns: df_z.rename(columns={'AM': 'ACCOUNT MANAGER'}, inplace=True)
            if 'ACOOUNT MANAGER' in df_z.columns: df_z.rename(columns={'ACOOUNT MANAGER': 'ACCOUNT MANAGER'}, inplace=True)
            
            # BLINDAJE: Solo columnas geográficas
            cols_permitidas = ['COD.CLIENTE', 'ACCOUNT MANAGER', 'DEPARTAMENTO', 'PROVINCIA', 'DISTRITO']
            cols_finales = [c for c in cols_permitidas if c in df_z.columns]
            df_z = df_z[cols_finales]
            
            if 'COD.CLIENTE' in df_z.columns:
                df_z = df_z.drop_duplicates('COD.CLIENTE')
                df_z['COD.CLIENTE'] = df_z['COD.CLIENTE'].astype(str).str.strip()
                return df_z
        except Exception as e:
            st.error(f"Error procesando Zonas: {e}")
    return None

@st.cache_data
def cargar_maestro_filtros():
    """Carga el catálogo para Segmentos, Marcas y Clasificación DR."""
    ruta = os.path.join(CARPETA_ACTUAL, "Actualizar archivos", "CAI historico 2.xlsx")
    if os.path.exists(ruta):
        try:
            df = pd.read_excel(ruta)
            df.columns = [c.upper().strip() for c in df.columns]
            
            # Normalización de nombres
            renames = {
                'SEGMENTO': 'SEGMENTO LB', 
                'MACRO MACHINE': 'MACRO_ MACHINE',
                # Aseguramos que la columna se llame CLASIFICACION DR (sin tilde o con tilde, unificamos)
                'CLASIFICACION DR': 'CLASIFICACIÓN DR' 
            }
            # Aplicar renames si existen las columnas origen
            df.rename(columns={k:v for k,v in renames.items() if k in df.columns}, inplace=True)
            
            col_cai = next((c for c in df.columns if "CAI" in c or "COD" in c), "CAI")
            df.rename(columns={col_cai: 'CAI'}, inplace=True)
            
            return df
        except: pass
    return None

# --------------------------------------------------------------------------
# 3. LOGICA PRINCIPAL DE CARGA Y CRUCE
# --------------------------------------------------------------------------
df_so_raw = cargar_sell_out_neuma()
df_zonas = cargar_maestro_zonas_seguro()
df_maestro = cargar_maestro_filtros()

if df_so_raw is None:
    st.error("❌ No se encontró el archivo de Sell Out.")
    st.stop()

# 1. Unificar Zonas
df_unificado = df_so_raw.copy()
if 'COD.CLIENTE' in df_unificado.columns:
    df_unificado['COD.CLIENTE'] = df_unificado['COD.CLIENTE'].astype(str).str.strip()
    if df_zonas is not None:
        df_unificado = pd.merge(df_unificado, df_zonas, on='COD.CLIENTE', how='left', suffixes=('', '_ZONA_DROP'))
        cols_drop = [c for c in df_unificado.columns if '_ZONA_DROP' in c]
        if cols_drop: df_unificado.drop(columns=cols_drop, inplace=True)

        for c in ['ACCOUNT MANAGER', 'DEPARTAMENTO', 'PROVINCIA', 'DISTRITO']:
            if c in df_unificado.columns: df_unificado[c] = df_unificado[c].fillna("SIN ASIGNAR")

# Salvar CAI si se perdió
if 'CAI' not in df_unificado.columns:
    if 'CAI_x' in df_unificado.columns: df_unificado.rename(columns={'CAI_x': 'CAI'}, inplace=True)
    elif 'CODIGO' in df_unificado.columns: df_unificado.rename(columns={'CODIGO': 'CAI'}, inplace=True)

# 2. Unificar Maestro Productos (Segmento, Marca, Clasificación DR)
if df_maestro is not None and 'CAI' in df_unificado.columns:
    df_unificado['CAI_Clean'] = df_unificado['CAI'].astype(str).str.strip()
    
    # Columnas a traer del maestro (Ahora incluye CLASIFICACIÓN DR)
    posibles_cols = ['CAI', 'SEGMENTO LB', 'MARCA', 'MACRO_ MACHINE', 'DENOMINATION', 'CLASIFICACIÓN DR', 'CLASIFICACION DR']
    cols_m = [c for c in posibles_cols if c in df_maestro.columns]
    
    maestro_min = df_maestro[cols_m].copy()
    
    # Unificar nombre Clasificación DR si vino sin tilde
    if 'CLASIFICACION DR' in maestro_min.columns and 'CLASIFICACIÓN DR' not in maestro_min.columns:
        maestro_min.rename(columns={'CLASIFICACION DR': 'CLASIFICACIÓN DR'}, inplace=True)
        
    maestro_min.rename(columns={'SEGMENTO LB': 'Segmento LB', 'MACRO MACHINE': 'MACRO_ MACHINE'}, inplace=True)
    
    col_cai_m = next((c for c in maestro_min.columns if "CAI" in c), "CAI")
    maestro_min['CAI_Clean'] = maestro_min[col_cai_m].astype(str).str.strip()
    maestro_min = maestro_min.drop(columns=[col_cai_m], errors='ignore').drop_duplicates('CAI_Clean')

    # Merge
    df_unificado = pd.merge(df_unificado, maestro_min, on='CAI_Clean', how='left')
    
    # Rellenar vacíos
    for c in ['Segmento LB', 'MARCA', 'MACRO_ MACHINE', 'DENOMINATION', 'CLASIFICACIÓN DR']:
        if c in df_unificado.columns: df_unificado[c] = df_unificado[c].fillna("OTROS")
else:
    if 'CAI' in df_unificado.columns:
        df_unificado['CAI_Clean'] = df_unificado['CAI'].astype(str).str.strip()
    else:
        df_unificado['CAI_Clean'] = "SIN CAI"

# --------------------------------------------------------------------------
# 4. BARRA LATERAL (FILTROS)
# --------------------------------------------------------------------------
st.sidebar.title("🎛️ Filtros")

# A. Filtros de Producto
st.sidebar.subheader("📦 Producto")
df_so_trend = df_unificado.copy()

# 1. Segmento
sel_seg = []
if 'Segmento LB' in df_so_trend.columns:
    seg_opts = sorted(df_so_trend['Segmento LB'].astype(str).unique())
    sel_seg = st.sidebar.multiselect("Segmento", seg_opts)
    if sel_seg: df_so_trend = df_so_trend[df_so_trend['Segmento LB'].isin(sel_seg)]

# 2. Marca
sel_marca = []
if 'MARCA' in df_so_trend.columns:
    marca_opts = sorted(df_so_trend['MARCA'].astype(str).unique())
    sel_marca = st.sidebar.multiselect("Marca", marca_opts)
    if sel_marca: df_so_trend = df_so_trend[df_so_trend['MARCA'].isin(sel_marca)]

# 3. Clasificación DR (NUEVO)
sel_clas_dr = []
if 'CLASIFICACIÓN DR' in df_so_trend.columns:
    # Filtramos nulos o vacíos para limpieza visual
    clas_opts = sorted([x for x in df_so_trend['CLASIFICACIÓN DR'].unique() if str(x) != 'nan'])
    sel_clas_dr = st.sidebar.multiselect("Clasificación DR", clas_opts)
    if sel_clas_dr: df_so_trend = df_so_trend[df_so_trend['CLASIFICACIÓN DR'].isin(sel_clas_dr)]

# B. Filtros de Zona (Cascada)
st.sidebar.subheader("🌍 Zona / Cliente")

# 1. Manager
if 'ACCOUNT MANAGER' in df_so_trend.columns:
    am_opts = sorted(df_so_trend['ACCOUNT MANAGER'].astype(str).unique())
    sel_am = st.sidebar.multiselect("Account Manager", am_opts)
    if sel_am: df_so_trend = df_so_trend[df_so_trend['ACCOUNT MANAGER'].isin(sel_am)]

# 2. Departamento
if 'DEPARTAMENTO' in df_so_trend.columns:
    dep_opts = sorted(df_so_trend['DEPARTAMENTO'].astype(str).unique())
    sel_dep = st.sidebar.multiselect("Departamento", dep_opts)
    if sel_dep: df_so_trend = df_so_trend[df_so_trend['DEPARTAMENTO'].isin(sel_dep)]

# 3. Provincia
if 'PROVINCIA' in df_so_trend.columns:
    prov_opts = sorted(df_so_trend['PROVINCIA'].astype(str).unique())
    sel_prov = st.sidebar.multiselect("Provincia", prov_opts)
    if sel_prov: df_so_trend = df_so_trend[df_so_trend['PROVINCIA'].isin(sel_prov)]

st.sidebar.markdown(f"--- \n**Registros:** {len(df_so_trend)}")

# --------------------------------------------------------------------------
# 5. VISUALIZACIÓN: MONITOR DE TENDENCIAS
# --------------------------------------------------------------------------
if df_so_trend.empty:
    st.warning("⚠️ No hay datos para mostrar con los filtros seleccionados.")
else:
    with st.expander("📈 Monitor de Tendencias (Vista Jerárquica)", expanded=True):
        # Configuración Visual
        col_view, col_info = st.columns([2, 3])
        with col_view:
            vista_jerarquia = st.radio("📂 Orden del Árbol:", ["Clientes ➝ Productos", "Productos ➝ Clientes"], horizontal=True)
            
            # Selector Año Extra
            if 'FECHA_DT' in df_so_trend.columns and df_so_trend['FECHA_DT'].notna().any():
                anios_disponibles = sorted(df_so_trend['FECHA_DT'].dt.year.dropna().unique().astype(int), reverse=True)
                anio_ref = st.selectbox("📅 Año para Columna Extra (Total):", anios_disponibles, index=0) if anios_disponibles else None
                fecha_max_so = df_so_trend['FECHA_DT'].max()
            else:
                anios_disponibles = []
                anio_ref = None
                fecha_max_so = pd.Timestamp.now()
        
        with col_info:
            st.info(f"📅 Datos analizados hasta: **{fecha_max_so.strftime('%d-%b-%Y')}**")

        # Preparación de datos para Grid
        cols_base = ['CLIENTE', 'CAI_Clean']
        if 'NOMBRE CLIENTE' in df_so_trend.columns and 'CLIENTE' not in df_so_trend.columns:
            df_so_trend['CLIENTE'] = df_so_trend['NOMBRE CLIENTE']
        if 'DENOMINATION' in df_so_trend.columns: cols_base.append('DENOMINATION')
        if 'CLASIFICACIÓN DR' in df_so_trend.columns: cols_base.append('CLASIFICACIÓN DR')

        df_calc = df_so_trend[cols_base + ['FECHA_DT', 'CANTIDAD']].copy()
        
        # Ventanas de tiempo (6M, 1Y, 1.5Y)
        ventanas_map = {"6M": 6, "1Y": 12, "1.5Y": 18}
        for label, meses in ventanas_map.items():
            f_ini_act = fecha_max_so - pd.DateOffset(months=meses)
            f_ini_prev = f_ini_act - pd.DateOffset(months=meses)
            
            mask_act = (df_calc['FECHA_DT'] > f_ini_act) & (df_calc['FECHA_DT'] <= fecha_max_so)
            df_calc[f'Q_Act_{label}'] = np.where(mask_act, df_calc['CANTIDAD'], 0)
            
            mask_prev = (df_calc['FECHA_DT'] > f_ini_prev) & (df_calc['FECHA_DT'] <= f_ini_act)
            df_calc[f'Q_Prev_{label}'] = np.where(mask_prev, df_calc['CANTIDAD'], 0)

        # Agrupar
        df_final_grid = df_calc.groupby(cols_base).sum(numeric_only=True).reset_index()

        # Columna Año Específico
        col_extra_anio = f"TOTAL {anio_ref}" if anio_ref else "TOTAL AÑO"
        if anio_ref:
            df_anio_ref = df_calc[df_calc['FECHA_DT'].dt.year == anio_ref].groupby(cols_base)['CANTIDAD'].sum().reset_index()
            df_anio_ref.rename(columns={'CANTIDAD': col_extra_anio}, inplace=True)
            df_final_grid = pd.merge(df_final_grid, df_anio_ref, on=cols_base, how='left').fillna(0)
        else:
            df_final_grid[col_extra_anio] = 0

        # Última Fecha de Compra
        df_dates = df_calc.groupby(cols_base)['FECHA_DT'].max().reset_index()
        df_final_grid = pd.merge(df_final_grid, df_dates, on=cols_base, how='left')
        df_final_grid['MAX_DATE_TS'] = df_final_grid['FECHA_DT'].apply(lambda x: int(x.timestamp() * 1000) if pd.notnull(x) else 0)

        # Descripción Visual
        if 'DENOMINATION' in df_final_grid.columns:
            df_final_grid['PRODUCTO_DESC'] = df_final_grid['CAI_Clean'].astype(str) + " | " + df_final_grid['DENOMINATION'].fillna("")
        else:
            df_final_grid['PRODUCTO_DESC'] = df_final_grid['CAI_Clean'].astype(str)

        # --- AG-GRID ---
        gb = GridOptionsBuilder.from_dataframe(df_final_grid)
        col_defs = []

        # Jerarquía
        if vista_jerarquia == "Clientes ➝ Productos":
            col_defs.append({"field": "CLIENTE", "rowGroup": True, "hide": True})
            col_defs.append({"field": "PRODUCTO_DESC", "rowGroup": True, "hide": True})
            header_arbol = "Jerarquía (Cliente ➝ CAI)"
        else:
            col_defs.append({"field": "PRODUCTO_DESC", "rowGroup": True, "hide": True})
            col_defs.append({"field": "CLIENTE", "rowGroup": True, "hide": True})
            header_arbol = "Jerarquía (CAI ➝ Cliente)"
        
        # Columna oculta Clasificación DR (útil si se quiere exportar, aunque no se muestre)
        if 'CLASIFICACIÓN DR' in df_final_grid.columns:
             col_defs.append({"field": "CLASIFICACIÓN DR", "hide": False}) # La dejo visible por si acaso

        # Columnas Fijas
        js_fmt_ts = """
        function(params) {
            if (!params.value || params.value <= 0) return "-";
            var date = new Date(params.value);
            var m = (date.getMonth() + 1).toString().padStart(2, '0');
            var y = date.getFullYear().toString().slice(-2);
            return m + '-' + y;
        }
        """
        col_defs.append({
            "headerName": "Última Compra", "field": "MAX_DATE_TS", "pinned": "left", "width": 115,
            "aggFunc": "max", "valueFormatter": JsCode(js_fmt_ts),
            "cellStyle": {"textAlign": "center", "fontWeight": "bold", "backgroundColor": "#f8f9fa"}
        })
        
        col_defs.append({
            "headerName": f"{col_extra_anio} (Q)", "field": col_extra_anio, "pinned": "left", "width": 100,
            "aggFunc": "sum", "valueFormatter": "x.toLocaleString()",
            "cellStyle": {"backgroundColor": "#fff3cd", "fontWeight": "bold", "color": "black", "textAlign": "center"}
        })

        # Columnas Dinámicas (Tendencias)
        for label in ["6M", "1Y", "1.5Y"]:
            col_prev, col_act = f'Q_Prev_{label}', f'Q_Act_{label}'
            js_icon = f"""
            function(params) {{
                var data = params.node.group ? params.node.aggData : params.data;
                if (!data) return '';
                var prev = data['{col_prev}'] || 0;
                var act = data['{col_act}'] || 0;
                if (act == 0 && prev > 0) return '💀'; 
                if (prev == 0 && act > 0) return '✨'; 
                if (act > prev) return '🟢'; 
                if (act < prev) return '🔴'; 
                if (act == prev && act == 0) return '⚪'; 
                return '🟡';
            }}
            """
            col_defs.append({
                "headerName": f"Periodo {label}",
                "children": [
                    {"headerName": "Prev", "field": col_prev, "width": 65, "aggFunc": "sum", "type": "numericColumn"},
                    {"headerName": "Act", "field": col_act, "width": 65, "aggFunc": "sum", "type": "numericColumn", "cellStyle": {"fontWeight": "bold", "backgroundColor": "#f0f2f6"}},
                    {"headerName": "Trend", "colId": f"Icon_{label}", "width": 60, "valueGetter": JsCode(js_icon), "cellStyle": {"textAlign": "center", "fontSize": "16px"}}
                ]
            })

        gb.configure_grid_options(groupDefaultExpanded=0)
        gridOptions = gb.build()
        gridOptions['columnDefs'] = col_defs
        gridOptions['autoGroupColumnDef'] = {"headerName": header_arbol, "minWidth": 320, "pinned": "left", "cellRendererParams": {"suppressCount": False}}

        AgGrid(df_final_grid, gridOptions=gridOptions, height=600, theme="streamlit", allow_unsafe_jscode=True, enable_enterprise_modules=True)