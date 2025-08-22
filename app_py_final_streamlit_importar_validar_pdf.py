# app_etapa1.py — Etapa 1: Importação e Pré-visualização
# Objetivo: subir planilha CSV/XLSX, normalizar cabeçalhos e exibir uma prévia.

import io
import re
from typing import Optional

import pandas as pd
import streamlit as st

from dataclasses import dataclass
from pandas.api.types import is_datetime64tz_dtype
import pandas as pd

def _as_naive_ts(s: pd.Series) -> pd.Series:
    """Converte série de datas para Timestamp 'naive' (sem timezone) e normaliza."""
    s2 = pd.to_datetime(s, errors="coerce")
    if is_datetime64tz_dtype(s2):
        s2 = s2.dt.tz_convert(None)
    return s2.dt.normalize()


# --- chaves únicas para widgets (evita conflito de IDs) ---
APP = "final"  # pode trocar por outro prefixo único do seu app

def K(name: str) -> str:
    """Gera uma chave única e estável para widgets do Streamlit."""
    return f"{APP}:{name}"

def _as_naive_ts(s: pd.Series) -> pd.Series:
    """Converte para Timestamp sem fuso e normaliza para meia-noite."""
    s2 = pd.to_datetime(s, errors="coerce")
    if is_datetime64tz_dtype(s2):
        # remove timezone (UTC → naive)
        s2 = s2.dt.tz_convert(None)
    return s2.dt.normalize()

# -----------------------------------------------------
# Config da página
# -----------------------------------------------------
st.set_page_config(page_title="Etapa 1 — Importar & Pré-visualizar", layout="wide")
st.title("Etapa 1 — Importação e Pré-visualização")
st.caption("Upload de planilha, normalização de cabeçalhos e prévia dos dados.")

# -----------------------------------------------------
# Dicionário de colunas conhecidas (mapeia → snake_case)
# -----------------------------------------------------
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

# -----------------------------------------------------
# Helpers de importação
# -----------------------------------------------------
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
    # 1) tenta sep auto
    try:
        return pd.read_csv(bio, sep=None, engine="python", encoding=enc)
    except Exception:
        pass
    # 2) tenta ponto e vírgula
    bio = io.BytesIO(file_bytes)
    try:
        return pd.read_csv(bio, sep=";", encoding=enc)
    except Exception:
        pass
    # 3) vírgula
    bio = io.BytesIO(file_bytes)
    try:
        return pd.read_csv(bio, sep=",", encoding=enc)
    except Exception:
        pass
    # 4) tab
    bio = io.BytesIO(file_bytes)
    return pd.read_csv(bio, sep="\t", encoding=enc)

def load_table(uploaded_file, sheet: str | int | None = None) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    content = uploaded_file.read()

    if name.endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(io.BytesIO(content), sheet_name=sheet if sheet is not None else 0, engine="openpyxl")
    else:
        df = read_csv_auto(content)

    # limpa cabeçalhos e remove "Unnamed: ..."
    df.columns = normalize_header(df.columns)
    keep = [c for c in df.columns if c and not str(c).lower().startswith("unnamed")]
    df = df[keep]

    # padroniza nomes
    new_cols = [EXPECTED_COLUMNS.get(c, to_snake_case(c)) for c in df.columns]
    df.columns = new_cols

    # tipos
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in LIKELY_NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

# -----------------------------------------------------
# UI — Sidebar
# -----------------------------------------------------
with st.sidebar:
    st.header("Upload & Opções")
    uploaded = st.file_uploader("Planilha (CSV/XLSX)", type=["csv","xlsx","xlsm","xls"], key=K("e1_planilha"))
    excel_sheet = st.text_input("Aba do Excel (opcional)", key=K("e1_sheet"))
    preview_rows = st.number_input("Linhas da prévia", min_value=5, max_value=100, value=10, step=5, key=K("e1_preview"))


# -----------------------------------------------------
# UI — Conteúdo
# -----------------------------------------------------
msg = st.empty()

if uploaded:
    try:
        sheet_arg: str | int | None = excel_sheet if excel_sheet.strip() else None
        df = load_table(uploaded, sheet_arg)
        st.session_state["df_etapa1"] = df.copy()

        msg.success("✅ Importação concluída.")
        st.subheader("Resumo")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Linhas", f"{len(df):,}")
        with c2:
            st.metric("Colunas", f"{len(df.columns)}")

        st.write("**Colunas padronizadas**")
        st.code(", ".join(df.columns), language="text")

        st.subheader("Pré-visualização")
        st.dataframe(df.head(int(preview_rows)), use_container_width=True)

        st.download_button(
            label="Baixar CSV normalizado",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="planilha_normalizada.csv",
            mime="text/csv",
        )

    except Exception as e:
        msg.error(f"❌ Falha na importação: {e}")
else:
    st.info("Faça o upload de um arquivo .csv ou .xlsx na barra lateral para começar.")


# app_etapa3.py — Etapa 3: PDF individual por animal (layout mapeado)
# - Upload CSV/XLSX (ou reaproveita df da Etapa 1/2 se estiver no session_state)
# - Gera um PDF em A4 paisagem, 1 animal por página, com logo opcional
# - Rótulos e posições conforme tabela enviada (substituições OPI/Méritos/Trato/Índice Saúde)

import io
import re
from datetime import datetime, date
from functools import partial
from typing import Optional, Iterable, Tuple, List

import pandas as pd
import streamlit as st

# --- chaves únicas para widgets (evita conflito de IDs) ---
APP = "final"  # pode trocar por outro prefixo único do seu app

def K(name: str) -> str:
    """Gera uma chave única e estável para widgets do Streamlit."""
    return f"{APP}:{name}"


# ---- Guard para dependências de PDF ----
try:
    from reportlab.platypus import (
        SimpleDocTemplate, Table, LongTable, TableStyle,
        Spacer, Image, PageBreak, Paragraph
    )
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except ModuleNotFoundError:
    st.error(
        "Dependência ausente para gerar PDF. Adicione **reportlab** e **pillow** no requirements.txt e rode novamente."
    )
    st.stop()

# ======================================================
# Config da página
# ======================================================
st.set_page_config(page_title="Etapa 3 — PDF Individual", layout="wide")
st.title("Etapa 3 — Geração de PDF Individual (por animal)")
st.caption("Layout e rótulos conforme mapeamento solicitado.")

# ======================================================
# Import helpers (iguais das etapas anteriores para ficar autônomo)
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
    "lactation_number","us_index","my_index","percent_rank",
    "milk","fat","protein","pl","dpr","scs","sce","dce","ssb","dsb",
    "ccr","hcr","liv","bwc","udc","flc","sta","str","bd","df","ra",
    "rw","fa","rlsv","rlrv","fu","ruh","ruw","uc","ud","ftp","rtp","tl"
}
ID_LIKE = ["customer_id","reg_number","farm_eartag_number","computer_id"]

def to_snake_case(name: str) -> str:
    n = re.sub(r"\s+", " ", str(name).strip())
    n = n.replace("/", " ").replace("-", " ")
    n = re.sub(r"[^\w\s]", "", n, flags=re.UNICODE)
    return n.lower().strip().replace(" ", "_")

def normalize_header(cols) -> list[str]:
    return [("" if c is None else re.sub(r"\s+", " ", str(c).strip())) for c in cols]

def guess_encoding_from_bytes(data: bytes) -> Optional[str]:
    try:
        import chardet
        return chardet.detect(data).get("encoding")
    except Exception:
        return None

def read_csv_auto(file_bytes: bytes) -> pd.DataFrame:
    enc = guess_encoding_from_bytes(file_bytes) or "utf-8-sig"
    for sep in [None, ";", ",", "\t"]:
        bio = io.BytesIO(file_bytes)
        try:
            return pd.read_csv(bio, sep=sep, engine="python" if sep is None else None, encoding=enc)
        except Exception:
            pass
    # último recurso
    return pd.read_csv(io.BytesIO(file_bytes), encoding=enc)

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
    df.columns = [EXPECTED_COLUMNS.get(c, to_snake_case(c)) for c in df.columns]

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
# Helpers PDF — estilos, formatação e células
# ======================================================
styles = getSampleStyleSheet()
STYLE_SECTION = ParagraphStyle("section", parent=styles["Heading4"], fontSize=12, spaceAfter=6)
STYLE_LABEL = ParagraphStyle("label", parent=styles["Normal"], fontSize=9, leading=11)
STYLE_SMALL = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=10)

def fmt_value(v) -> str:
    if pd.isna(v):
        return "—"
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%d/%m/%Y")
    try:
        f = float(v)
        if abs(f - int(f)) < 1e-6:
            return f"{int(f):,}".replace(",", ".")
        return f"{f:.2f}".replace(".", ",")
    except Exception:
        return str(v)

def label_value(label: str, value) -> Paragraph:
    return Paragraph(f"<b>{label}</b>: {fmt_value(value)}", STYLE_LABEL)

def grid_from_pairs(pairs: List[Tuple[str, object]], cols: int = 3) -> Table:
    rows, line = [], []
    for lab, val in pairs:
        line.append(label_value(lab, val))
        if len(line) == cols:
            rows.append(line); line = []
    if line:
        while len(line) < cols:
            line.append(Paragraph("", STYLE_LABEL))
        rows.append(line)
    t = Table(rows)
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    return t

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
    canvas.drawString(20, 15, f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}')
    if contact:
        canvas.drawCentredString(width/2, 15, contact)
    canvas.drawRightString(width - 20, 15, f'Página {canvas.getPageNumber()}')
    canvas.restoreState()

# ======================================================
# Geração do PDF — layout individual conforme mapeamento
# ======================================================
def gerar_pdf_individual(
    df: pd.DataFrame,
    logo_path: Optional[str],
    title: str,
    contact: Optional[str],
    limit_animals: Optional[int] = None
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))

    # Cabeçalho/rodapé
    cb = partial(_draw_header_footer, title=title, contact=contact, logo_path=logo_path)

    elements = []
    n = len(df) if not limit_animals else min(limit_animals, len(df))
    for i in range(n):
        r = df.iloc[i]

        # Topo: Prova de Matriz — Fazenda / Código ABCBRH
        header_tbl = Table([
            [label_value("Fazenda", r.get("customer_id")),
             label_value("Código ABCBRH", r.get("reg_number"))]
        ])
        header_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
            ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements += [Spacer(1, 18), header_tbl, Spacer(1, 8)]

        # Linha Animal + Data nascimento (ao lado)
        animal_tbl = Table([
            [label_value("Animal", r.get("farm_eartag_number")),
             label_value("Data nascimento", r.get("birthdate"))]
        ])
        animal_tbl.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ]))
        elements += [animal_tbl, Spacer(1, 8)]

        # Pedigree (esq) + Último parto / Lactação (dir)
        tbl_pedigree = Table([
            [label_value("Código pai", r.get("sire_code"))],
            [label_value("Pai", r.get("sire_name"))],
            [label_value("Avô", r.get("mgs_name"))],
            [label_value("Bisavô", r.get("mmgs_name"))],
        ])
        tbl_pedigree.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
        ]))
        side_right = Table([
            [label_value("Último parto", r.get("calving_date"))],
            [label_value("Lactação", r.get("lactation_number"))],
        ])
        side_right.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ]))
        two_col = Table([[tbl_pedigree, side_right]], colWidths=[360, None])
        two_col.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        elements += [two_col, Spacer(1, 10)]

        # Índices — substituem OPI / Mérito Líquido / Mérito Queijo
        indices_tbl = Table([[
            label_value("Índice Americano", r.get("us_index")),
            label_value("Meu Índice", r.get("my_index")),
            label_value("Posição Ranking fazenda", r.get("percent_rank")),
        ]])
        indices_tbl.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ]))
        elements += [indices_tbl, Spacer(1, 10)]

        # Produção & Vida
        elements.append(Paragraph("Produção & Vida", STYLE_SECTION))
        prod_pairs = [
            ("Leite (lbs)", r.get("milk")),            # R / PTALeite → Leite (lbs)
            ("Gordura (lbs)", r.get("fat")),           # T
            ("Proteína (lbs)", r.get("protein")),      # V
            ("Vida Produtiva (meses)", r.get("pl")),   # X
        ]
        elements += [grid_from_pairs(prod_pairs, cols=4), Spacer(1, 6)]

        # Saúde & Reprodução (com substituições solicitadas)
        elements.append(Paragraph("Saúde & Reprodução", STYLE_SECTION))
        health_pairs = [
            ("DPR - Taxa de Prenhez (%)", r.get("dpr")),                     # Z
            ("Células Somáticas", r.get("scs")),                              # AB
            ("Facilidade de Parto - Touro(%)", r.get("sce")),                 # AD
            ("Facilidade de Parto - Filhas (%)", r.get("dce")),               # AF (substitui 'Trato Economizado')
            ("Natimortalidade - Touro (%)", r.get("ssb")),                    # AH (substitui 'Índice de Saúde')
            ("Natimortalidade – Filhas", r.get("dsb")),                       # AJ (substitui 'Taxa de Sobrevivência de Novilhas')
            ("CCR - Taxa de Concepção de Vacas (%)", r.get("ccr")),           # AL
            ("HCR - Taxa de Concepção de Novilhas (%)", r.get("hcr")),        # AN
            ("Taxa de Sobrevivência de Vacas (%)", r.get("liv")),             # AP
        ]
        elements += [grid_from_pairs(health_pairs, cols=3), Spacer(1, 6)]

        # Conformação (Tipo)
        elements.append(Paragraph("Conformação", STYLE_SECTION))
        type_pairs = [
            ("Composto Corporal", r.get("bwc")),                 # AR
            ("Composto de Úbere", r.get("udc")),                 # AT
            ("Composto de Pernas e Pés", r.get("flc")),          # AV
            ("Estatura", r.get("sta")),                          # AX
            ("Força Corporal", r.get("str")),                    # AZ
            ("Profundidade Corporal", r.get("bd")),              # BB
            ("Forma Leiteira", r.get("df")),                     # BD
            ("Ângulo de Garupa", r.get("ra")),                   # BF
            ("Largura de Garupa", r.get("rw")),                  # BH
            ("Ângulo de Casco", r.get("fa")),                    # BJ
            ("Pernas Traseiras - Vista Lateral", r.get("rlsv")), # BL
            ("Pernas Traseiras - Vista Traseira", r.get("rlrv")),# BN
            ("Inserção Anterior de Úbere", r.get("fu")),         # BP
            ("Altura de Úbere Posterior", r.get("ruh")),         # BR
            ("Largura de Úbere Posterior", r.get("ruw")),        # BT
            ("Ligamento de Úbere", r.get("uc")),                 # BV
            ("Profundidade de Úbere", r.get("ud")),              # BX
            ("Posicionamento dos Tetos Anteriores", r.get("ftp")),# BZ
            ("Posicionamento dos Tetos Posteriores", r.get("rtp")),# CB
            ("Comprimento de Teto", r.get("tl")),                # CD
        ]
        elements.append(grid_from_pairs(type_pairs, cols=4))

        if i < n - 1:
            elements.append(PageBreak())

    doc.build(elements, onFirstPage=cb, onLaterPages=cb)
    pdf = buf.getvalue()
    buf.close()
    return pdf

# ======================================================
# UI — Sidebar
# ======================================================
with st.sidebar:
    st.header("Upload & Opções")
    uploaded = st.file_uploader("Planilha (CSV/XLSX)", type=["csv","xlsx","xlsm","xls"], key=K("e3_planilha"))
    excel_sheet = st.text_input("Aba do Excel (opcional)", key=K("e3_sheet"))
    logo_file = st.file_uploader("Logotipo (PNG/JPG)", type=["png","jpg","jpeg"], key=K("e3_logo"))
    report_title = st.text_input("Título (cabeçalho)", value="Prova de Matriz", key=K("e3_title"))
    contact_info = st.text_input("Rodapé (contato)", value="Alta Genetics • www.altagenetics.com.br", key=K("e3_contact"))
    limit_animals = st.number_input("Qtd. de animais no PDF", min_value=1, value=20, step=1, key=K("e3_limit"))
    st.divider()
    st.subheader("PDF")
    logo_file = st.file_uploader("Logotipo (PNG/JPG)", type=["png","jpg","jpeg"])
    report_title = st.text_input("Título (cabeçalho)", value="Prova de Matriz")
    contact_info = st.text_input("Rodapé (contato)", value="Alta Genetics • www.altagenetics.com.br")
    limit_animals = st.number_input("Qtd. de animais no PDF", min_value=1, value=20, step=1)

# ======================================================
# Corpo — gera PDF
# ======================================================
msg = st.empty()

# Reaproveita df das etapas anteriores se existir
df: Optional[pd.DataFrame] = None
if "df_etapa2" in st.session_state:
    df = st.session_state["df_etapa2"]
elif "df_etapa1" in st.session_state:
    df = st.session_state["df_etapa1"]

if uploaded:
    try:
        sheet_arg: str | int | None = excel_sheet if excel_sheet.strip() else None
        df = load_table(uploaded, sheet_arg)
        st.session_state["df_etapa3"] = df.copy()
    except Exception as e:
        msg.error(f"❌ Falha na importação: {e}")
        df = None

if df is None:
    st.info("Envie um CSV/XLSX ou carregue antes as Etapas 1/2 no mesmo navegador.")
    st.stop()

msg.success("✅ Dados prontos para gerar PDF.")

# Caminho temporário p/ logo
logo_path = None
if logo_file:
    logo_path = f"temp_logo.{logo_file.name.split('.')[-1]}"
    with open(logo_path, "wb") as f:
        f.write(logo_file.read())

pdf_bytes = gerar_pdf_individual(
    df=df,
    logo_path=logo_path,
    title=report_title,
    contact=contact_info,
    limit_animals=int(limit_animals),
)

st.download_button(
    "📄 Baixar PDF (individual por animal)",
    data=pdf_bytes,
    file_name="relatorio_animais_individual.pdf",
    mime="application/pdf",
)
