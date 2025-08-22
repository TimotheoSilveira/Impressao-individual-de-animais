# app.py — Streamlit (Etapas 1, 2 e 3)
# Importar (CSV/XLSX), validar e gerar PDF com logotipo/cabeçalho/rodapé

from __future__ import annotations
import io
import re
from datetime import datetime, date
from functools import partial
from typing import Optional, Tuple, Iterable

import pandas as pd
import streamlit as st
from reportlab.platypus import (
    SimpleDocTemplate, LongTable, TableStyle, Spacer, Image, PageBreak
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet

# ======================================================
# Configuração da página
# ======================================================
st.set_page_config(page_title="Importar • Validar • PDF", layout="wide")
st.title("Pipeline — Importar, Validar e Gerar PDF")
st.caption("Upload de planilha, normalização de colunas, validações e relatório em PDF com identidade visual.")

# ======================================================
# Dicionário de colunas conhecidas e conjuntos auxiliares
# ======================================================
EXPECTED_COLUMNS = {
    "Customer ID": "customer_id", "Reg Number": "reg_number", "ChainNum": "chain_num",
    "Farm Eartag Number": "farm_eartag_number", "Computer ID": "computer_id",
    "BirthDate": "birthdate", "Sire Code": "sire_code", "Sire Name": "sire_name",
    "MGS Code": "mgs_code", "MGS Name": "mgs_name", "MMGS Code": "mmgs_code",
    "MMGS Name": "mmgs_name", "Calving Date": "calving_date",
    "Lactation Number": "lactation_number", "US Index": "us_index", "My Index": "my_index",
    "Percent Rank": "percent_rank", "Milk": "milk", "Fat": "fat", "Protein": "protein",
    "PL": "pl", "DPR": "dpr", "SCS": "scs", "SCE": "sce", "DCE": "dce", "SSB": "ssb",
    "DSB": "dsb", "CCR": "ccr", "HCR": "hcr", "LIV": "liv", "BWC": "bwc", "UDC": "udc",
    "FLC": "flc", "STA": "sta", "STR": "str", "BD": "bd", "DF": "df", "RA": "ra",
    "RW": "rw", "FA": "fa", "RLSV": "rlsv", "RLRV": "rlrv", "FU": "fu", "RUH": "ruh",
    "RUW": "ruw", "UC": "uc", "UD": "ud", "FTP": "ftp", "RTP": "rtp", "TL": "tl",
}

DATE_COLS = {"birthdate", "calving_date"}
LIKELY_NUMERIC = {
    "chain_num","computer_id","lactation_number","us_index","my_index","percent_rank",
    "milk","fat","protein","pl","dpr","scs","sce","dce","ssb","dsb","ccr","hcr","liv",
    "bwc","udc","flc","sta","str","bd","df","ra","rw","fa","rlsv","rlrv","fu","ruh",
    "ruw","uc","ud","ftp","rtp","tl"
}
ID_LIKE = ["customer_id","reg_number","farm_eartag_number","computer_id"]

# ======================================================
# Utilidades de importação
# ======================================================

def to_snake_case(name: str) -> str:
    n = re.sub(r"\s+", " ", str(name).strip())
    n = n.replace("/", " ").replace("-", " ")
    n = re.sub(r"[^\w\s]", "", n, flags=re.UNICODE)
    return n.lower().strip().replace(" ", "_")


def normalize_header(cols) -> list[str]:
    out = []
    for c in cols:
        s = "" if c is None else re.sub(r"\s+", " ", str(c).strip())
        out.append(s)
    return out


def guess_encoding_from_bytes(data: bytes) -> Optional[str]:
    try:
        import chardet
        enc = chardet.detect(data).get("encoding")
        return enc
    except Exception:
        return None


def read_csv_auto(file_bytes: bytes) -> pd.DataFrame:
    enc = guess_encoding_from_bytes(file_bytes) or "utf-8-sig"
    bio = io.BytesIO(file_bytes)
    try:
        return pd.read_csv(bio, sep=None, engine="python", encoding=enc)
    except Exception:
        pass
    bio = io.BytesIO(file_bytes)
    try:
        return pd.read_csv(bio, sep=";", encoding=enc)
    except Exception:
        pass
    bio = io.BytesIO(file_bytes)
    try:
        return pd.read_csv(bio, sep=",", encoding=enc)
    except Exception:
        bio = io.BytesIO(file_bytes)
        return pd.read_csv(bio, sep="\t", encoding=enc)


def load_table(uploaded_file, sheet: str | int | None = None) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    content = uploaded_file.read()

    if name.endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(io.BytesIO(content), sheet_name=sheet if sheet is not None else 0, engine="openpyxl")
    else:
        df = read_csv_auto(content)

    df.columns = normalize_header(df.columns)
    keep = [c for c in df.columns if c and not str(c).lower().startswith("unnamed")]
    df = df[keep]

    new_cols = [EXPECTED_COLUMNS.get(c, to_snake_case(c)) for c in df.columns]
    df.columns = new_cols

    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    for c in LIKELY_NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    for c in ID_LIKE:
        if c in df.columns:
            df[c] = df[c].astype("string")

    return df

# ======================================================
# Validação (Etapa 2)
# ======================================================

def validate_schema(df: pd.DataFrame) -> Tuple[list[str], list[str]]:
    must_have = [
        "reg_number", "farm_eartag_number", "lactation_number",
        "birthdate", "calving_date", "us_index", "my_index",
        "percent_rank", "scs"
    ]
    missing = [c for c in must_have if c not in df.columns]
    unknown = [c for c in df.columns if c not in EXPECTED_COLUMNS.values()]
    return missing, unknown


def validate_types_and_ranges(
    df: pd.DataFrame,
    today: date,
    min_birth_year: int,
    min_calving_year: int,
) -> pd.DataFrame:
    issues = []

    def add_issue(idx, col, val, msg):
        issues.append({"index": int(idx), "coluna": col, "valor": val, "problema": msg})

    if "percent_rank" in df.columns:
        s = df["percent_rank"]
        mask = s.notna() & ((s < 0) | (s > 100))
        for idx, val in s[mask].items():
            add_issue(idx, "percent_rank", val, "Fora do intervalo [0, 100]")

    if "lactation_number" in df.columns:
        s = df["lactation_number"]
        mask = s.notna() & ((s < 1) | (s.astype(float) % 1 != 0))
        for idx, val in s[mask].items():
            add_issue(idx, "lactation_number", val, ">= 1 e inteiro")

    min_birth = date(min_birth_year, 1, 1)
    min_calving = date(min_calving_year, 1, 1)

    if "birthdate" in df.columns:
        s = df["birthdate"]
        mask = s.notna() & ((s.dt.date < min_birth) | (s.dt.date > today))
        for idx, val in s[mask].items():
            add_issue(idx, "birthdate", str(val), f"Data fora de {min_birth}..{today}")

    if "calving_date" in df.columns:
        s = df["calving_date"]
        mask = s.notna() & ((s.dt.date < min_calving) | (s.dt.date > today))
        for idx, val in s[mask].items():
            add_issue(idx, "calving_date", str(val), f"Data fora de {min_calving}..{today}")

    if set(["birthdate","calving_date"]).issubset(df.columns):
        s = df[["birthdate","calving_date"]].dropna()
        mask = s["calving_date"] < s["birthdate"]
        for idx, row in s[mask].iterrows():
            add_issue(idx, "calving_date", str(row["calving_date"]), "Calving < Birth (inconsistente)")

    if "scs" in df.columns:
        s = df["scs"]
        for idx, val in s[s > 3.0].items():
            add_issue(idx, "scs", val, "> 3,00 (evitar recomendar)")
        for idx, val in s[(s > 2.8) & (s <= 3.0)].items():
            add_issue(idx, "scs", val, "> 2,80 (atenção)")

    for idc in ("reg_number","farm_eartag_number"):
        if idc in df.columns:
            s = df[idc].astype("string")
            mask = s.isna() | (s.str.strip() == "")
            for idx, val in s[mask].items():
                add_issue(idx, idc, val, "Identificador vazio")

    key_cols = [c for c in ("reg_number","farm_eartag_number") if c in df.columns]
    if key_cols:
        dup_mask = df.duplicated(subset=key_cols, keep=False)
        for idx in df.index[dup_mask]:
            add_issue(idx, "+".join(key_cols), "duplicado", "Possível duplicidade pela(s) chave(s)")

    return pd.DataFrame(issues)


def suggest_clean(df: pd.DataFrame, drop_dups_by=("reg_number","farm_eartag_number")) -> pd.DataFrame:
    key_cols = [c for c in drop_dups_by if c in df.columns]
    cleaned = df.copy()
    if key_cols:
        cleaned = cleaned.drop_duplicates(subset=key_cols, keep="first")
    return cleaned

# ======================================================
# PDF (Etapa 3): cabeçalho/rodapé e paginação de colunas
# ======================================================
styles = getSampleStyleSheet()


def _draw_header_footer(canvas, doc, title: str, contact: str | None, logo_path: str | None):
    width, height = landscape(A4)
    canvas.saveState()

    y_top = height - 20
    try:
        if logo_path:
            canvas.drawImage(logo_path, 20, y_top - 32, width=120, height=32, preserveAspectRatio=True, mask='auto')
            text_x = 150
        else:
            text_x = 20
    except Exception:
        text_x = 20

    canvas.setFont('Helvetica-Bold', 12)
    canvas.drawString(text_x, y_top - 10, title)
    canvas.setStrokeColor(colors.lightgrey)
    canvas.line(20, y_top - 36, width - 20, y_top - 36)

    canvas.setFont('Helvetica', 9)
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
    canvas.drawString(20, 15, f'Gerado em {now_str}')
    if contact:
        canvas.drawCentredString(width / 2, 15, contact)
    canvas.drawRightString(width - 20, 15, f'Página {canvas.getPageNumber()}')

    canvas.restoreState()


def split_columns(df: pd.DataFrame, max_cols: int = 10) -> Iterable[list[str]]:
    cols = df.columns.tolist()
    for i in range(0, len(cols), max_cols):
        yield cols[i:i + max_cols]


def gerar_pdf(
    df: pd.DataFrame,
    logo_path: str | None = None,
    *,
    title: str = 'Relatório de Animais — Ranking',
    contact: str | None = None,
    max_cols_per_page: int = 10,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))

    elements = []
    elements.append(Spacer(1, 24))  # espaço para o cabeçalho desenhado no canvas

    slices = list(split_columns(df, max_cols=max_cols_per_page)) or [df.columns.tolist()]
    for idx, cols in enumerate(slices, start=1):
        data = [cols] + df[cols].astype(str).values.tolist()
        table = LongTable(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ]))
        elements.append(table)
        if idx < len(slices):
            elements.append(PageBreak())

    cb = partial(_draw_header_footer, title=title, contact=contact, logo_path=logo_path)
    doc.build(elements, onFirstPage=cb, onLaterPages=cb)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# ======================================================
# Sidebar / UI principal
# ======================================================
with st.sidebar:
    st.header("Upload & Opções")
    uploaded = st.file_uploader("Planilha (CSV/XLSX)", type=["csv", "xlsx", "xlsm", "xls"]) 
    excel_sheet = st.text_input("Aba do Excel (opcional)")
    preview_rows = st.number_input("Linhas de prévia", min_value=5, max_value=100, value=10, step=5)
    st.divider()
    st.subheader("PDF • Identidade visual")
    logo_file = st.file_uploader("Logotipo (PNG/JPG)", type=["png","jpg","jpeg"])
    report_title = st.text_input("Título do relatório", value="Relatório de Animais — Ranking")
    contact_info = st.text_input("Contato (rodapé)", value="Alta Genetics • www.altagenetics.com.br • contato@altagenetics.com.br")
    max_cols_pdf = st.slider("Máx. colunas por página (PDF)", min_value=6, max_value=18, value=10)

msg = st.empty()

if uploaded:
    try:
        sheet_arg: str | int | None = excel_sheet if excel_sheet.strip() else None
        df = load_table(uploaded, sheet_arg)
        st.session_state["df_raw"] = df.copy()
        msg.success("✅ Importação concluída.")

        tab1, tab2, tab3, tab4 = st.tabs(["Prévia", "Validação", "Exportar CSV", "PDF"])

        with tab1:
            st.subheader("Resumo da importação")
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Linhas", f"{len(df):,}")
            with c2:
                st.metric("Colunas", f"{len(df.columns)}")
            st.write("**Colunas padronizadas**")
            st.code(", ".join(df.columns), language="text")
            st.subheader("Pré-visualização")
            st.dataframe(df.head(int(preview_rows)), use_container_width=True)

        with tab2:
            st.subheader("Relatório de validação")
            today = date.today()
            with st.expander("Parâmetros"):
                min_birth_year = st.number_input("Ano mínimo de nascimento", min_value=1970, max_value=datetime.now().year, value=1990)
                min_calving_year = st.number_input("Ano mínimo de parto", min_value=1990, max_value=datetime.now().year, value=2000)
            missing, unknown = validate_schema(df)
            if missing:
                st.error("Colunas obrigatórias ausentes: " + ", ".join(missing))
            else:
                st.success("Esquema mínimo ok (colunas essenciais presentes).")
            if unknown:
                with st.expander("Colunas não mapeadas (aceitas, mas fora do dicionário)"):
                    st.code(", ".join(unknown))
            issues_df = validate_types_and_ranges(df, today, min_birth_year, min_calving_year)
            if not issues_df.empty:
                st.warning(f"Foram encontradas {len(issues_df)} inconsistências.")
                st.dataframe(issues_df, use_container_width=True)
                colname = st.selectbox("Filtrar por coluna", options=["(todas)"] + sorted(issues_df["coluna"].unique().tolist()))
                if colname != "(todas)":
                    st.dataframe(issues_df[issues_df["coluna"] == colname], use_container_width=True)
            else:
                st.success("Nenhuma inconsistência detectada pelas regras atuais.")

        with tab3:
            st.subheader("Exportar CSV normalizado/limpo")
            st.download_button(
                label="Baixar CSV normalizado",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="planilha_normalizada.csv",
                mime="text/csv",
            )
            cleaned = suggest_clean(df)
            st.download_button(
                label="Baixar CSV limpo (sem duplicados por reg_number/farm_eartag_number)",
                data=cleaned.to_csv(index=False).encode("utf-8"),
                file_name="planilha_limpa.csv",
                mime="text/csv",
            )

        with tab4:
            st.subheader("Gerar PDF")
            logo_path = None
            if logo_file:
                logo_path = f"temp_logo.{logo_file.name.split('.')[-1]}"
                with open(logo_path, "wb") as f:
                    f.write(logo_file.read())
            pdf_bytes = gerar_pdf(
                df,
                logo_path=logo_path,
                title=report_title,
                contact=contact_info,
                max_cols_per_page=int(max_cols_pdf),
            )
            st.download_button(
                label="📄 Baixar relatório em PDF",
                data=pdf_bytes,
                file_name="relatorio_animais.pdf",
                mime="application/pdf",
            )

    except Exception as e:
        msg.error(f"❌ Falha: {e}")
else:
    st.info("Faça o upload de um arquivo .csv ou .xlsx na barra lateral para começar.")
