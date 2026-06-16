import io as _io

import pandas as pd
import streamlit as st

from cleaner.dedup import dedup_exact, dedup_fuzzy
from cleaner.errors import DataCleanerError
from cleaner.io import list_sheets, read_table
from cleaner.normalize import normalize
from cleaner.profile import profile_table

st.set_page_config(page_title="Data Cleaner", page_icon="🧹", layout="wide")

NORM_OPS = ["trim", "lowercase", "email", "phone"]


# Lê o ficheiro carregado para DataFrame; cache para não reler a cada interação
@st.cache_data(show_spinner=False)
def _load(file_bytes, name, sheet):
    bio = _io.BytesIO(file_bytes)
    bio.name = name  # read_table usa a extensão do nome
    return read_table(bio, sheet=sheet)


@st.cache_data(show_spinner=False)
def _sheets(file_bytes, name):
    bio = _io.BytesIO(file_bytes)
    bio.name = name
    return list_sheets(bio)


# Serializa um DataFrame para bytes descarregáveis (CSV ou Excel)
def _to_bytes(df, fmt):
    if fmt == "csv":
        return df.to_csv(index=False).encode("utf-8")
    buf = _io.BytesIO()
    with pd.ExcelWriter(buf) as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


# Aplica normalização + dedup conforme a config escolhida na UI
def _run(df, norm_config, keys, mode, threshold, block_size):
    work = normalize(df, norm_config) if norm_config else df.copy()
    audits = []
    if mode in ("Exact", "Exact then Fuzzy"):
        work, a = dedup_exact(work, keys)
        audits.append(a)
    if mode in ("Fuzzy", "Exact then Fuzzy"):
        work, a = dedup_fuzzy(work, keys, threshold=threshold, block_size=block_size)
        audits.append(a)
    audit = pd.concat(audits, ignore_index=True) if audits else pd.DataFrame()
    if not audit.empty:
        audit["group_id"] = range(1, len(audit) + 1)
    return work, audit


st.title("🧹 Data Cleaner")
st.caption("Profile, normalize and deduplicate any CSV or Excel file.")

uploaded = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx", "xls"])

if uploaded is None:
    st.info("Upload a file to begin.")
    st.stop()

file_bytes = uploaded.getvalue()

# Excel com várias sheets → deixar escolher; CSV ignora
try:
    sheets = _sheets(file_bytes, uploaded.name)
    sheet = None
    if len(sheets) > 1:
        sheet = st.selectbox("Worksheet", sheets, index=0)
    df = _load(file_bytes, uploaded.name, sheet)
except DataCleanerError as e:
    st.error(str(e))
    st.stop()
except Exception as e:  # ficheiro corrompido/ilegível → erro claro, sem crash
    st.error(f"Could not read the file: {e}")
    st.stop()

# --- Profile ---
st.subheader("1 · Profile")
p = profile_table(df)
c1, c2, c3 = st.columns(3)
c1.metric("Rows", p["n_rows"])
c2.metric("Columns", p["n_cols"])
c3.metric("Exact duplicate rows", p["exact_duplicates"])
prof_df = pd.DataFrame(
    {
        "column": p["columns"],
        "dtype": [p["dtypes"][c] for c in p["columns"]],
        "null_%": [p["null_pct"][c] for c in p["columns"]],
    }
)
st.dataframe(prof_df, use_container_width=True, hide_index=True)
with st.expander("Preview data"):
    st.dataframe(df.head(50), use_container_width=True)

# --- Controls ---
st.subheader("2 · Clean")
cols = list(df.columns)

norm_cols = st.multiselect("Columns to normalize", cols)
norm_config = {}
for col in norm_cols:
    ops = st.multiselect(f"Operations for '{col}'", NORM_OPS, key=f"ops_{col}")
    if ops:
        norm_config[col] = ops

keys = st.multiselect("Key columns for deduplication", cols)
mode = st.selectbox("Deduplication", ["Exact", "Fuzzy", "Exact then Fuzzy"])
threshold, block_size = 85, 1
if mode in ("Fuzzy", "Exact then Fuzzy"):
    threshold = st.slider("Fuzzy similarity threshold", 50, 100, 85)
    block_size = st.number_input(
        "Blocking prefix length", min_value=1, max_value=5, value=1,
        help="Only records sharing the first N characters of the key are compared.",
    )

# --- Run ---
if st.button("Run cleaning", type="primary"):
    if not keys:
        st.warning("Select at least one key column for deduplication.")
        st.stop()
    try:
        clean, audit = _run(df, norm_config, keys, mode, threshold, int(block_size))
    except DataCleanerError as e:
        st.error(str(e))
        st.stop()

    removed = len(df) - len(clean)
    st.success(f"Done. {removed} duplicate row(s) removed — {len(clean)} remain.")

    st.markdown("**Cleaned data**")
    st.dataframe(clean.head(100), use_container_width=True, hide_index=True)
    st.markdown("**Audit — duplicate groups (kept vs removed)**")
    st.dataframe(audit, use_container_width=True, hide_index=True)

    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("⬇ Clean (CSV)", _to_bytes(clean, "csv"), "clean.csv", "text/csv")
    d2.download_button(
        "⬇ Clean (Excel)", _to_bytes(clean, "xlsx"), "clean.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    d3.download_button("⬇ Audit (CSV)", _to_bytes(audit, "csv"), "audit.csv", "text/csv")
    d4.download_button(
        "⬇ Audit (Excel)", _to_bytes(audit, "xlsx"), "audit.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
