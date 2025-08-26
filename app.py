# app.py
# Streamlit: Cargar un XLSX, transformar a un esquema mínimo, limpiar,
# deduplicar por teléfono/email (conservando el más reciente), y generar reporte.

import re
from io import BytesIO
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cargador y Normalizador XLSX", layout="wide")
st.title("Cargar y Transformar XLSX")

# --- Configuración de columnas (origen -> destino) ---
KEEP_MAP = {
    "Submission ID": "submission_id",
    "Created": "created_at",
    "Nombre y Apellidos": "full_name",
    "Teléfono (Te enviaremos toda la información por WhatsApp)": "phone",
    "Email": "email",
    "Guía": "guide",
    "Otro interés": "other_interest",
    "gdpr_e": "gdpr_e",
    "gdpr_g": "gdpr_g",
    "Política de Privacidad": "privacy_policy",
    "Código producto": "product_code",
    "campaign_fullcode": "campaign_fullcode",
    "País": "country",
}

# --- Helpers de limpieza y validación ---
def _remove_spaces_phone(x):
    """Quita SOLO espacios del teléfono (respeta otros símbolos)."""
    if pd.isna(x):
        return None
    s = re.sub(r"\s+", "", str(x)).strip()
    return s or None

def _to_bool(x):
    if pd.isna(x):
        return None
    s = str(x).strip().lower()
    return s in {"1","true","t","sí","si","yes","y","acepto","accept","ok"}

def _valid_email(s):
    if pd.isna(s):
        return False
    s = str(s).strip()
    return re.match(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", s, re.I) is not None

def _before_colon(x):
    """Devuelve todo lo que está antes del primer ':' (o el valor limpio si no hay ':')."""
    if pd.isna(x):
        return None
    s = str(x)
    return s.split(":", 1)[0].strip()

def transform_min(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    - Renombra/selecciona columnas (solo KEEP_MAP).
    - Limpia: email lower/trim, phone sin espacios, created_at a datetime.
    - country: valor antes de ':'.
    - full_name -> firstname (1ª palabra) + middlename (resto).
    - Elimina filas con other_interest == 'NON' (case-insensitive).
    - Dedup por phone y luego por email, conservando el más reciente (created_at).
    - Devuelve (df_limpio, reporte_duplicados).
    """

    # Aviso si faltan columnas de origen
    missing = [col for col in KEEP_MAP.keys() if col not in df_raw.columns]
    if missing:
        st.warning(f"Faltan columnas en el XLSX: {missing}")

    # Renombrar y asegurar esquema
    df = df_raw.rename(columns=KEEP_MAP)
    for dest in KEEP_MAP.values():
        if dest not in df.columns:
            df[dest] = pd.NA
    df = df[list(KEEP_MAP.values())].copy()

    # Limpiezas base
    df["full_name"]  = df["full_name"].astype(str).str.strip()
    df["email"]      = df["email"].astype(str).str.strip().str.lower().where(df["email"].notna(), None)
    df["phone"]      = df["phone"].apply(_remove_spaces_phone)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    for c in ["gdpr_e", "gdpr_g", "privacy_policy"]:
        if c in df.columns:
            df[c] = df[c].apply(_to_bool)

    # country: quedarse con lo anterior a ':'
    df["country"] = df["country"].apply(_before_colon)

    # Split de nombre: primera palabra = firstname, resto = middlename
    split = df["full_name"].str.split(r"\s+", n=1, expand=True)
    df["firstname"]  = split[0].where(split[0].notna(), None)
    df["middlename"] = split[1].where(split.shape[1] > 1, None) if 1 in split.columns else None

    # Eliminar filas con other_interest == 'NON' (case-insensitive, trims)
    oi = df["other_interest"]
    mask_non = oi.notna() & oi.astype(str).str.strip().str.upper().eq("NON")
    df = df[~mask_non].reset_index(drop=True).copy()

    # UID interno para reporte / dedup
    df["_uid"] = df.reset_index(drop=True).index

    # Orden por fecha (más reciente primero; NaT al final). mergesort es estable
    df = df.sort_values("created_at", ascending=False, na_position="last", kind="mergesort")

    # --- Generación de reportes por etapa ---
    def _stage_report(dfin: pd.DataFrame, key: str, reason: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Dedup por 'key' manteniendo el más reciente. Devuelve (df_out, reporte_etapa)."""
        nonnull = dfin[dfin[key].notna()].copy()
        if nonnull.empty:
            return dfin, pd.DataFrame()

        kept = nonnull.drop_duplicates(subset=[key], keep="first")[
            [key, "_uid", "submission_id", "created_at", "phone", "email"]
        ].rename(columns={
            "_uid": "kept_uid",
            "submission_id": "kept_submission_id",
            "created_at": "kept_created_at",
            "phone": "kept_phone",
            "email": "kept_email",
        })

        joined = nonnull.merge(
            kept[[key, "kept_uid", "kept_submission_id", "kept_created_at", "kept_phone", "kept_email"]],
            on=key, how="left"
        )

        removed = joined[joined["_uid"] != joined["kept_uid"]].copy()
        if removed.empty:
            return dfin, pd.DataFrame()

        report = removed.assign(
            reason=reason,
            key_value=removed[key]
        )[[
            "reason", "key_value",
            "kept_submission_id", "kept_created_at", "kept_phone", "kept_email",
            "submission_id", "created_at", "phone", "email", "_uid"
        ]].rename(columns={
            "submission_id": "removed_submission_id",
            "created_at": "removed_created_at",
            "phone": "removed_phone",
            "email": "removed_email",
            "_uid": "removed_uid",
        })

        # Eliminar de dfin las filas marcadas como removed
        dfout = dfin[~dfin["_uid"].isin(report["removed_uid"])].copy()
        return dfout, report

    # --- DEDUP POR PHONE ---
    df, rep_phone = _stage_report(df, key="phone", reason="dup_phone")
    # --- DEDUP POR EMAIL ---
    df, rep_email = _stage_report(df, key="email", reason="dup_email")

    # Reporte combinado
    if (rep_phone is not None and not rep_phone.empty) or (rep_email is not None and not rep_email.empty):
        dup_report = pd.concat([r for r in [rep_phone, rep_email] if r is not None and not r.empty], ignore_index=True)
    else:
        dup_report = pd.DataFrame(columns=[
            "reason","key_value",
            "kept_submission_id","kept_created_at","kept_phone","kept_email",
            "removed_submission_id","removed_created_at","removed_phone","removed_email"
        ])

    # Checks rápidos (opcionales para UI)
    df["email_valido"] = df["email"].apply(_valid_email)
    df["telefono_valido"] = df["phone"].apply(
        lambda x: False if not x else (8 <= len(re.sub(r"\D", "", x)) <= 15)
    )

    # Limpiar columnas internas
    df = df.drop(columns=["_uid"], errors="ignore")
    dup_report = dup_report.drop(columns=["removed_uid"], errors="ignore")

    return df.reset_index(drop=True), dup_report


# =========================
#           UI
# =========================
uploaded = st.file_uploader(
    "Sube un archivo .xlsx (cualquier nombre)",
    type=["xlsx"],
    accept_multiple_files=False
)

if uploaded is not None:
    try:
        # Leer nombres de hojas y permitir seleccionar
        xls = pd.ExcelFile(uploaded, engine="openpyxl")
        sheet = st.selectbox("Selecciona la hoja a procesar", xls.sheet_names)
        df_raw = pd.read_excel(xls, sheet_name=sheet, dtype=str)  # leemos todo como str para no perder formatos

        st.success(f"Archivo: {uploaded.name} | Hoja: {sheet} | Filas: {len(df_raw)} | Columnas: {len(df_raw.columns)}")

        with st.expander("Ver columnas originales"):
            st.write(list(df_raw.columns))

        # Transformación principal
        st.header("Transformación y limpieza")
        df_out, dup_report = transform_min(df_raw)

        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Filas limpias", len(df_out))
        with col2: st.metric("Emails válidos", int(df_out["email_valido"].sum()))
        with col3: st.metric("Teléfonos válidos", int(df_out["telefono_valido"].sum()))
        with col4: st.metric("Duplicados eliminados", len(dup_report))

        # Tabs de salida
        tab1, tab2 = st.tabs(["✅ Datos limpios", "♻️ Duplicados eliminados"])

        with tab1:
            st.dataframe(df_out.head(200), use_container_width=True)

            st.download_button(
                "Descargar CSV limpio (UTF-8)",
                data=df_out.to_csv(index=False),
                file_name="leads_min_limpio.csv",
                mime="text/csv"
            )

            out_clean = BytesIO()
            with pd.ExcelWriter(out_clean, engine="openpyxl") as writer:
                df_out.to_excel(writer, index=False, sheet_name="leads")
            st.download_button(
                "Descargar Excel limpio",
                data=out_clean.getvalue(),
                file_name="leads_min_limpio.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with tab2:
            if dup_report.empty:
                st.success("No se detectaron duplicados por teléfono ni por email.")
            else:
                st.dataframe(dup_report, use_container_width=True)

                st.download_button(
                    "Descargar reporte duplicados (CSV)",
                    data=dup_report.to_csv(index=False),
                    file_name="reporte_duplicados.csv",
                    mime="text/csv"
                )

                out_rep = BytesIO()
                with pd.ExcelWriter(out_rep, engine="openpyxl") as writer:
                    dup_report.to_excel(writer, index=False, sheet_name="duplicados")
                st.download_button(
                    "Descargar reporte duplicados (Excel)",
                    data=out_rep.getvalue(),
                    file_name="reporte_duplicados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        st.error(f"No se pudo leer el XLSX. Detalle: {e}")
else:
    st.info("Sube un archivo .xlsx para empezar.")
