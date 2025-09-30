import io
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
        /* Quitar barra/linea superior */
        div[data-testid="stDecoration"] {{ display:none !important; }}
        header[data-testid="stHeader"] {{
            background:transparent !important;
            box-shadow:none !important;
            border-bottom:none !important;
        }}

        html, body, [data-testid="stAppViewContainer"] {{
            margin:0 !important;
            padding:0 !important;
        }}

        /* Fondo general */
        .stApp {{
            background: linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)),
                        url("{BG_IMAGE}");
            background-size: cover; background-position:center;
            color:{PRIMARY_COLOR};
        }}

        /* Cabecera */
        .header-container {{
            display:flex; align-items:center; justify-content:flex-start;
            background:white; padding:16px 26px; border-radius:12px;
            margin-bottom:16px; border:1px solid rgba(0,0,0,0.06);
        }}
        .header-logo {{height:54px; margin-right:18px;}}
        .header-title {{font-size:28px; font-weight:800; color:{PRIMARY_COLOR};}}

        /* Tipografía global */
        h1,h2,h3,h4,h5,h6,p,label,span,div {{
            color:{PRIMARY_COLOR} !important;
        }}

        /* ---------- INPUTS ---------- */

        /* Caja principal selectbox */
        .stSelectbox div[data-baseweb="select"] > div {{
            background:white !important; color:{PRIMARY_COLOR} !important;
            border:1px solid {PRIMARY_COLOR} !important; border-radius:6px !important;
        }}
        .stSelectbox div[data-baseweb="select"] svg {{ fill:{PRIMARY_COLOR} !important; }}

        /* Menú desplegable */
        div[data-baseweb="popover"] {{ background:white !important; color:{PRIMARY_COLOR} !important; }}
        div[role="listbox"] {{ background:white !important; color:{PRIMARY_COLOR} !important; border:1px solid {PRIMARY_COLOR} !important; border-radius:8px !important; }}
        div[role="option"] {{ background:white !important; color:{PRIMARY_COLOR} !important; }}
        div[role="option"]:hover {{ background:#e6eaf5 !important; color:{PRIMARY_COLOR} !important; }}

        /* File uploader */
        .stFileUploader div[data-testid="stFileUploaderDropzone"],
        .stFileUploader section[data-testid="stFileUploaderDropzone"] {{
            background:white !important; border:2px dashed {PRIMARY_COLOR} !important;
            border-radius:10px !important; color:{PRIMARY_COLOR} !important;
        }}
        .stFileUploader div[data-testid="stFileUploaderDropzone"] span,
        .stFileUploader section[data-testid="stFileUploaderDropzone"] span {{
            color:{PRIMARY_COLOR} !important; font-weight:500 !important;
        }}
        .stFileUploader div[data-testid="stFileUploaderDropzone"] button,
        .stFileUploader section[data-testid="stFileUploaderDropzone"] button {{
            background:white !important; color:{PRIMARY_COLOR} !important;
            border:1px solid {PRIMARY_COLOR} !important; border-radius:6px !important;
            font-weight:600 !important; padding:4px 12px !important;
        }}
        .stFileUploader div[data-testid="stFileUploaderDropzone"] button:hover,
        .stFileUploader section[data-testid="stFileUploaderDropzone"] button:hover {{
            background:#e6eaf5 !important; color:{PRIMARY_COLOR} !important;
        }}

        /* Text input */
        .stTextInput > div > div > input {{
            background:white !important; color:{PRIMARY_COLOR} !important;
            border:1px solid {PRIMARY_COLOR} !important; border-radius:6px !important;
        }}

        /* Number input */
        .stNumberInput input[type="number"] {{
            background:white !important; color:{PRIMARY_COLOR} !important;
            border:1px solid {PRIMARY_COLOR} !important; border-radius:6px !important;
        }}

        /* Botón de descarga */
        .stDownloadButton button {{
            background:white !important; color:{PRIMARY_COLOR} !important;
            border:1px solid {PRIMARY_COLOR} !important; border-radius:6px !important;
            font-weight:600 !important; padding:6px 16px !important;
        }}
        .stDownloadButton button:hover {{
            background:#e6eaf5 !important; color:{PRIMARY_COLOR} !important;
        }}

        /* Sidebar */
        section[data-testid="stSidebar"] > div {{
            background:rgba(255,255,255,0.92); padding:8px 10px; border-left:1px solid rgba(0,0,0,0.06);
        }}
        section[data-testid="stSidebar"] * {{ color:{PRIMARY_COLOR} !important; }}

        /* Dataframe */
        div[data-testid="stDataFrame"] {{
            background:rgba(255,255,255,0.85); border-radius:10px; padding:6px;
        }}
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

st.caption("Carga un CSV, aplica el pipeline de transformación y descarga el resultado. Las tildes se conservan (opción BOM para Excel).")

# ================== SIDEBAR ==================
with st.sidebar:
    st.header("⚙️ Opciones de lectura")
    sep_in = st.selectbox("Separador de entrada", [",", ";", "\t"], index=0, help="Separador del CSV original.")
    enc_in = st.selectbox("Codificación de entrada", ["utf-8", "latin-1"], index=0)

    st.header("⚙️ Opciones de salida")
    sep_out = st.selectbox("Separador de salida", [",", ";", "\t"], index=0, help="Para Excel en es-ES suele ir bien ';'")
    bom_out = st.checkbox("Incluir BOM (utf-8-sig) para Excel", value=True)

    st.markdown("---")
    st.caption("Si ves caracteres raros en Excel, activa BOM o importa el CSV eligiendo UTF-8.")

uploaded = st.file_uploader("📤 Sube tu archivo CSV", type=["csv"])

# ================== PARÁMETROS DEL PIPELINE ==================
COLUMNAS_NECESARIAS = [
    "Submission ID", "Created", "Nombre y Apellidos",
    "Teléfono", "Email",
    "Guía", "Artista", "gdpr_e", "gdpr_g", "campaign_fullcode", "País"
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

# Mapeo de códigos de producto a títulos completos
MAP_PRODUCTO = {
    "PS":  "Antonio López - Paisajes",
    "DC":  "Manolo Valdés - Damas y Caballeros",
    "SI":  "Sorolla Íntimo",
    "P61": "Jaume Plensa 61",
    "VC":  "Fernando Botero - Via Crucis",
    "CV": "Steve McCurry - Capturando la vida",
}

# ================== FUNCIÓN DE TRANSFORMACIÓN ==================
def transformar(df: pd.DataFrame, start_id_value=None) -> pd.DataFrame:
    # 1) Mantener columnas necesarias (avisar si falta alguna)
    faltan = [c for c in COLUMNAS_NECESARIAS if c not in df.columns]
    if faltan:
        st.warning(f"Faltan columnas en la entrada: {faltan}")
    presentes = [c for c in COLUMNAS_NECESARIAS if c in df.columns]
    df = df[presentes].copy()

    # 2) Renombrar
    df.rename(columns=RENOMBRE, inplace=True)

    # 2.5) ===== FILTRAR DESDE ID (INCLUSIVO) - FORZADO A NUMÉRICO =====
    if start_id_value is not None and "id_integrador" in df.columns:
        df["id_integrador"] = pd.to_numeric(df["id_integrador"], errors="coerce")
        total_antes = len(df)
        df = df.dropna(subset=["id_integrador"])  # descartar no numéricos
        descartados_no_num = total_antes - len(df)
        df = df.loc[df["id_integrador"] >= int(start_id_value)]
        descartados_previos = total_antes - descartados_no_num - len(df)
        st.info(f"Filtrado por ID desde **{int(start_id_value)}**: "
                f"descartados no numéricos = {descartados_no_num}, "
                f"descartados por ser anteriores = {max(descartados_previos, 0)}")

    # ===== DEDUPLICADO INMEDIATO TRAS RENOMBRAR =====
    # 3) Filtrar filas cuyo producto_interes contenga "NON" (case-insensitive)
    if "producto_interes" in df.columns:
        df = df[~df["producto_interes"].astype(str).str.contains("NON", case=False, na=False)]

    # 4) Claves normalizadas para deduplicar
    df["telefono_norm"] = df["telefono"].astype(str).str.replace(" ", "", regex=False) if "telefono" in df.columns else ""
    df["email_norm"] = df["email"].astype(str).str.strip().str.lower() if "email" in df.columns else ""

    # 5) Eliminar duplicados por teléfono y por email (mantener primera aparición)
    df = df.drop_duplicates(subset=["telefono_norm"], keep="first")
    df = df.drop_duplicates(subset=["email_norm"], keep="first")

    # 6) Quitar columnas auxiliares
    df.drop(columns=["telefono_norm", "email_norm"], inplace=True, errors="ignore")

    # ===== RESTO DEL PIPELINE =====
    # 7) Dividir 'nombre' en 'nombre_pila' y 'primer_apellido', eliminar 'nombre'
    if "nombre" in df.columns:
        df["nombre_pila"] = df["nombre"].astype(str).str.split().str[0]
        df["primer_apellido"] = df["nombre"].astype(str).str.split(n=1).str[1].fillna("")
        df.drop(columns=["nombre"], inplace=True)

    # 8) Añadir sufijo a id_integrador
    if "id_integrador" in df.columns:
        df["id_integrador"] = df["id_integrador"].astype("Int64").astype(str) + "-es_guias"

    # 9) Limpiar teléfono (quitar espacios)
    if "telefono" in df.columns:
        df["telefono"] = df["telefono"].astype(str).str.replace(" ", "", regex=False)

    # 10) País: quedarse con lo anterior a ":" y limpiar espacios
    if "pais" in df.columns:
        df["pais"] = df["pais"].astype(str).str.split(":").str[0].str.strip()

    # 11) Mapear RGPD
    if "rgpd_acepta" in df.columns:
        df["rgpd_acepta"] = df["rgpd_acepta"].map(MAP_RGPD)
    if "rgpd_grupo" in df.columns:
        df["rgpd_grupo"] = df["rgpd_grupo"].map(MAP_RGPD)

    # 12) Mapear producto_interes (códigos -> títulos), conservar original si no hay match
    if "producto_interes" in df.columns:
        df["producto_interes"] = (
            df["producto_interes"].astype(str).str.strip().map(MAP_PRODUCTO).fillna(df["producto_interes"])
        )

    # 13) Añadir columnas fijas
    df["mercado"] = "EU"
    df["idioma"] = "Español"
    df["tipo_registro"] = "Guias"
    df["marca"] = "Artika"
    df["subcanal"] = "iArtika"

    # 14) Reordenar: nombre_pila y primer_apellido detrás de fecha_captacion
    cols = list(df.columns)
    orden = ["id_integrador", "fecha_captacion", "nombre_pila", "primer_apellido"]
    resto = [c for c in cols if c not in orden]
    df = df[[c for c in orden if c in df.columns] + resto]

    return df

# ================== FLUJO DE LA APP ==================
if uploaded is None:
    st.info("Sube un archivo CSV para comenzar.")
else:
    # Lectura con los parámetros elegidos
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

    # ===== UI: Selección de ID de inicio (siempre numérico) =====
    start_id_value = None
    if "Submission ID" in df_in.columns:
        serie_num = pd.to_numeric(df_in["Submission ID"], errors="coerce").dropna()
        if not serie_num.empty:
            min_id = int(serie_num.min())
            max_id = int(serie_num.max())
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

    # Transformar
    df_out = transformar(df_in, start_id_value=start_id_value)

    st.subheader("✅ Vista previa - Salida")
    st.dataframe(df_out.head(20), use_container_width=True)

# ===== Descarga en XLSX =====
import io

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_out.to_excel(writer, index=False, sheet_name="datos")

    # (Opcional) Autoajuste simple de anchos de columna
    worksheet = writer.sheets["datos"]
    for i, col in enumerate(df_out.columns):
        # Calcula un ancho razonable usando hasta 100 filas para no tardar
        sample = df_out[col].astype(str).head(100).tolist()
        max_len = max([len(col)] + [len(s) for s in sample]) + 2
        worksheet.set_column(i, i, min(max_len, 50))

# Importante: mover el puntero al principio y obtener los bytes
buffer.seek(0)
data = buffer.getvalue()

st.download_button(
    label="⬇️ Descargar Excel transformado (.xlsx)",
    data=data,
    file_name="descargas_transformado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)



