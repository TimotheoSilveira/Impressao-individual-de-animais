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

# app_etapa2.py — Etapa 2: Validação de dados
# Objetivo: importar planilha, validar esquema/tipos/faixas, checar duplicidades e exportar relatório de inconsistências.


import io
import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Tuple, Dict, List

import pandas as pd
import streamlit as st

# --- chaves únicas para widgets (evita conflito de IDs) ---
APP = "final"  # pode trocar por outro prefixo único do seu app

def K(name: str) -> str:
    """Gera uma chave única e estável para widgets do Streamlit."""
    return f"{APP}:{name}"

# ======================================================
# Config da página
# ======================================================
st.set_page_config(page_title="Etapa 2 — Validação", layout="wide")
st.title("Etapa 2 — Validação de Dados")
st.caption("Validação de esquema, tipos, faixas plausíveis e duplicidades — com exportação de inconsistências.")

# ======================================================
# Dicionário de colunas conhecidas e conjuntos auxiliares
# (iguais à Etapa 1 para manter consistência)
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

# ======================================================
# Import helpers (mesmos da Etapa 1, para rodar isolado)
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
        return chardet.detect(data).get("encoding")
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
        pass
    bio = io.BytesIO(file_bytes)
    return pd.read_csv(bio, sep="\t", encoding=enc)

def load_table(uploaded_file, sheet: str | int | None = None) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    content = uploaded_file.read()
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(io.BytesIO(content), sheet_name=sheet if sheet is not None else 0, engine="openpyxl")
    else:
        df = read_csv_auto(content)

    # cabeçalhos
    df.columns = normalize_header(df.columns)
    keep = [c for c in df.columns if c and not str(c).lower().startswith("unnamed")]
    df = df[keep]

    # padroniza nomes
    df.columns = [EXPECTED_COLUMNS.get(c, to_snake_case(c)) for c in df.columns]

    # tipos
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in LIKELY_NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# ======================================================
# Validação
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

@dataclass
class RangeRule:
    low: Optional[float] = None
    high: Optional[float] = None
    label: str = ""


# ======================================================
# Sidebar
# ======================================================
with st.sidebar:
    st.header("Upload & Parâmetros")
    uploaded = st.file_uploader("Planilha (CSV/XLSX)", type=["csv","xlsx","xlsm","xls"], key=K("e2_planilha"))
    excel_sheet = st.text_input("Aba do Excel (opcional)", key=K("e2_sheet"))
    min_birth_year = st.number_input("Ano mínimo de nascimento", min_value=1970, max_value=2100, value=1990, key=K("e2_birth_y"))
    min_calving_year = st.number_input("Ano mínimo de parto", min_value=1990, max_value=2100, value=2000, key=K("e2_calv_y"))
    custom_keys = st.multiselect("Chaves para detectar duplicados", ["reg_number","farm_eartag_number","customer_id","computer_id"], default=["reg_number","farm_eartag_number"], key=K("e2_dup_keys"))
    use_extra = st.checkbox("Ativar checagem de faixas plausíveis adicionais", value=True, key=K("e2_extra"))
    st.divider()
    st.subheader("Parâmetros de datas")
    min_birth_year = st.number_input("Ano mínimo de nascimento", min_value=1970, max_value=datetime.now().year, value=1990)
    min_calving_year = st.number_input("Ano mínimo de parto", min_value=1990, max_value=datetime.now().year, value=2000)
    st.divider()
    st.subheader("Duplicidades")
    custom_keys = st.multiselect(
        "Chaves para detectar duplicados",
        options=["reg_number","farm_eartag_number","customer_id","computer_id"],
        default=["reg_number","farm_eartag_number"],
    )
    st.divider()
    st.subheader("Faixas adicionais (opcionais)")
    use_extra = st.checkbox("Ativar checagem de faixas plausíveis adicionais", value=True)
    if use_extra:
        milk_low  = st.number_input("Leite (lbs) — mínimo", value=-5000)
        milk_high = st.number_input("Leite (lbs) — máximo", value=20000)
        fat_low   = st.number_input("Gordura (lbs) — mínimo", value=-200)
        fat_high  = st.number_input("Gordura (lbs) — máximo", value=1500)
        prot_low  = st.number_input("Proteína (lbs) — mínimo", value=-200)
        prot_high = st.number_input("Proteína (lbs) — máximo", value=1500)
        pl_low    = st.number_input("Vida Produtiva (meses) — mínimo", value=-20)
        pl_high   = st.number_input("Vida Produtiva (meses) — máximo", value=120)
    preview_rows = st.number_input("Linhas da prévia", min_value=5, max_value=100, value=10, step=5)

# ======================================================
# Corpo — lógica
# ======================================================
msg = st.empty()

def build_extra_ranges() -> Dict[str, RangeRule]:
    if not use_extra:
        return {}
    return {
        "milk": RangeRule(milk_low, milk_high, "Leite (lbs)"),
        "fat": RangeRule(fat_low, fat_high, "Gordura (lbs)"),
        "protein": RangeRule(prot_low, prot_high, "Proteína (lbs)"),
        "pl": RangeRule(pl_low, pl_high, "Vida Produtiva (meses)"),
    }

# Permitir reaproveitar df da Etapa 1 (se rodou no mesmo navegador)
df: Optional[pd.DataFrame] = None
if "df_etapa1" in st.session_state:
    df = st.session_state["df_etapa1"]

if uploaded:
    try:
        sheet_arg: str | int | None = excel_sheet if excel_sheet.strip() else None
        df = load_table(uploaded, sheet_arg)
    except Exception as e:
        msg.error(f"❌ Falha na importação: {e}")
        df = None

if df is None:
    st.info("Faça o upload de um arquivo .csv/.xlsx (ou carregue a Etapa 1 antes no mesmo navegador).")
    st.stop()

# Resumo
msg.success("✅ Dados carregados.")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Linhas", f"{len(df):,}")
with c2:
    st.metric("Colunas", f"{len(df.columns)}")
with c3:
    st.metric("Com datas", f"{sum(c in df.columns for c in DATE_COLS)} / {len(DATE_COLS)}")

st.subheader("Pré-visualização")
st.dataframe(df.head(int(preview_rows)), use_container_width=True)

# Esquema
st.subheader("Validação de Esquema")
missing, unknown = validate_schema(df)
if missing:
    st.error("Colunas obrigatórias ausentes: " + ", ".join(missing))
else:
    st.success("Esquema mínimo OK (colunas essenciais presentes).")
if unknown:
    with st.expander("Colunas não mapeadas (aceitas, mas fora do dicionário)"):
        st.code(", ".join(unknown))

# Regras
def validate_types_and_ranges(
    df: pd.DataFrame,
    today,
    min_birth_year: int,
    min_calving_year: int,
    extra_ranges: dict[str, "RangeRule"] | None = None,
    dup_keys: list[str] | None = None,
) -> pd.DataFrame:
    """Retorna um DataFrame de issues: index, coluna, valor, problema, gravidade."""
    issues = []

    def add_issue(idx, col, val, msg, sev="erro"):
        issues.append({"index": int(idx), "coluna": col, "valor": val, "problema": msg, "gravidade": sev})

    # --- percent_rank em [0, 100] ---
    if "percent_rank" in df.columns:
        s = pd.to_numeric(df["percent_rank"], errors="coerce")
        mask = s.notna() & ((s < 0) | (s > 100))
        for idx, val in s[mask].items():
            add_issue(idx, "percent_rank", val, "Fora do intervalo [0, 100]")

    # --- lactation_number inteiro >= 1 ---
    if "lactation_number" in df.columns:
        s = pd.to_numeric(df["lactation_number"], errors="coerce")
        mask = s.notna() & ((s < 1) | (s % 1 != 0))
        for idx, val in s[mask].items():
            add_issue(idx, "lactation_number", val, "Deve ser inteiro ≥ 1")

  
    if "birthdate" in df.columns:
        s = _as_naive_ts(df["birthdate"])
        mask = s.notna() & ((s < min_birth_ts) | (s > today_ts))
        for idx, val in s[mask].items():
            add_issue(idx, "birthdate", str(val), f"Fora de {min_birth_ts.date()}..{today_ts.date()}")

    if "calving_date" in df.columns:
        s = _as_naive_ts(df["calving_date"])
        mask = s.notna() & ((s < min_calving_ts) | (s > today_ts))
        for idx, val in s[mask].items():
            add_issue(idx, "calving_date", str(val), f"Fora de {min_calving_ts.date()}..{today_ts.date()}")

    if {"birthdate","calving_date"}.issubset(df.columns):
        b = _as_naive_ts(df["birthdate"])
        c = _as_naive_ts(df["calving_date"])
        both = pd.DataFrame({"b": b, "c": c}).dropna()
        mask = both["c"] < both["b"]
        for idx, row in both[mask].iterrows():
            add_issue(idx, "calving_date", str(row["c"]), "Calving < Birth (inconsistente)")

    # --- alertas de SCS ---
    if "scs" in df.columns:
        s = pd.to_numeric(df["scs"], errors="coerce")
        for idx, val in s[s > 3.0].items():
            add_issue(idx, "scs", val, "> 3,00 (evitar recomendar)", sev="alerta")
        for idx, val in s[(s > 2.8) & (s <= 3.0)].items():
            add_issue(idx, "scs", val, "> 2,80 (atenção)", sev="alerta")

    # --- IDs vazios ---
    for idc in ("reg_number","farm_eartag_number"):
        if idc in df.columns:
            s = df[idc].astype("string")
            mask = s.isna() | (s.str.strip() == "")
            for idx, val in s[mask].items():
                add_issue(idx, idc, val, "Identificador vazio")

    # --- Duplicidades ---
    keys = [c for c in (dup_keys or ["reg_number","farm_eartag_number"]) if c in df.columns]
    if keys:
        dup_mask = df.duplicated(subset=keys, keep=False)
        for idx in df.index[dup_mask]:
            add_issue(idx, "+".join(keys), "duplicado", "Possível duplicidade pela(s) chave(s)")

    # --- Faixas adicionais (opcionais) ---
    extra_ranges = extra_ranges or {}
    for col, rule in extra_ranges.items():
        if col in df.columns and (rule.low is not None or rule.high is not None):
            s = pd.to_numeric(df[col], errors="coerce")
            mask = s.notna() & (
                ((rule.low is not None) & (s < rule.low)) |
                ((rule.high is not None) & (s > rule.high))
            )
            for idx, val in s[mask].items():
                add_issue(idx, col, val, f"Fora da faixa {rule.low}..{rule.high}", sev="alerta")

    return pd.DataFrame(issues)

# --- Validação de Tipos/Faixas/Duplicidades ---
# (garante que issues_df SEMPRE existe, evitando NameError)
issues_df = pd.DataFrame(columns=["index","coluna","valor","problema","gravidade"])

try:
    issues_df = validate_types_and_ranges(
        df=df,
        today=date.today(),
        min_birth_year=int(min_birth_year),
        min_calving_year=int(min_calving_year),
        extra_ranges=build_extra_ranges() if 'build_extra_ranges' in globals() else {},
        dup_keys=custom_keys if 'custom_keys' in globals() else None,
    )
except Exception as e:
    st.error(f"❌ Falha na validação: {e}")
    # mantém issues_df como DataFrame vazio



if issues_df.empty:
    st.success("Nenhuma inconsistência detectada pelas regras atuais.")
else:
    st.warning(f"Foram encontradas {len(issues_df)} inconsistências.")
    # Filtros
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        col_filter = st.selectbox("Filtrar por coluna", options=["(todas)"] + sorted(issues_df["coluna"].unique().tolist()))
    with c2:
        sev_filter = st.selectbox("Gravidade", options=["(todas)","erro","alerta"])
    with c3:
        query = st.text_input("Contém (texto livre em problema/valor)")
    filtered = issues_df.copy()
    if col_filter != "(todas)":
        filtered = filtered[filtered["coluna"] == col_filter]
    if sev_filter != "(todas)":
        filtered = filtered[filtered["gravidade"] == sev_filter]
    if query.strip():
        q = query.strip().lower()
        filtered = filtered[
            filtered["problema"].str.lower().str.contains(q) |
            filtered["valor"].astype(str).str.lower().str.contains(q)
        ]
    st.dataframe(filtered, use_container_width=True)
    st.download_button(
        "Baixar inconsistências (CSV)",
        data=issues_df.to_csv(index=False).encode("utf-8"),
        file_name="inconsistencias.csv",
        mime="text/csv",
    )
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
# app_etapa3b.py — Etapa 3B: PDF em TABELA (só colunas úteis + rótulos do mapeamento)
# - Importa CSV/XLSX (ou reaproveita df da Etapa 1/2 via session_state)
# - Seleciona apenas as colunas que NÃO são "Desconsiderar"
# - Renomeia cabeçalhos no PDF conforme seu mapeamento
# - Divide em múltiplas páginas se muitas colunas (controle "Máx. colunas por página")

import io, re
from typing import Optional, Iterable, List
from datetime import datetime

import pandas as pd
import streamlit as st


# --- chaves únicas para widgets (evita conflito de IDs) ---
APP = "final"  # pode trocar por outro prefixo único do seu app

def K(name: str) -> str:
    """Gera uma chave única e estável para widgets do Streamlit."""
    return f"{APP}:{name}"


# ---------- Guard para PDF ----------
try:
    from reportlab.platypus import SimpleDocTemplate, LongTable, TableStyle, Spacer, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
except ModuleNotFoundError:
    st.error("Faltam dependências para PDF. Instale: reportlab e pillow.")
    st.stop()

# ============== Config página ==============
st.set_page_config(page_title="Etapa 3B — PDF em Tabela", layout="wide")
st.title("Etapa 3B — PDF em Tabela (colunas úteis)")
st.caption("Gera um PDF tabular com rótulos conforme o mapeamento definido.")

# ============== Import helpers (compatível com Etapas 1/2) ==============
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
DATE_COLS = {"birthdate","calving_date"}
LIKELY_NUMERIC = {
    "lactation_number","us_index","my_index","percent_rank","milk","fat","protein","pl","dpr","scs",
    "sce","dce","ssb","dsb","ccr","hcr","liv","bwc","udc","flc","sta","str","bd","df","ra","rw","fa",
    "rlsv","rlrv","fu","ruh","ruw","uc","ud","ftp","rtp","tl"
}

def to_snake_case(name: str) -> str:
    n = re.sub(r"\s+"," ", str(name).strip())
    n = n.replace("/"," ").replace("-"," ")
    n = re.sub(r"[^\w\s]","", n)
    return n.lower().strip().replace(" ","_")

def normalize_header(cols) -> list[str]:
    return [("" if c is None else re.sub(r"\s+"," ", str(c).strip())) for c in cols]

def guess_encoding_from_bytes(data: bytes) -> Optional[str]:
    try:
        import chardet; return chardet.detect(data).get("encoding")
    except Exception:
        return None

def read_csv_auto(b: bytes) -> pd.DataFrame:
    enc = guess_encoding_from_bytes(b) or "utf-8-sig"
    for sep in [None, ";", ",", "\t"]:
        bio = io.BytesIO(b)
        try:
            return pd.read_csv(bio, sep=sep, engine="python" if sep is None else None, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(io.BytesIO(b), encoding=enc)

def load_table(uploaded_file, sheet: str|int|None=None) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    if name.endswith((".xlsx",".xlsm",".xls")):
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet if sheet else 0, engine="openpyxl")
    else:
        df = read_csv_auto(data)
    df.columns = normalize_header(df.columns)
    df = df[[c for c in df.columns if c and not str(c).lower().startswith("unnamed")]]
    df.columns = [EXPECTED_COLUMNS.get(c, to_snake_case(c)) for c in df.columns]
    for c in DATE_COLS:
        if c in df.columns: df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in LIKELY_NUMERIC:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# ============== Colunas úteis → Rótulos (SEU mapeamento) ==============
PDF_LABELS = {
    # Identificação
    "customer_id": "Fazenda",
    "reg_number": "Código ABCBRH",      # (Reg. genômico)
    "farm_eartag_number": "Animal",
    "birthdate": "Data nascimento",

    # Pedigree e eventos
    "sire_code": "Código pai",
    "sire_name": "Pai",
    "mgs_name": "Avô",
    "mmgs_name": "Bisavô",
    "calving_date": "Último parto",
    "lactation_number": "Lactação",

    # Índices (substituem OPI / Méritos)
    "us_index": "Índice Americano",
    "my_index": "Meu Índice",
    "percent_rank": "Posição Ranking fazenda",

    # Produção & Vida
    "milk": "Leite (lbs)",
    "fat": "Gordura (lbs)",
    "protein": "Proteína (lbs)",
    "pl": "Vida Produtiva (meses)",

    # Saúde & Reprodução (substituições solicitadas)
    "dpr": "DPR - Taxa de Prenhez (%)",
    "scs": "Células Somáticas",
    "sce": "Facilidade de Parto - Touro(%)",
    "dce": "Facilidade de Parto - Filhas (%)",
    "ssb": "Natimortalidade - Touro (%)",
    "dsb": "Natimortalidade – Filhas",
    "ccr": "CCR - Taxa de Concepção de Vacas (%)",
    "hcr": "HCR - Taxa de Concepção de Novilhas (%)",
    "liv": "Taxa de Sobrevivência de Vacas (%)",

    # Conformação (Tipo)
    "bwc": "Composto Corporal",
    "udc": "Composto de Úbere",
    "flc": "Composto de Pernas e Pés",
    "sta": "Estatura",
    "str": "Força Corporal",
    "bd": "Profundidade Corporal",
    "df": "Forma Leiteira",
    "ra": "Ângulo de Garupa",
    "rw": "Largura de Garupa",
    "fa": "Ângulo de Casco",
    "rlsv": "Pernas Traseiras - Vista Lateral",
    "rlrv": "Pernas Traseiras - Vista Traseira",
    "fu": "Inserção Anterior de Úbere",
    "ruh": "Altura de Úbere Posterior",
    "ruw": "Largura de Úbere Posterior",
    "uc": "Ligamento de Úbere",
    "ud": "Profundidade de Úbere",
    "ftp": "Posicionamento dos Tetos Anteriores",
    "rtp": "Posicionamento dos Tetos Posteriores",
    "tl": "Comprimento de Teto",
}

# Grupos (para você poder escolher o que entra)
GROUPS = {
    "Identificação": ["customer_id","reg_number","farm_eartag_number","birthdate"],
    "Pedigree & Eventos": ["sire_code","sire_name","mgs_name","mmgs_name","calving_date","lactation_number"],
    "Índices": ["us_index","my_index","percent_rank"],
    "Produção & Vida": ["milk","fat","protein","pl"],
    "Saúde & Reprodução": ["dpr","scs","sce","dce","ssb","dsb","ccr","hcr","liv"],
    "Conformação": ["bwc","udc","flc","sta","str","bd","df","ra","rw","fa","rlsv","rlrv","fu","ruh","ruw","uc","ud","ftp","rtp","tl"],
}

# ============== Sidebar ==============
with st.sidebar:
    st.header("Upload & Filtros")
    uploaded = st.file_uploader("Planilha (CSV/XLSX)", type=["csv","xlsx","xlsm","xls"], key=K("e3b_planilha"))
    excel_sheet = st.text_input("Aba do Excel (opcional)", key=K("e3b_sheet"))
    sort_col = st.selectbox("Ordenar por", options=["(nenhum)"] + list(PDF_LABELS.keys()), key=K("e3b_sort"))
    max_cols_per_page = st.slider("Máx. colunas por página (PDF)", 6, 20, 10, key=K("e3b_maxcols"))
    limit_rows = st.number_input("Limitar linhas (0 = todas)", min_value=0, value=0, step=10, key=K("e3b_limit"))
    st.divider()

    st.subheader("Grupos a incluir")
    chosen_groups = []
    for g in GROUPS:
        if st.checkbox(g, True):
            chosen_groups.append(g)

    st.divider()
    sort_col = st.selectbox("Ordenar por", options=["(nenhum)"] + list(PDF_LABELS.keys()))
    max_cols_per_page = st.slider("Máx. colunas por página (PDF)", 6, 20, 10)
    limit_rows = st.number_input("Limitar linhas (0 = todas)", min_value=0, value=0, step=10)

# ============== Leitura de dados ==============
msg = st.empty()

df: Optional[pd.DataFrame] = None
if "df_etapa2" in st.session_state:
    df = st.session_state["df_etapa2"]
elif "df_etapa1" in st.session_state:
    df = st.session_state["df_etapa1"]

if uploaded:
    try:
        sheet_arg = excel_sheet if excel_sheet.strip() else None
        df = load_table(uploaded, sheet_arg)
        st.session_state["df_etapa3b"] = df.copy()
    except Exception as e:
        msg.error(f"❌ Falha na importação: {e}")
        df = None

if df is None:
    st.info("Envie um CSV/XLSX ou carregue antes as Etapas 1/2 no mesmo navegador.")
    st.stop()

# ============== Seleção de colunas úteis ==============
selected_cols: List[str] = []
for g in chosen_groups:
    selected_cols += GROUPS[g]
# mantém apenas colunas que existem no DF
selected_cols = [c for c in selected_cols if c in df.columns]

if not selected_cols:
    st.error("Nenhuma coluna selecionada/existente. Marque ao menos um grupo.")
    st.stop()

# ordenar, limitar
work = df.copy()
if sort_col in work.columns:
    work = work.sort_values(by=sort_col, kind="stable")
if limit_rows and limit_rows > 0:
    work = work.head(int(limit_rows))

# ============== Funções PDF ==============
def fmt_value(v) -> str:
    if pd.isna(v): return "—"
    if isinstance(v, pd.Timestamp): return v.strftime("%d/%m/%Y")
    try:
        f = float(v)
        if abs(f - int(f)) < 1e-6: return f"{int(f):,}".replace(",", ".")
        return f"{f:.2f}".replace(".", ",")
    except Exception:
        return str(v)

def split_columns(cols: List[str], max_cols: int) -> Iterable[List[str]]:
    for i in range(0, len(cols), max_cols):
        yield cols[i:i+max_cols]

def build_table(df_slice: pd.DataFrame, cols: List[str]) -> LongTable:
    headers = [PDF_LABELS.get(c, c) for c in cols]
    data = [headers] + [[fmt_value(v) for v in row] for row in df_slice[cols].itertuples(index=False, name=None)]
    tbl = LongTable(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
    ]))
    return tbl

def draw_header_footer(canvas, doc):
    width, height = landscape(A4)
    canvas.saveState()
    canvas.setFont('Helvetica-Bold', 12)
    canvas.drawString(20, height-25, "Relatório — Tabela (colunas úteis)")
    canvas.setStrokeColor(colors.lightgrey)
    canvas.line(20, height-30, width-20, height-30)
    canvas.setFont('Helvetica', 9)
    canvas.drawString(20, 15, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    canvas.drawRightString(width-20, 15, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()

def gerar_pdf_tabela(df_full: pd.DataFrame, cols_all: List[str], max_cols: int = 10) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    elements = [Spacer(1, 24)]
    col_slices = list(split_columns(cols_all, max_cols))
    for i, cols in enumerate(col_slices, start=1):
        elements.append(build_table(df_full, cols))
        if i < len(col_slices):
            elements.append(PageBreak())
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    pdf = buf.getvalue(); buf.close()
    return pdf

# ============== Preview e Download ==============
st.success(f"✅ {len(work)} linhas • {len(selected_cols)} colunas úteis selecionadas.")
st.dataframe(work[selected_cols].head(20), use_container_width=True)

pdf_bytes = gerar_pdf_tabela(work, selected_cols, max_cols=int(max_cols_per_page))
st.download_button(
    "📄 Baixar PDF (tabela — colunas úteis)",
    data=pdf_bytes,
    file_name="relatorio_tabela_colunas_uteis.pdf",
    mime="application/pdf",
)
# app_etapa4.py — Etapa 4: Exportar XLSX em abas por grupo
# Grupos: Identificação, Índices, Produção, Saúde, Conformação
# Lê CSV/XLSX (ou reaproveita df das etapas anteriores via session_state)
# Gera um .xlsx em memória com abas e rótulos conforme seu mapeamento

import io, re
from typing import Optional, Dict, List
from datetime import datetime

import pandas as pd
import streamlit as st

# --- chaves únicas para widgets (evita conflito de IDs) ---
APP = "final"  # pode trocar por outro prefixo único do seu app

def K(name: str) -> str:
    """Gera uma chave única e estável para widgets do Streamlit."""
    return f"{APP}:{name}"


# =========================================
# Config página
# =========================================
st.set_page_config(page_title="Etapa 4 — Exportar XLSX (abas por grupo)", layout="wide")
st.title("Etapa 4 — Exportar XLSX (abas por grupo)")
st.caption("Cria um arquivo .xlsx com abas: Identificação, Índices, Produção, Saúde e Conformação.")

# =========================================
# Mapeamentos (iguais ao que usamos no PDF)
# =========================================
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
DATE_COLS = {"birthdate","calving_date"}
LIKELY_NUMERIC = {
    "lactation_number","us_index","my_index","percent_rank","milk","fat","protein","pl","dpr","scs",
    "sce","dce","ssb","dsb","ccr","hcr","liv","bwc","udc","flc","sta","str","bd","df","ra","rw","fa",
    "rlsv","rlrv","fu","ruh","ruw","uc","ud","ftp","rtp","tl"
}

# Rótulos amigáveis (iguais ao PDF)
LABELS = {
    # Identificação
    "customer_id": "Fazenda",
    "reg_number": "Código ABCBRH",
    "farm_eartag_number": "Animal",
    "birthdate": "Data nascimento",
    # Índices
    "us_index": "Índice Americano",
    "my_index": "Meu Índice",
    "percent_rank": "Posição Ranking fazenda",
    # Produção & Vida
    "milk": "Leite (lbs)",
    "fat": "Gordura (lbs)",
    "protein": "Proteína (lbs)",
    "pl": "Vida Produtiva (meses)",
    # Saúde & Reprodução
    "dpr": "DPR - Taxa de Prenhez (%)",
    "scs": "Células Somáticas",
    "sce": "Facilidade de Parto - Touro(%)",
    "dce": "Facilidade de Parto - Filhas (%)",
    "ssb": "Natimortalidade - Touro (%)",
    "dsb": "Natimortalidade – Filhas",
    "ccr": "CCR - Taxa de Concepção de Vacas (%)",
    "hcr": "HCR - Taxa de Concepção de Novilhas (%)",
    "liv": "Taxa de Sobrevivência de Vacas (%)",
    # Conformação
    "bwc": "Composto Corporal",
    "udc": "Composto de Úbere",
    "flc": "Composto de Pernas e Pés",
    "sta": "Estatura",
    "str": "Força Corporal",
    "bd": "Profundidade Corporal",
    "df": "Forma Leiteira",
    "ra": "Ângulo de Garupa",
    "rw": "Largura de Garupa",
    "fa": "Ângulo de Casco",
    "rlsv": "Pernas Traseiras - Vista Lateral",
    "rlrv": "Pernas Traseiras - Vista Traseira",
    "fu": "Inserção Anterior de Úbere",
    "ruh": "Altura de Úbere Posterior",
    "ruw": "Largura de Úbere Posterior",
    "uc": "Ligamento de Úbere",
    "ud": "Profundidade de Úbere",
    "ftp": "Posicionamento dos Tetos Anteriores",
    "rtp": "Posicionamento dos Tetos Posteriores",
    "tl": "Comprimento de Teto",
}

GROUPS = {
    "Identificação": ["customer_id","reg_number","farm_eartag_number","birthdate"],
    "Índices": ["us_index","my_index","percent_rank"],
    "Produção": ["milk","fat","protein","pl"],
    "Saúde": ["dpr","scs","sce","dce","ssb","dsb","ccr","hcr","liv"],
    "Conformação": ["bwc","udc","flc","sta","str","bd","df","ra","rw","fa","rlsv","rlrv","fu","ruh","ruw","uc","ud","ftp","rtp","tl"],
}

# =========================================
# Import helpers (autônomo)
# =========================================
def to_snake_case(name: str) -> str:
    n = re.sub(r"\s+"," ", str(name).strip())
    n = n.replace("/"," ").replace("-"," ")
    n = re.sub(r"[^\w\s]","", n)
    return n.lower().strip().replace(" ","_")

def normalize_header(cols) -> list[str]:
    return [("" if c is None else re.sub(r"\s+"," ", str(c).strip())) for c in cols]

def guess_encoding_from_bytes(data: bytes) -> Optional[str]:
    try:
        import chardet; return chardet.detect(data).get("encoding")
    except Exception:
        return None

def read_csv_auto(b: bytes) -> pd.DataFrame:
    enc = guess_encoding_from_bytes(b) or "utf-8-sig"
    for sep in [None, ";", ",", "\t"]:
        bio = io.BytesIO(b)
        try:
            return pd.read_csv(bio, sep=sep, engine="python" if sep is None else None, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(io.BytesIO(b), encoding=enc)

def load_table(uploaded_file, sheet: str|int|None=None) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    if name.endswith((".xlsx",".xlsm",".xls")):
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet if sheet else 0, engine="openpyxl")
    else:
        df = read_csv_auto(data)
    df.columns = normalize_header(df.columns)
    df = df[[c for c in df.columns if c and not str(c).lower().startswith("unnamed")]]
    df.columns = [EXPECTED_COLUMNS.get(c, to_snake_case(c)) for c in df.columns]
    for c in DATE_COLS:
        if c in df.columns: df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in LIKELY_NUMERIC:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# =========================================
# Sidebar
# =========================================
with st.sidebar:
    st.header("Upload & Opções")
    uploaded = st.file_uploader("Planilha (CSV/XLSX)", type=["csv","xlsx","xlsm","xls"], key=K("e4_planilha"))
    excel_sheet = st.text_input("Aba do Excel (opcional)", key=K("e4_sheet"))
    sort_col = st.selectbox("Ordenar por (opcional)", options=["(nenhum)"] + sum(GROUPS.values(), []), key=K("e4_sort"))
    limit_rows = st.number_input("Limitar linhas (0 = todas)", min_value=0, value=0, step=10, key=K("e4_limit"))
    st.divider()
    st.subheader("Grupos a incluir")
    chosen = []
    for g in GROUPS:
        if st.checkbox(g, True):
            chosen.append(g)
    st.divider()
    sort_col = st.selectbox("Ordenar por (opcional)", options=["(nenhum)"] + sum(GROUPS.values(), []))
    limit_rows = st.number_input("Limitar linhas (0 = todas)", min_value=0, value=0, step=10)

msg = st.empty()

# Reusa df de etapas anteriores se existir
df: Optional[pd.DataFrame] = None
if "df_etapa3b" in st.session_state:
    df = st.session_state["df_etapa3b"]
elif "df_etapa2" in st.session_state:
    df = st.session_state["df_etapa2"]
elif "df_etapa1" in st.session_state:
    df = st.session_state["df_etapa1"]

if uploaded:
    try:
        sheet_arg = excel_sheet if excel_sheet.strip() else None
        df = load_table(uploaded, sheet_arg)
        st.session_state["df_etapa4"] = df.copy()
    except Exception as e:
        msg.error(f"❌ Falha na importação: {e}")
        df = None

if df is None:
    st.info("Envie um CSV/XLSX ou carregue uma das etapas anteriores no mesmo navegador.")
    st.stop()

msg.success(f"✅ Dados carregados ({len(df)} linhas, {len(df.columns)} colunas).")

# =========================================
# Monta DFs por grupo (apenas colunas existentes)
# =========================================
def group_df(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    real = [c for c in cols if c in df.columns]
    out = df[real].copy()
    return out.rename(columns={c: LABELS.get(c, c) for c in real})

# aplica ordenação/limite antes de fatiar
work = df.copy()
if sort_col in work.columns:
    work = work.sort_values(by=sort_col, kind="stable")
if limit_rows and limit_rows > 0:
    work = work.head(int(limit_rows))

sheets: Dict[str, pd.DataFrame] = {}
for g in chosen:
    gdf = group_df(work, GROUPS[g])
    if not gdf.empty:
        sheets[g] = gdf

if not sheets:
    st.error("Nenhum grupo/coluna selecionado(a). Marque ao menos um grupo.")
    st.stop()

# Preview
tabs = st.tabs(list(sheets.keys()))
for tab, (name, gdf) in zip(tabs, sheets.items()):
    with tab:
        st.subheader(name)
        st.dataframe(gdf.head(20), use_container_width=True)

# =========================================
# Exporta XLSX (xlsxwriter se disponível; senão openpyxl)
# =========================================
def export_xlsx(sheets: Dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    engine = "xlsxwriter"
    try:
        with pd.ExcelWriter(buf, engine=engine) as writer:
            for sheet_name, data in sheets.items():
                data.to_excel(writer, sheet_name=sheet_name[:31], index=False)
                # autoajuste de largura (xlsxwriter)
                ws = writer.sheets[sheet_name[:31]]
                for i, col in enumerate(data.columns):
                    max_len = max([len(str(col))] + [len(str(x)) for x in data[col].head(200)])
                    ws.set_column(i, i, min(max(10, max_len + 2), 40))
            writer.close()
        return buf.getvalue()
    except Exception:
        # fallback para openpyxl
        buf.seek(0); buf.truncate(0)
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for sheet_name, data in sheets.items():
                data.to_excel(writer, sheet_name=sheet_name[:31], index=False)
                ws = writer.sheets[sheet_name[:31]]
                # autoajuste simples
                for col_cells in ws.columns:
                    max_len = 10
                    col_letter = col_cells[0].column_letter
                    for cell in col_cells[:200]:
                        if cell.value is not None:
                            max_len = max(max_len, len(str(cell.value)))
                    ws.column_dimensions[col_letter].width = min(max_len + 2, 40)
            writer.close()
        return buf.getvalue()

xlsx_bytes = export_xlsx(sheets)

st.download_button(
    "⬇️ Baixar XLSX (abas por grupo)",
    data=xlsx_bytes,
    file_name=f"export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
# app_etapa4b.py — Etapa 4B: Exportar XLSX + PDF (pacote completo)
# - Lê CSV/XLSX (ou reaproveita df das etapas anteriores via session_state)
# - Seleciona grupos/colunas, aplica rótulos padronizados
# - Gera XLSX (abas por grupo) e PDF (tabela) com os mesmos rótulos
# - Disponibiliza downloads individuais e um ZIP contendo ambos

import io, re, zipfile
from typing import Optional, Dict, List, Iterable
from datetime import datetime

import pandas as pd
import streamlit as st

# --- chaves únicas para widgets (evita conflito de IDs) ---
APP = "final"  # pode trocar por outro prefixo único do seu app

def K(name: str) -> str:
    """Gera uma chave única e estável para widgets do Streamlit."""
    return f"{APP}:{name}"



# ====== Guard para PDF ======
try:
    from reportlab.platypus import SimpleDocTemplate, LongTable, TableStyle, Spacer, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
except ModuleNotFoundError:
    st.error("Faltam dependências para PDF. Instale: reportlab e pillow.")
    st.stop()

# ====== Config página ======
st.set_page_config(page_title="Etapa 4B — XLSX + PDF (pacote)", layout="wide")
st.title("Etapa 4B — Exportar XLSX + PDF (pacote completo)")
st.caption("Mesmos grupos e rótulos usados nas etapas anteriores; opção de baixar tudo em um ZIP.")

# ====== Mapeamentos/Conjuntos (iguais aos anteriores) ======
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
DATE_COLS = {"birthdate","calving_date"}
LIKELY_NUMERIC = {
    "lactation_number","us_index","my_index","percent_rank","milk","fat","protein","pl","dpr","scs",
    "sce","dce","ssb","dsb","ccr","hcr","liv","bwc","udc","flc","sta","str","bd","df","ra","rw","fa",
    "rlsv","rlrv","fu","ruh","ruw","uc","ud","ftp","rtp","tl"
}

LABELS = {
    # Identificação
    "customer_id": "Fazenda",
    "reg_number": "Código ABCBRH",
    "farm_eartag_number": "Animal",
    "birthdate": "Data nascimento",
    # Índices
    "us_index": "Índice Americano",
    "my_index": "Meu Índice",
    "percent_rank": "Posição Ranking fazenda",
    # Produção & Vida
    "milk": "Leite (lbs)",
    "fat": "Gordura (lbs)",
    "protein": "Proteína (lbs)",
    "pl": "Vida Produtiva (meses)",
    # Saúde & Reprodução
    "dpr": "DPR - Taxa de Prenhez (%)",
    "scs": "Células Somáticas",
    "sce": "Facilidade de Parto - Touro(%)",
    "dce": "Facilidade de Parto - Filhas (%)",
    "ssb": "Natimortalidade - Touro (%)",
    "dsb": "Natimortalidade – Filhas",
    "ccr": "CCR - Taxa de Concepção de Vacas (%)",
    "hcr": "HCR - Taxa de Concepção de Novilhas (%)",
    "liv": "Taxa de Sobrevivência de Vacas (%)",
    # Conformação
    "bwc": "Composto Corporal",
    "udc": "Composto de Úbere",
    "flc": "Composto de Pernas e Pés",
    "sta": "Estatura",
    "str": "Força Corporal",
    "bd": "Profundidade Corporal",
    "df": "Forma Leiteira",
    "ra": "Ângulo de Garupa",
    "rw": "Largura de Garupa",
    "fa": "Ângulo de Casco",
    "rlsv": "Pernas Traseiras - Vista Lateral",
    "rlrv": "Pernas Traseiras - Vista Traseira",
    "fu": "Inserção Anterior de Úbere",
    "ruh": "Altura de Úbere Posterior",
    "ruw": "Largura de Úbere Posterior",
    "uc": "Ligamento de Úbere",
    "ud": "Profundidade de Úbere",
    "ftp": "Posicionamento dos Tetos Anteriores",
    "rtp": "Posicionamento dos Tetos Posteriores",
    "tl": "Comprimento de Teto",
}

GROUPS = {
    "Identificação": ["customer_id","reg_number","farm_eartag_number","birthdate"],
    "Índices": ["us_index","my_index","percent_rank"],
    "Produção": ["milk","fat","protein","pl"],
    "Saúde": ["dpr","scs","sce","dce","ssb","dsb","ccr","hcr","liv"],
    "Conformação": ["bwc","udc","flc","sta","str","bd","df","ra","rw","fa","rlsv","rlrv","fu","ruh","ruw","uc","ud","ftp","rtp","tl"],
}

# ====== Helpers de importação (autônomo) ======
def to_snake_case(name: str) -> str:
    n = re.sub(r"\s+"," ", str(name).strip())
    n = n.replace("/"," ").replace("-"," ")
    n = re.sub(r"[^\w\s]","", n)
    return n.lower().strip().replace(" ","_")

def normalize_header(cols) -> list[str]:
    return [("" if c is None else re.sub(r"\s+"," ", str(c).strip())) for c in cols]

def guess_encoding_from_bytes(data: bytes) -> Optional[str]:
    try:
        import chardet; return chardet.detect(data).get("encoding")
    except Exception:
        return None

def read_csv_auto(b: bytes) -> pd.DataFrame:
    enc = guess_encoding_from_bytes(b) or "utf-8-sig"
    for sep in [None, ";", ",", "\t"]:
        bio = io.BytesIO(b)
        try:
            return pd.read_csv(bio, sep=sep, engine="python" if sep is None else None, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(io.BytesIO(b), encoding=enc)

def load_table(uploaded_file, sheet: str|int|None=None) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    if name.endswith((".xlsx",".xlsm",".xls")):
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet if sheet else 0, engine="openpyxl")
    else:
        df = read_csv_auto(data)
    df.columns = normalize_header(df.columns)
    df = df[[c for c in df.columns if c and not str(c).lower().startswith("unnamed")]]
    df.columns = [EXPECTED_COLUMNS.get(c, to_snake_case(c)) for c in df.columns]
    for c in DATE_COLS:
        if c in df.columns: df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in LIKELY_NUMERIC:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# ====== Sidebar ======
with st.sidebar:
    st.header("Upload & Seleção")
    uploaded = st.file_uploader("Planilha (CSV/XLSX)", type=["csv","xlsx","xlsm","xls"], key=K("e4b_planilha"))
    excel_sheet = st.text_input("Aba do Excel (opcional)", key=K("e4b_sheet"))
    sort_col = st.selectbox("Ordenar por (opcional)", options=["(nenhum)"] + sum(GROUPS.values(), []), key=K("e4b_sort"))
    limit_rows = st.number_input("Limitar linhas (0 = todas)", min_value=0, value=0, step=10, key=K("e4b_limit"))
    report_title = st.text_input("Título do PDF", value="Relatório — Tabela (colunas úteis)", key=K("e4b_title"))
    contact_info = st.text_input("Rodapé do PDF", value="Alta Genetics • www.altagenetics.com.br", key=K("e4b_contact"))
    max_cols_per_page = st.slider("Máx. colunas por página", 6, 20, 10, key=K("e4b_maxcols"))
    st.divider()
    st.subheader("Grupos a incluir")
    chosen = []
    for g in GROUPS:
        if st.checkbox(g, True):
            chosen.append(g)
    st.divider()
    sort_col = st.selectbox("Ordenar por (opcional)", options=["(nenhum)"] + sum(GROUPS.values(), []))
    limit_rows = st.number_input("Limitar linhas (0 = todas)", min_value=0, value=0, step=10)
    st.divider()
    st.subheader("PDF — aparência")
    report_title = st.text_input("Título do PDF", value="Relatório — Tabela (colunas úteis)")
    contact_info = st.text_input("Rodapé do PDF", value="Alta Genetics • www.altagenetics.com.br")
    max_cols_per_page = st.slider("Máx. colunas por página", 6, 20, 10)

msg = st.empty()

# Reaproveita df de etapas anteriores
df: Optional[pd.DataFrame] = None
for key in ("df_etapa4","df_etapa3b","df_etapa2","df_etapa1"):
    if key in st.session_state:
        df = st.session_state[key]
        break

if uploaded:
    try:
        sheet_arg = excel_sheet if excel_sheet.strip() else None
        df = load_table(uploaded, sheet_arg)
        st.session_state["df_etapa4b"] = df.copy()
    except Exception as e:
        msg.error(f"❌ Falha na importação: {e}")
        df = None

if df is None:
    st.info("Envie um CSV/XLSX ou carregue uma das etapas anteriores no mesmo navegador.")
    st.stop()

msg.success(f"✅ Dados carregados ({len(df)} linhas, {len(df.columns)} colunas).")

# ====== Seleciona colunas por grupo ======
def group_df(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    real = [c for c in cols if c in df.columns]
    out = df[real].copy()
    return out.rename(columns={c: LABELS.get(c, c) for c in real})

work = df.copy()
if sort_col in work.columns:
    work = work.sort_values(by=sort_col, kind="stable")
if limit_rows and limit_rows > 0:
    work = work.head(int(limit_rows))

sheets: Dict[str, pd.DataFrame] = {}
for g in chosen:
    gdf = group_df(work, GROUPS[g])
    if not gdf.empty:
        sheets[g] = gdf

if not sheets:
    st.error("Nenhum grupo/coluna selecionado(a). Marque ao menos um grupo.")
    st.stop()

# Preview
tabs = st.tabs(list(sheets.keys()))
for tab, (name, gdf) in zip(tabs, sheets.items()):
    with tab:
        st.subheader(name)
        st.dataframe(gdf.head(20), use_container_width=True)

# ====== Exporta XLSX ======
def export_xlsx(sheets: Dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    try:
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            for sheet_name, data in sheets.items():
                data.to_excel(writer, sheet_name=sheet_name[:31], index=False)
                ws = writer.sheets[sheet_name[:31]]
                for i, col in enumerate(data.columns):
                    max_len = max([len(str(col))] + [len(str(x)) for x in data[col].head(200)])
                    ws.set_column(i, i, min(max(10, max_len + 2), 40))
            writer.close()
        return buf.getvalue()
    except Exception:
        # fallback para openpyxl
        buf.seek(0); buf.truncate(0)
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for sheet_name, data in sheets.items():
                data.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            writer.close()
        return buf.getvalue()

# ====== Exporta PDF (tabela) ======
def fmt_value(v) -> str:
    if pd.isna(v): return "—"
    if isinstance(v, pd.Timestamp): return v.strftime("%d/%m/%Y")
    try:
        f = float(v)
        if abs(f - int(f)) < 1e-6: return f"{int(f):,}".replace(",", ".")
        return f"{f:.2f}".replace(".", ",")
    except Exception:
        return str(v)

def split_columns(cols: List[str], max_cols: int) -> Iterable[List[str]]:
    for i in range(0, len(cols), max_cols):
        yield cols[i:i+max_cols]

def build_table(df_slice: pd.DataFrame, cols_labs: List[str]) -> LongTable:
    data = [cols_labs] + [[fmt_value(v) for v in row] for row in df_slice.itertuples(index=False, name=None)]
    tbl = LongTable(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
    ]))
    return tbl

def draw_header_footer(canvas, doc, title: str, contact: Optional[str]):
    width, height = landscape(A4)
    canvas.saveState()
    canvas.setFont('Helvetica-Bold', 12)
    canvas.drawString(20, height-25, title)
    canvas.setStrokeColor(colors.lightgrey)
    canvas.line(20, height-30, width-20, height-30)
    canvas.setFont('Helvetica', 9)
    canvas.drawString(20, 15, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    if contact:
        canvas.drawCentredString(width/2, 15, contact)
    canvas.drawRightString(width-20, 15, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()

def export_pdf_table(sheets: Dict[str, pd.DataFrame], max_cols: int, title: str, contact: Optional[str]) -> bytes:
    # Junta todas as colunas selecionadas em uma única tabela (como Etapa 3B)
    # Monta DF final concatenando grupos lado a lado (mesmas linhas)
    # Para garantir ordem, usamos a união das colunas na sequência dos grupos
    ordered_cols_machine = []
    ordered_cols_labels = []
    for g, cols in sheets.items():
        # `sheets[g]` já está renomeado para labels; precisamos sincronizar
        for lab in cols.columns.tolist():
            ordered_cols_labels.append(lab)
    # como o DF de trabalho já está filtrado, apenas reusa o primeiro sheet como base
    base = next(iter(sheets.values()))
    # para PDF, concatenamos todas as colunas (labels) lado a lado pela ordem
    df_pdf = pd.concat([sheets[g] for g in sheets], axis=1)
    # fatiamos em páginas por quantidade de colunas
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    elements = [Spacer(1, 24)]
    # calcula fatias pelas labels
    label_slices = list(split_columns(df_pdf.columns.tolist(), max_cols))
    for i, labs in enumerate(label_slices, start=1):
        tbl = build_table(df_pdf[labs], labs)
        elements.append(tbl)
        if i < len(label_slices):
            elements.append(PageBreak())
    doc.build(elements,
              onFirstPage=lambda c, d: draw_header_footer(c, d, title, contact),
              onLaterPages=lambda c, d: draw_header_footer(c, d, title, contact))
    pdf = buf.getvalue(); buf.close()
    return pdf

# ====== Geração dos arquivos ======
xlsx_bytes = export_xlsx(sheets)
pdf_bytes = export_pdf_table(sheets, max_cols=int(max_cols_per_page),
                             title=report_title, contact=contact_info)

ts = datetime.now().strftime("%Y%m%d_%H%M")
xlsx_name = f"export_{ts}.xlsx"
pdf_name  = f"relatorio_{ts}.pdf"

# Downloads individuais
c1, c2, c3 = st.columns([1,1,1])
with c1:
    st.download_button("⬇️ Baixar XLSX", data=xlsx_bytes, file_name=xlsx_name,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with c2:
    st.download_button("📄 Baixar PDF", data=pdf_bytes, file_name=pdf_name, mime="application/pdf")

# ZIP com ambos
with c3:
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(xlsx_name, xlsx_bytes)
        zf.writestr(pdf_name, pdf_bytes)
    st.download_button("🗜️ Baixar pacote ZIP (XLSX+PDF)",
                       data=zip_buf.getvalue(),
                       file_name=f"pacote_{ts}.zip",
                       mime="application/zip")

# app_etapa5.py — Etapa 5: Médias do Rebanho
# - Importa CSV/XLSX (ou reaproveita df das Etapas 1–4 via session_state)
# - Filtros (fazenda, lactação, intervalos de datas)
# - Calcula médias (e estatísticas) gerais ou por grupos
# - Exporta CSV/XLSX dos agregados

import io, re
from typing import Optional, Dict, List
from datetime import date

import pandas as pd
import streamlit as st

# --- chaves únicas para widgets (evita conflito de IDs) ---
APP = "final"  # pode trocar por outro prefixo único do seu app

def K(name: str) -> str:
    """Gera uma chave única e estável para widgets do Streamlit."""
    return f"{APP}:{name}"


# ============================
# Config página
# ============================
st.set_page_config(page_title="Etapa 5 — Médias do Rebanho", layout="wide")
st.title("Etapa 5 — Médias do Rebanho")
st.caption("Cálculo de médias/estatísticas para produção, índices e saúde (geral ou por grupos).")

# ============================
# Mapeamentos (os mesmos das etapas anteriores)
# ============================
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
LABELS = {
    "customer_id": "Fazenda",
    "reg_number": "Código ABCBRH",
    "farm_eartag_number": "Animal",
    "birthdate": "Data nascimento",
    "lactation_number": "Lactação",
    "us_index": "Índice Americano",
    "my_index": "Meu Índice",
    "percent_rank": "Posição Ranking fazenda",
    "milk": "Leite (lbs)", "fat": "Gordura (lbs)", "protein": "Proteína (lbs)",
    "pl": "Vida Produtiva (meses)",
    "dpr": "DPR - Taxa de Prenhez (%)", "scs": "Células Somáticas",
    "ccr": "CCR - Vacas (%)", "hcr": "HCR - Novilhas (%)", "liv": "Sobrevivência de Vacas (%)",
}

# Grupos de métricas para seleção
GROUPS = {
    "Índices": ["us_index","my_index","percent_rank"],
    "Produção & Vida": ["milk","fat","protein","pl"],
    "Saúde & Reprodução": ["dpr","scs","ccr","hcr","liv"],
    # Pode incluir Conformação se desejar (muitas colunas):
    # "Conformação": ["bwc","udc","flc","sta","str","bd","df","ra","rw","fa","rlsv","rlrv","fu","ruh","ruw","uc","ud","ftp","rtp","tl"],
}

# ============================
# Import helpers (autônomo)
# ============================
def to_snake_case(name: str) -> str:
    n = re.sub(r"\s+"," ", str(name).strip())
    n = n.replace("/"," ").replace("-"," ")
    n = re.sub(r"[^\w\s]","", n)
    return n.lower().strip().replace(" ","_")

def normalize_header(cols) -> list[str]:
    return [("" if c is None else re.sub(r"\s+"," ", str(c).strip())) for c in cols]

def guess_encoding_from_bytes(data: bytes) -> Optional[str]:
    try:
        import chardet; return chardet.detect(data).get("encoding")
    except Exception:
        return None

def read_csv_auto(b: bytes) -> pd.DataFrame:
    enc = guess_encoding_from_bytes(b) or "utf-8-sig"
    for sep in [None, ";", ",", "\t"]:
        bio = io.BytesIO(b)
        try:
            return pd.read_csv(bio, sep=sep, engine="python" if sep is None else None, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(io.BytesIO(b), encoding=enc)

def load_table(uploaded_file, sheet: str|int|None=None) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    if name.endswith((".xlsx",".xlsm",".xls")):
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet if sheet else 0, engine="openpyxl")
    else:
        df = read_csv_auto(data)
    df.columns = normalize_header(df.columns)
    df = df[[c for c in df.columns if c and not str(c).lower().startswith("unnamed")]]
    df.columns = [EXPECTED_COLUMNS.get(c, to_snake_case(c)) for c in df.columns]
    for c in DATE_COLS:
        if c in df.columns: df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in LIKELY_NUMERIC:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# ============================
# Sidebar (filtros e opções)
# ============================
with st.sidebar:
    st.header("Upload & Filtros")
    uploaded = st.file_uploader("Planilha (CSV/XLSX)", type=["csv","xlsx","xlsm","xls"], key=K("e5_planilha"))
    excel_sheet = st.text_input("Aba do Excel (opcional)", key=K("e5_sheet"))
    filt_farm = st.text_input("Filtrar por Fazenda (contém)", key=K("e5_fazenda"))
    lact_min, lact_max = st.slider("Lactação (intervalo)", 1, 12, (1, 12), key=K("e5_lact"))
    use_birth = st.checkbox("Filtrar por Data de Nascimento", value=False, key=K("e5_use_birth"))
    use_calv = st.checkbox("Filtrar por Último Parto", value=False, key=K("e5_use_calv"))
    group_mode = st.selectbox("Escolha o agrupamento", ["(Geral)", "Fazenda", "Lactação", "Fazenda + Lactação"], key=K("e5_group"))
    show_mean = st.checkbox("Média", True, key=K("e5_mean"))
    show_median = st.checkbox("Mediana", True, key=K("e5_median"))
    show_std = st.checkbox("Desvio Padrão", False, key=K("e5_std"))
    show_count = st.checkbox("N válidos", True, key=K("e5_count"))
    decimals = st.number_input("Casas decimais", 0, 6, 2, key=K("e5_dec"))
    st.subheader("Filtros")
    filt_farm = st.text_input("Filtrar por Fazenda (contém)")
    lact_min, lact_max = st.slider("Lactação (intervalo)", 1, 12, (1, 12))
    st.write("Datas (opcionais)")
    use_birth = st.checkbox("Filtrar por Data de Nascimento", value=False)
    birth_min = st.date_input("Nascimento de", value=date(1990,1,1), disabled=not use_birth)
    birth_max = st.date_input("Nascimento até", value=date.today(), disabled=not use_birth)
    use_calv = st.checkbox("Filtrar por Último Parto", value=False)
    calv_min = st.date_input("Parto de", value=date(2000,1,1), disabled=not use_calv)
    calv_max = st.date_input("Parto até", value=date.today(), disabled=not use_calv)

    st.subheader("Colunas para média")
    chosen_groups = []
    for g in GROUPS:
        if st.checkbox(g, True):
            chosen_groups.append(g)

    st.subheader("Agrupar por")
    group_mode = st.selectbox(
        "Escolha o agrupamento",
        ["(Geral)", "Fazenda", "Lactação", "Fazenda + Lactação"]
    )

    st.subheader("Estatísticas")
    show_mean = st.checkbox("Média", True)
    show_median = st.checkbox("Mediana", True)
    show_std = st.checkbox("Desvio Padrão", False)
    show_count = st.checkbox("N válidos", True)
    decimals = st.number_input("Casas decimais", 0, 6, 2)

# ============================
# Carrega df (pode vir do session_state)
# ============================
msg = st.empty()

df: Optional[pd.DataFrame] = None
for key in ("df_etapa4b","df_etapa4","df_etapa3b","df_etapa3","df_etapa2","df_etapa1"):
    if key in st.session_state:
        df = st.session_state[key]
        break

if uploaded:
    try:
        sheet_arg = excel_sheet if excel_sheet.strip() else None
        df = load_table(uploaded, sheet_arg)
        st.session_state["df_etapa5"] = df.copy()
    except Exception as e:
        msg.error(f"❌ Falha na importação: {e}")
        df = None

if df is None:
    st.info("Envie um CSV/XLSX ou carregue uma das etapas anteriores no mesmo navegador.")
    st.stop()

# ============================
# Aplica filtros
# ============================
work = df.copy()

if filt_farm.strip() and "customer_id" in work.columns:
    work = work[work["customer_id"].astype(str).str.contains(filt_farm.strip(), case=False, na=False)]

if "lactation_number" in work.columns:
    work = work[(work["lactation_number"].fillna(0) >= lact_min) & (work["lactation_number"].fillna(0) <= lact_max)]

if use_birth and "birthdate" in work.columns:
    work = work[(work["birthdate"].dt.date >= birth_min) & (work["birthdate"].dt.date <= birth_max)]

if use_calv and "calving_date" in work.columns:
    work = work[(work["calving_date"].dt.date >= calv_min) & (work["calving_date"].dt.date <= calv_max)]

msg.success(f"✅ Dados após filtros: {len(work)} linhas.")

# ============================
# Seleção de métricas a agregar
# ============================
metrics_cols: List[str] = []
for g in chosen_groups:
    metrics_cols += GROUPS[g]
metrics_cols = [c for c in metrics_cols if c in work.columns]

if not metrics_cols:
    st.error("Nenhuma métrica selecionada. Marque ao menos um grupo na barra lateral.")
    st.stop()

# ============================
# Agrupamento e agregação
# ============================
group_cols: List[str] = []
if group_mode == "Fazenda" and "customer_id" in work.columns:
    group_cols = ["customer_id"]
elif group_mode == "Lactação" and "lactation_number" in work.columns:
    group_cols = ["lactation_number"]
elif group_mode == "Fazenda + Lactação" and {"customer_id","lactation_number"}.issubset(work.columns):
    group_cols = ["customer_id","lactation_number"]

aggs = {}
if show_mean: aggs["mean"] = "Média"
if show_median: aggs["median"] = "Mediana"
if show_std: aggs["std"] = "Desv.Pad."
if show_count: aggs["count"] = "N válidos"
if not aggs:
    st.error("Selecione ao menos uma estatística (média/mediana/etc.).")
    st.stop()

# constrói dicionário de agg para cada coluna
agg_spec = {c: list(aggs.keys()) for c in metrics_cols}

if group_cols:
    grouped = work.groupby(group_cols, dropna=False).agg(agg_spec)
else:
    # para o caso geral, cria um índice fictício
    grouped = work.agg(agg_spec)
    # coloca rótulo de "Geral"
    grouped = grouped.to_frame().T
    grouped.index = pd.Index(["Geral"], name="Grupo")

# reorganiza MultiIndex → colunas com sufixo da estatística
grouped.columns = [f"{col}__{stat}" for col, stat in grouped.columns.to_flat_index()]
grouped = grouped.reset_index()

# Renomeia colunas visíveis (labels + estatística)
rename_cols = {}
for c in grouped.columns:
    if "__" in c:
        base, stat = c.split("__", 1)
        label = LABELS.get(base, base)
        rename_cols[c] = f"{label} ({aggs.get(stat, stat)})"
    elif c in LABELS:
        rename_cols[c] = LABELS[c]
grouped = grouped.rename(columns=rename_cols)

# Formatação numérica
def fmt_df(df_in: pd.DataFrame, decimals: int) -> pd.DataFrame:
    df_out = df_in.copy()
    for c in df_out.columns:
        if df_out[c].dtype.kind in "fc":
            df_out[c] = df_out[c].round(decimals)
    return df_out

result = fmt_df(grouped, int(decimals))

# ============================
# Cards de destaque (somente quando "Geral")
# ============================
if not group_cols:
    st.subheader("Médias do rebanho — Destaques")
    key_metrics = [c for c in ["milk","fat","protein","pl","dpr","scs","us_index","my_index"] if c in work.columns]
    cols = st.columns(min(4, len(key_metrics)) or 1)
    for i, m in enumerate(key_metrics):
        with cols[i % len(cols)]:
            val = work[m].mean(skipna=True)
            st.metric(LABELS.get(m, m), f"{val:.{int(decimals)}f}" if pd.notna(val) else "—")

# ============================
# Tabela e download
# ============================
st.subheader("Tabela de estatísticas")
st.dataframe(result, use_container_width=True)

st.download_button(
    "⬇️ Baixar CSV (estatísticas)",
    data=result.to_csv(index=False).encode("utf-8"),
    file_name="medias_rebanho.csv",
    mime="text/csv",
)

# Exporta XLSX
def export_xlsx(df_out: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    try:
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df_out.to_excel(writer, sheet_name="Medias", index=False)
            ws = writer.sheets["Medias"]
            for i, col in enumerate(df_out.columns):
                max_len = max([len(str(col))] + [len(str(x)) for x in df_out[col].head(200)])
                ws.set_column(i, i, min(max(12, max_len + 2), 50))
            writer.close()
        return buf.getvalue()
    except Exception:
        buf.seek(0); buf.truncate(0)
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_out.to_excel(writer, sheet_name="Medias", index=False)
            writer.close()
        return buf.getvalue()

xlsx_bytes = export_xlsx(result)
st.download_button(
    "⬇️ Baixar XLSX (estatísticas)",
    data=xlsx_bytes,
    file_name="medias_rebanho.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.info("Dica: use o agrupamento por **Fazenda** ou **Lactação** para comparar médias entre grupos.")
