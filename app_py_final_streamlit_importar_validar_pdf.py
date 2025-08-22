# app.py — Etapa 3: Importação + Validação + Geração de PDF com logotipo e rodapé
# Objetivo: subir planilha, normalizar cabeçalhos, validar ranges, exibir amostra e gerar relatório PDF personalizado.

from __future__ import annotations
import io
import re
from typing import Optional
from datetime import datetime

import pandas as pd
import streamlit as st
try:
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, LongTable, PageBreak
    )
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfgen import canvas
except ModuleNotFoundError:
    st.error(
        "Dependência ausente para geração de PDF. Adicione **reportlab** e **pillow** ao `requirements.txt` e refaça o deploy."
    )
    st.stop()

# -------------------------------
# Utilidades de normalização
# -------------------------------
EXPECTED_COLUMNS = {"Customer ID": "customer_id", "Reg Number": "reg_number", "ChainNum": "chain_num", "Farm Eartag Number": "farm_eartag_number", "Computer ID": "computer_id", "BirthDate": "birthdate", "Sire Code": "sire_code", "Sire Name": "sire_name", "MGS Code": "mgs_code", "MGS Name": "mgs_name", "MMGS Code": "mmgs_code", "MMGS Name": "mmgs_name", "Calving Date": "calving_date", "Lactation Number": "lactation_number", "US Index": "us_index", "My Index": "my_index", "Percent Rank": "percent_rank", "Milk": "milk", "Fat": "fat", "Protein": "protein", "PL": "pl", "DPR": "dpr", "SCS": "scs", "SCE": "sce", "DCE": "dce", "SSB": "ssb", "DSB": "dsb", "CCR": "ccr", "HCR": "hcr", "LIV": "liv", "BWC": "bwc", "UDC": "udc", "FLC": "flc", "STA": "sta", "STR": "str", "BD": "bd", "DF": "df", "RA": "ra", "RW": "rw", "FA": "fa", "RLSV": "rlsv", "RLRV": "rlrv", "FU": "fu", "RUH": "ruh", "RUW": "ruw", "UC": "uc", "UD": "ud", "FTP": "ftp", "RTP": "rtp", "TL": "tl",}
DATE_COLS = {"birthdate", "calving_date"}
LIKELY_NUMERIC = {"chain_num","computer_id","lactation_number","us_index","my_index","percent_rank","milk","fat","protein","pl","dpr","scs","sce","dce","ssb","dsb","ccr","hcr","liv","bwc","udc","flc","sta","str","bd","df","ra","rw","fa","rlsv","rlrv","fu","ruh","ruw","uc","ud","ftp","rtp","tl"}
VALIDATION_RULES = {"percent_rank": (0, 100),"scs": (1, 5),"dpr": (-10, 10),"milk": (-5000, 20000),"fat": (-200, 1500),"protein": (-200, 1500),}

# -------------------------------
# Funções de leitura
# -------------------------------
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
    enc = guess_encoding_from_bytes(file_bytes) or "utf-8"
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
    return pd.read_csv(bio, encoding=enc)

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
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=False, infer_datetime_format=True)
    for c in LIKELY_NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# -------------------------------
# Validação
# -------------------------------
def validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    issues = []
    for col, (low, high) in VALIDATION_RULES.items():
        if col in df.columns:
            mask = (df[col].notna()) & ((df[col] < low) | (df[col] > high))
            if mask.any():
                problems = df.loc[mask, [col]].copy()
                problems["coluna"] = col
                problems["faixa"] = f"{low}–{high}"
                issues.append(problems)
    if issues:
        return pd.concat(issues, axis=0)
    return pd.DataFrame(columns=["coluna","faixa"])

# -------------------------------
# Funções auxiliares para PDF
# -------------------------------
def rodape(canvas, doc):
    canvas.saveState()
    footer_text = f"Alta Genetics — Relatório gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    width, height = landscape(A4)
    canvas.setFont('Helvetica', 8)
    canvas.drawString(30, 20, footer_text)
    canvas.drawRightString(width-30, 20, f"Página {doc.page}")
    canvas.restoreState()

# -------------------------------
# Geração de PDF (Etapa 3)
# -------------------------------
# -------------------------------
# Geração de PDF (Etapa 3) — com cabeçalho/rodapé
# -------------------------------
from datetime import datetime
from functools import partial


def _draw_header_footer(canvas, doc, title: str, contact: str | None, logo_path: str | None):
    width, height = landscape(A4)
    canvas.saveState()

    # Header line and logo/title
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

    # Footer with date/time, contact, and page number
    canvas.setFont('Helvetica', 9)
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
    canvas.drawString(20, 15, f'Gerado em {now_str}')
    if contact:
        canvas.drawCentredString(width / 2, 15, contact)
    canvas.drawRightString(width - 20, 15, f'Página {canvas.getPageNumber()}')

    canvas.restoreState()


def gerar_pdf(df: pd.DataFrame, logo_path: str | None = None, *, title: str = 'Relatório de Animais — Ranking', contact: str | None = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Spacer(1, 24))

    cols = df.columns.tolist()
    data = [cols] + df[cols].astype(str).values.tolist()
    table = Table(data, repeatRows=1)
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

    cb = partial(_draw_header_footer, title=title, contact=contact, logo_path=logo_path)
    doc.build(elements, onFirstPage=cb, onLaterPages=cb)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# -------------------------------
# UI Streamlit — Etapa 3
# -------------------------------
st.set_page_config(page_title="Importar + Validar + PDF", layout="wide")
st.title("Etapa 3 — Importar, Validar e Gerar PDF com logotipo e rodapé")

with st.sidebar:
    st.header("Upload & Opções")
    uploaded = st.file_uploader("Selecione sua planilha", type=["csv", "xlsx", "xlsm", "xls"])
    preview_rows = st.number_input("Linhas de prévia", min_value=5, max_value=50, value=10, step=5)
    logo_file = st.file_uploader("Logotipo (PNG/JPG)", type=["png","jpg","jpeg"])
    report_title = st.text_input("Título do relatório", value="Relatório de Animais — Ranking")
    contact_info = st.text_input("Contato (rodapé)", value="Alta Genetics • www.altagenetics.com.br • contato@altagenetics.com.br")

if uploaded:
    try:
        df = load_table(uploaded)
        st.success("✅ Importação concluída.")

        st.subheader("Pré-visualização")
        st.dataframe(df.head(int(preview_rows)), use_container_width=True)

        st.subheader("Validação de faixas plausíveis")
        problems = validate_dataframe(df)
        if problems.empty:
            st.success("Nenhum problema encontrado.")
        else:
            st.warning("Valores fora das faixas plausíveis detectados:")
            st.dataframe(problems, use_container_width=True)

        logo_path = None
        if logo_file:
            logo_path = f"temp_logo.{logo_file.name.split('.')[-1]}"
            with open(logo_path, "wb") as f:
                f.write(logo_file.read())
        
        pdf_bytes = gerar_pdf(df, logo_path=logo_path, title=report_title, contact=contact_info)
        st.download_button(
            label="📄 Baixar relatório em PDF",
            data=pdf_bytes,
            file_name="relatorio_animais.pdf",
            mime="application/pdf",
        )

    except Exception as e:
        st.error(f"❌ Falha ao importar/validar/gerar PDF: {e}")
else:
    st.info("Faça o upload de um arquivo .csv ou .xlsx na barra lateral para começar.")
