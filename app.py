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
        /* Fondo general con imagen + overlay blanco 50% */
        .stApp {{
            background: linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)),
                        url("{BG_IMAGE}");
            background-size: cover;
            background-position: center;
            color: {PRIMARY_COLOR};
        }}

        /* Cabecera */
        .header-container {{
            display: flex;
            align-items: center;
            justify-content: flex-start;
            background-color: white;
            padding: 16px 26px;
            border-radius: 12px;
            margin-bottom: 16px;
            border: 1px solid rgba(0,0,0,0.06);
        }}

        .header-logo {{
            height: 54px;
            margin-right: 18px;
        }}

        .header-title {{
            font-size: 28px;
            font-weight: 800;
            letter-spacing: 0.3px;
            color: {PRIMARY_COLOR};
        }}

        /* Tipografía general */
        h1, h2, h3, h4, h5, h6, p, label, span, div {{
            color: {PRIMARY_COLOR} !important;
        }}

        /* Botón de descarga */
        .stDownloadButton button {{
            background-color: {PRIMARY_COLOR} !important;
            color: white !important;
            border-radius: 8px;
            font-weight: 600;
        }}

        /* Sidebar blanco con texto primario */
        section[data-testid="stSidebar"] > div {{
            background-color: rgba(255,255,255,0.92);
            padding: 8px 10px;
            border-left: 1px solid rgba(0,0,0,0.06);
        }}
        section[data-testid="stSidebar"] * {{
            color: {PRIMARY_COLOR} !important;
        }}

        /* Dataframe borde suave */
        div[data-testid="stDataFrame"] {{
            background-color: rgba(255,255,255,0.85);
            border-radius: 10px;
            padding: 6px;
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
        <div class="header-title">ARTIKA BOOKS - GUIAS</div>
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
    "Teléfono (Te enviaremos toda la información por WhatsApp)", "Email",
    "Guía", "Otro interés", "gdpr_e", "gdpr_g", "campaign_fullcode", "País"
]

RENOMBRE = {
    "Submission ID": "id_integrador",
    "Created": "fecha_captacion",
    "Nombre y Apellidos": "nombre",
    "Teléfono (Te enviaremos toda la información por WhatsApp)": "telefono",
    "Email": "email",
    "Guía": "guia",
    "Otro interés": "producto_interes",
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
    "MY2": "Steve McCurry - Capturando la vida",
}

# ================== FUNCIÓN DE TRANSFORMACIÓN ==================
def transformar(df: pd.DataFrame) -> pd.DataFrame:
    # 1) Mantener columnas necesarias (avisar si falta alguna)
    faltan = [c for c in COLUMNAS_NECESARIAS if c not in df.columns]
    if faltan:
        st.warning(f"Faltan columnas en la entrada: {faltan}")
    presentes = [c for c in COLUMNAS_NECESARIAS if c in df.columns]
    df = df[presentes].copy()

    # 2) Renombrar
    df.rename(columns=RENOMBRE, inplace=True)

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
        df["id_integrador"] = df["id_integrador"].astype(str) + "-es_guias"

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

    # Transformar
    df_out = transformar(df_in)

    st.subheader("✅ Vista previa - Salida")
    st.dataframe(df_out.head(20), use_container_width=True)

    # Descarga
    encoding_out = "utf-8-sig" if bom_out else "utf-8"
    buffer = io.StringIO()
    df_out.to_csv(buffer, index=False, encoding=encoding_out, sep=sep_out)
    data = buffer.getvalue().encode(encoding_out)

    st.download_button(
        label="⬇️ Descargar CSV transformado",
        data=data,
        file_name="descargas_transformado.csv",
        mime="text/csv",
        use_container_width=True
    )

    st.success("Transformación completada. Puedes descargar el archivo arriba.")
