import io
import unicodedata
from pathlib import Path
from glob import iglob
import pandas as pd
import streamlit as st

# ================== CONFIG & ESTILOS ==================
st.set_page_config(page_title="ARTIKA BOOKS - GUIAS", page_icon="📚", layout="wide")

PRIMARY_COLOR = "#000722"
BG_IMAGE = "https://artikabooks.com/wp-content/uploads/2025/02/Banner_Artika_ok-scaled.jpg"
LOGO_URL = "https://artikabooks.com/wp-content/uploads/2024/01/logo-artikabooks.svg"

st.markdown(
    f"""
    <style>
        div[data-testid="stDecoration"] {{ display:none !important; }}
        header[data-testid="stHeader"] {{ background:transparent !important; box-shadow:none !important; border-bottom:none !important; }}
        html, body, [data-testid="stAppViewContainer"] {{ margin:0 !important; padding:0 !important; }}
        .stApp {{
            background: linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)),
                        url("{BG_IMAGE}");
            background-size: cover; background-position:center; color:{PRIMARY_COLOR};
        }}
        .header-container {{ display:flex; align-items:center; justify-content:flex-start; background:white; padding:16px 26px; border-radius:12px; margin-bottom:16px; border:1px solid rgba(0,0,0,0.06); }}
        .header-logo {{height:54px; margin-right:18px;}}
        .header-title {{font-size:28px; font-weight:800; color:{PRIMARY_COLOR};}}
        h1,h2,h3,h4,h5,h6,p,label,span,div {{ color:{PRIMARY_COLOR} !important; }}
        .stSelectbox div[data-baseweb="select"] > div {{ background:white !important; color:{PRIMARY_COLOR} !important; border:1px solid {PRIMARY_COLOR} !important; border-radius:6px !important; }}
        .stSelectbox div[data-baseweb="select"] svg {{ fill:{PRIMARY_COLOR} !important; }}
        div[data-baseweb="popover"], div[role="listbox"], div[role="option"] {{ background:white !important; color:{PRIMARY_COLOR} !important; }}
        div[role="listbox"] {{ border:1px solid {PRIMARY_COLOR} !important; border-radius:8px !important; }}
        div[role="option"]:hover {{ background:#e6eaf5 !important; }}
        .stFileUploader [data-testid="stFileUploaderDropzone"] {{ background:white !important; border:2px dashed {PRIMARY_COLOR} !important; border-radius:10px !important; }}
        .stTextInput input, .stNumberInput input[type="number"] {{ background:white !important; color:{PRIMARY_COLOR} !important; border:1px solid {PRIMARY_COLOR} !important; border-radius:6px !important; }}
        .stDownloadButton button {{ background:white !important; color:{PRIMARY_COLOR} !important; border:1px solid {PRIMARY_COLOR} !important; border-radius:6px !important; font-weight:600 !important; padding:6px 16px !important; }}
        .stDownloadButton button:hover {{ background:#e6eaf5 !important; }}
        section[data-testid="stSidebar"] > div {{ background:rgba(255,255,255,0.92); padding:8px 10px; border-left:1px solid rgba(0,0,0,0.06); }}
        section[data-testid="stSidebar"] * {{ color:{PRIMARY_COLOR} !important; }}
        div[data-testid="stDataFrame"] {{ background:rgba(255,255,255,0.85); border-radius:10px; padding:6px; }}
    </style>
    """,
    unsafe_allow_html=True
)

# Cabecera
st.markdown(
    f"""
    <div class="header-container">
        <img src="{LOGO_URL}" class="header-logo">
        <div class="header-title">    CAPTACIÓN - GUIAS</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.caption("Carga un CSV, aplica el pipeline de transformación y descarga el resultado en Excel (.xlsx).")

# ================== SIDEBAR ==================
with st.sidebar:
    st.header("⚙️ Opciones de lectura (CSV principal)")
    sep_in = st.selectbox("Separador de entrada", [",", ";", "\t"], index=0)
    enc_in = st.selectbox("Codificación de entrada", ["utf-8", "latin-1"], index=0)
    st.header("🧩 Maestro de modalidad")
    url_modalidad = st.text_input("URL RAW de GitHub (opcional)", placeholder="https://raw.githubusercontent.com/.../modalidad.xlsx")
    debug_mode = st.checkbox("🔧 Modo diagnóstico", value=False, help="Muestra rutas y archivos reales en el entorno")

uploaded = st.file_uploader("📤 Sube tu archivo CSV", type=["csv"])

# ================== PARÁMETROS DEL PIPELINE ==================
COLUMNAS_NECESARIAS = [
    "Submission ID", "Created", "Nombre y Apellidos",
    "Teléfono", "Email", "Guía", "Artista",
    "gdpr_e", "gdpr_g", "campaign_fullcode", "País"
]

RENOMBRE = {
    "Submission ID": "id_integrador",
    "Created": "fecha_captacion",
    "Nombre y Apellidos": "nombre",
    "Teléfono": "telefono",
    "Email": "email",
    "Guía": "guia",
    "Artista": "producto_interes",
    "gdpr_e": "rgpd_acepta",
    "gdpr_g": "rgpd_grupo",
    "campaign_fullcode": "modalidad",
    "País": "pais"
}

MAP_RGPD = {"No": "No", "Yes": "Sí"}
MAP_PRODUCTO = {
    "PS":  "Antonio López - Paisajes",
    "DC":  "Manolo Valdés - Damas y Caballeros",
    "SI":  "Sorolla Íntimo",
    "P61": "Jaume Plensa 61",
    "VC":  "Fernando Botero - Via Crucis",
    "CV":  "Steve McCurry - Capturando la vida",
}

# ================== UTILIDADES ==================
def normalizar_texto_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip().str.lower()
    s = s.apply(lambda x: ''.join(c for c in unicodedata.normalize('NFKD', x) if not unicodedata.combining(c)))
    s = s.str.replace(r'[^0-9a-z]+', ' ', regex=True)
    s = s.str.replace(r'\s+', ' ', regex=True).str.strip()
    return s

@st.cache_data(show_spinner=False)
def listar_archivos(d: Path) -> list[str]:
    try:
        return sorted([p.name for p in d.iterdir() if p.is_file()])
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def cargar_excel_local(paths: list[Path]) -> tuple[pd.DataFrame | None, str, list[str], str, str]:
    """
    Intenta cargar el primer Excel que exista en 'paths'.
    Devuelve: (df, origen, rutas_probadas, appdir, cwd)
    """
    probadas = []
    for p in paths:
        probadas.append(str(p))
        try:
            if p.exists():
                df = pd.read_excel(p)
                return df, str(p), probadas, str(Path(__file__).parent), str(Path.cwd())
        except Exception:
            continue
    return None, "", probadas, str(Path(__file__).parent), str(Path.cwd())

@st.cache_data(show_spinner=False)
def cargar_excel_url(url: str) -> tuple[pd.DataFrame | None, str]:
    try:
        df = pd.read_excel(url)
        return df, url
    except Exception:
        return None, url

def buscar_candidatos_modalidad() -> list[Path]:
    """
    Busca modalidad ignorando mayúsculas y por coincidencia parcial 'modalid'
    en: appdir, ./data, cwd, /mnt/data
    """
    appdir = Path(__file__).parent
    datadir = appdir / "data"
    cwd = Path.cwd()
    bases = [appdir, datadir, cwd, Path("/mnt/data")]

    def case_insensitive(base: Path, fname: str) -> list[Path]:
        if not base.exists():
            return []
        target = fname.lower()
        return [p for p in base.iterdir() if p.is_file() and p.name.lower() == target]

    candidates: list[Path] = []
    for b in bases:
        candidates += case_insensitive(b, "modalidad.xlsx")
        candidates += case_insensitive(b, "Modalidad.xlsx")

    # Coincidencia parcial *.xls* que contenga 'modalid'
    for b in [appdir, datadir]:
        if b.exists():
            for p in iglob(str(b / "**/*.xls*"), recursive=True):
                pth = Path(p)
                if "modalid" in pth.name.lower():
                    candidates.append(pth)

    # Quitar duplicados manteniendo orden
    seen = set()
    unique = []
    for p in candidates:
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    return unique

# ========== CARGA MAESTRO PAÍSES ==========
@st.cache_data(show_spinner=False)
def cargar_maestro_paises() -> tuple[pd.DataFrame | None, str, list[str], str, str]:
    paths = [
        Path(__file__).parent / "Paises_landing_ISO.xlsx",
        Path(__file__).parent / "data" / "Paises_landing_ISO.xlsx",
        Path.cwd() / "Paises_landing_ISO.xlsx",
        Path.cwd() / "data" / "Paises_landing_ISO.xlsx",
        Path("/mnt/data/Paises_landing_ISO.xlsx"),
    ]
    return cargar_excel_local(paths)

DF_MAESTRO_PAISES, ORIGEN_PAISES, RUTAS_PAISES, APPDIR, CWD = cargar_maestro_paises()
if DF_MAESTRO_PAISES is not None and {"País","País_normalizado"}.issubset(DF_MAESTRO_PAISES.columns):
    st.caption(f"✅ Maestro de países cargado desde: {ORIGEN_PAISES}")
    st.dataframe(DF_MAESTRO_PAISES.head(10), use_container_width=True)
else:
    st.error("❌ No se encontró/valida el maestro de países 'Paises_landing_ISO.xlsx' (faltan columnas 'País' y 'País_normalizado').")
    with st.expander("Rutas probadas (países)"):
        st.code("\n".join(RUTAS_PAISES))

# ========== CARGA MAESTRO MODALIDAD ==========
def cargar_maestro_modalidad(url_hint: str | None = None):
    # 1) Si nos das URL RAW de GitHub, priorizamos eso
    if url_hint:
        df_url, origen_url = cargar_excel_url(url_hint)
        if df_url is not None:
            return df_url, origen_url, ["(usada URL proporcionada)"], APPDIR, CWD

    # 2) Búsqueda local flexible
    candidates = buscar_candidatos_modalidad()
    # Añadimos rutas típicas por si no encuentra nada
    if not candidates:
        candidates = [
            Path(__file__).parent / "modalidad.xlsx",
            Path(__file__).parent / "data" / "modalidad.xlsx",
            Path.cwd() / "modalidad.xlsx",
            Path.cwd() / "data" / "modalidad.xlsx",
            Path("/mnt/data/modalidad.xlsx"),
        ]
    return cargar_excel_local(candidates)

DF_MAESTRO_MODALIDAD, ORIGEN_MODALIDAD, RUTAS_MODALIDAD, APPDIR, CWD = cargar_maestro_modalidad(url_modalidad if url_modalidad.strip() else None)
if DF_MAESTRO_MODALIDAD is None:
    st.error("❌ No se encontró el maestro 'modalidad.xlsx'.")
    with st.expander("Rutas/criterios probados (modalidad)"):
        st.code("\n".join(RUTAS_MODALIDAD))
else:
    # Validamos columnas esperadas
    cols_ok = {"Modalidad","Nombre"}.issubset(DF_MAESTRO_MODALIDAD.columns)
    if not cols_ok:
        st.warning(f"⚠️ Maestro de modalidad cargado desde {ORIGEN_MODALIDAD}, pero faltan columnas 'Modalidad' y/o 'Nombre'. Columnas detectadas: {list(DF_MAESTRO_MODALIDAD.columns)}")
    else:
        # Normalización básica interna
        DF_MAESTRO_MODALIDAD["Modalidad"] = DF_MAESTRO_MODALIDAD["Modalidad"].astype(str).str.strip()
        DF_MAESTRO_MODALIDAD["Nombre"] = DF_MAESTRO_MODALIDAD["Nombre"].astype(str).str.strip()
        st.success(f"✅ Maestro de modalidad cargado correctamente desde: {ORIGEN_MODALIDAD} ({len(DF_MAESTRO_MODALIDAD)} filas)")
    st.dataframe(DF_MAESTRO_MODALIDAD.head(10), use_container_width=True)

# ========= PANEL DIAGNÓSTICO OPCIONAL =========
if debug_mode:
    st.subheader("🔧 Diagnóstico del entorno")
    col1, col2 = st.columns(2)
    with col1:
        st.write("`__file__`:", __file__)
        st.write("`APPDIR`:", APPDIR)
        st.write("`CWD`:", CWD)
    with col2:
        st.write("Archivos en APPDIR:")
        st.code("\n".join(listar_archivos(Path(APPDIR))) or "(no se pudieron listar)")
        st.write("Archivos en ./data:")
        st.code("\n".join(listar_archivos(Path(APPDIR) / "data")) or "(no se pudieron listar)")

# ================== FUNCIÓN DE TRANSFORMACIÓN ==================
def transformar(df: pd.DataFrame, start_id_value=None,
                df_paises: pd.DataFrame | None = None,
                df_modalidad: pd.DataFrame | None = None) -> pd.DataFrame:

    faltan = [c for c in COLUMNAS_NECESARIAS if c not in df.columns]
    if faltan:
        st.warning(f"Faltan columnas en la entrada: {faltan}")
    presentes = [c for c in COLUMNAS_NECESARIAS if c in df.columns]
    df = df[presentes].copy()

    df.rename(columns=RENOMBRE, inplace=True)

    if start_id_value is not None and "id_integrador" in df.columns:
        df["id_integrador"] = pd.to_numeric(df["id_integrador"], errors="coerce")
        total_antes = len(df)
        df = df.dropna(subset=["id_integrador"])
        descartados_no_num = total_antes - len(df)
        df = df.loc[df["id_integrador"] >= int(start_id_value)]
        descartados_previos = total_antes - descartados_no_num - len(df)
        st.info(f"Filtrado por ID desde **{int(start_id_value)}**: no numéricos = {descartados_no_num}, anteriores = {max(descartados_previos, 0)}")

    if "producto_interes" in df.columns:
        df = df[~df["producto_interes"].astype(str).str.contains("NON", case=False, na=False)]

    df["telefono_norm"] = df["telefono"].astype(str).str.replace(" ", "", regex=False) if "telefono" in df.columns else ""
    df["email_norm"] = df["email"].astype(str).str.strip().str.lower() if "email" in df.columns else ""
    df = df.drop_duplicates(subset=["telefono_norm"], keep="first")
    df = df.drop_duplicates(subset=["email_norm"], keep="first")
    df.drop(columns=["telefono_norm", "email_norm"], inplace=True, errors="ignore")

    if "nombre" in df.columns:
        df["nombre_pila"] = df["nombre"].astype(str).str.split().str[0]
        df["primer_apellido"] = df["nombre"].astype(str).str.split(n=1).str[1].fillna("")
        df.drop(columns=["nombre"], inplace=True)

    if "id_integrador" in df.columns:
        df["id_integrador"] = df["id_integrador"].astype("Int64").astype(str) + "-es_guias"

    if "telefono" in df.columns:
        df["telefono"] = df["telefono"].astype(str).str.replace(" ", "", regex=False)

    if "pais" in df.columns:
        df["pais"] = df["pais"].astype(str).str.split(":").str[0].str.strip()

    # --- Cruce PAÍSES ---
    if df_paises is not None and {"País","País_normalizado"}.issubset(df_paises.columns) and "pais" in df.columns:
        df["_pais_norm"] = normalizar_texto_series(df["pais"])
        mp = df_paises.copy()
        mp["_pais_norm"] = normalizar_texto_series(mp["País"])
        mp = mp.drop_duplicates(subset=["_pais_norm"], keep="first")
        df = df.merge(mp[["_pais_norm", "País_normalizado"]], on="_pais_norm", how="left")
        df["pais"] = df["País_normalizado"].fillna(df["pais"])
        total = len(df); matched = df["País_normalizado"].notna().sum()
        if total > 0: st.info(f"Maestro de países: {matched} de {total} filas normalizadas ({matched/total:.1%}).")
        no_match = df.loc[df["País_normalizado"].isna(), "_pais_norm"].dropna().unique().tolist()
        if no_match:
            st.warning("Países sin correspondencia (muestra máx. 20): " + ", ".join(no_match[:20]) + ("..." if len(no_match) > 20 else ""))
        df.drop(columns=["_pais_norm", "País_normalizado"], inplace=True, errors="ignore")

    # Map RGPD
    if "rgpd_acepta" in df.columns: df["rgpd_acepta"] = df["rgpd_acepta"].map(MAP_RGPD)
    if "rgpd_grupo"  in df.columns: df["rgpd_grupo"]  = df["rgpd_grupo"].map(MAP_RGPD)

    # Map producto_interes
    if "producto_interes" in df.columns:
        df["producto_interes"] = df["producto_interes"].astype(str).str.strip().map(MAP_PRODUCTO).fillna(df["producto_interes"])

    # --- Cruce MODALIDAD ---
    if df_modalidad is not None and {"Modalidad","Nombre"}.issubset(df_modalidad.columns) and "modalidad" in df.columns:
        dm = df_modalidad.copy()
        df["_modalidad_norm"] = normalizar_texto_series(df["modalidad"])
        dm["_modalidad_norm"] = normalizar_texto_series(dm["Modalidad"])
        dm = dm.drop_duplicates(subset=["_modalidad_norm"], keep="first")
        df = df.merge(dm[["_modalidad_norm", "Nombre"]], on="_modalidad_norm", how="left")
        df["modalidad"] = df["Nombre"].fillna(df["modalidad"])
        total = len(df); matched = df["Nombre"].notna().sum()
        if total > 0: st.info(f"Maestro de modalidad: {matched} de {total} filas mapeadas ({matched/total:.1%}).")
        no_match = df.loc[df["Nombre"].isna(), "_modalidad_norm"].dropna().unique().tolist()
        if no_match:
            st.warning("Modalidades sin correspondencia (muestra máx. 20): " + ", ".join(no_match[:20]) + ("..." if len(no_match) > 20 else ""))
        df.drop(columns=["_modalidad_norm", "Nombre"], inplace=True, errors="ignore")

    # Fijos
    df["mercado"] = "EU"
    df["idioma"] = "Español"
    df["tipo_registro"] = "Guias"
    df["marca"] = "Artika"
    df["subcanal"] = "iArtika"

    # Reordenar
    cols = list(df.columns)
    orden = ["id_integrador", "fecha_captacion", "nombre_pila", "primer_apellido"]
    resto = [c for c in cols if c not in orden]
    df = df[[c for c in orden if c in df.columns] + resto]
    return df

# ===== Utilidad: exportar a XLSX =====
def dataframe_a_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "datos") -> bytes:
    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as w:
            df.to_excel(w, index=False, sheet_name=sheet_name)
            ws = w.sheets[sheet_name]
            for i, col in enumerate(df.columns):
                sample = df[col].astype(str).head(100).tolist()
                max_len = max([len(col)] + [len(s) for s in sample]) + 2
                ws.set_column(i, i, min(max_len, 50))
    except Exception:
        try:
            from openpyxl.utils import get_column_letter  # type: ignore
            with pd.ExcelWriter(buffer, engine="openpyxl") as w:
                df.to_excel(w, index=False, sheet_name=sheet_name)
                ws = w.sheets[sheet_name]
                for i, col in enumerate(df.columns, start=1):
                    sample = df[col].astype(str).head(100).tolist()
                    max_len = max([len(col)] + [len(s) for s in sample]) + 2
                    ws.column_dimensions[get_column_letter(i)].width = min(max_len, 50)
        except Exception:
            with pd.ExcelWriter(buffer, engine="openpyxl") as w:
                df.to_excel(w, index=False, sheet_name=sheet_name)
    buffer.seek(0)
    return buffer.getvalue()

# ================== FLUJO DE LA APP ==================
if uploaded is None:
    st.info("Sube un archivo CSV para comenzar.")
else:
    # NOTA: no detenemos la app si falta un maestro; mostramos avisos y seguimos para diagnosticar
    try:
        df_in = pd.read_csv(uploaded, encoding=enc_in, sep=sep_in)
    except UnicodeDecodeError:
        st.error("No se pudo leer con la codificación seleccionada. Prueba con 'latin-1'.")
        st.stop()
    except Exception as e:
        st.error(f"No se pudo leer el CSV: {e}")
        st.stop()

    st.subheader("👀 Vista previa - Entrada")
    st.dataframe(df_in.head(20), use_container_width=True)

    start_id_value = None
    if "Submission ID" in df_in.columns:
        serie_num = pd.to_numeric(df_in["Submission ID"], errors="coerce").dropna()
        if not serie_num.empty:
            min_id = int(serie_num.min()); max_id = int(serie_num.max())
            st.markdown("### 🔢 Procesar desde ID (id_integrador)")
            start_id_value = st.number_input(
                "Indica el ID desde el que quieres procesar (inclusivo).",
                min_value=min_id, max_value=max_id, value=min_id, step=1,
                help="Se eliminarán los registros con ID inferiores."
            )
        else:
            st.error("La columna 'Submission ID' no contiene valores numéricos válidos.")
    else:
        st.info("No se encontró la columna 'Submission ID'. No se aplicará el filtro por ID de inicio.")

    df_out = transformar(
        df_in,
        start_id_value=start_id_value,
        df_paises=DF_MAESTRO_PAISES,
        df_modalidad=DF_MAESTRO_MODALIDAD
    )

    st.subheader("✅ Vista previa - Salida")
    st.dataframe(df_out.head(20), use_container_width=True)

    data_xlsx = dataframe_a_xlsx_bytes(df_out, sheet_name="datos")
    st.download_button(
        label="⬇️ Descargar Excel transformado (.xlsx)",
        data=data_xlsx,
        file_name="descargas_transformado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    st.success("Transformación completada. Puedes descargar el archivo arriba.")
