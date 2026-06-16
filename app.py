import io as _io

import pandas as pd
import streamlit as st

from cleaner.dedup import dedup_exact, dedup_fuzzy
from cleaner.errors import DataCleanerError
from cleaner.io import list_sheets, read_table
from cleaner.linkage import COMPARISON_TYPES, dedupe_records, link_records
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


# Upload + leitura (com escolha de sheet em Excel). Devolve df ou para com erro.
def _upload_and_read(label, key):
    up = st.file_uploader(label, type=["csv", "xlsx", "xls"], key=key)
    if up is None:
        return None
    file_bytes = up.getvalue()
    try:
        sheets = _sheets(file_bytes, up.name)
        sheet = None
        if len(sheets) > 1:
            sheet = st.selectbox(f"Worksheet ({up.name})", sheets, index=0, key=f"sheet_{key}")
        return _load(file_bytes, up.name, sheet)
    except DataCleanerError as e:
        st.error(str(e))
        st.stop()
    except Exception as e:  # ficheiro corrompido/ilegível → erro claro, sem crash
        st.error(f"Could not read the file: {e}")
        st.stop()


# UI da config de comparação por coluna (tipo curado por coluna escolhida).
# Devolve {coluna: tipo} para o motor de matching probabilístico.
def _comparison_ui(cols, key_prefix):
    chosen = st.multiselect("Columns to compare", cols, key=f"{key_prefix}_cols")
    config = {}
    for col in chosen:
        ctype = st.selectbox(
            f"Comparison type for '{col}'", list(COMPARISON_TYPES),
            key=f"{key_prefix}_type_{col}",
            help="exact = identical · name/email = fuzzy by field · phone = small typos · date = date logic",
        )
        config[col] = ctype
    return config


# Tabela de resultado + auditoria + chart de match-weights + downloads (T7).
def _show_probabilistic_result(result_df, audit, chart, result_label, result_name):
    if audit.empty:
        st.warning("No matches above the threshold. Try lowering it.")
    st.markdown(f"**{result_label}**")
    st.dataframe(result_df.head(200), use_container_width=True, hide_index=True)
    st.markdown("**Audit — match probability per pair/group**")
    st.dataframe(audit, use_container_width=True, hide_index=True)

    if chart is not None:
        st.markdown("**Match weights** — each field's contribution to a match")
        st.altair_chart(chart, use_container_width=True)

    d1, d2, d3, d4 = st.columns(4)
    d1.download_button(f"⬇ {result_label} (CSV)", _to_bytes(result_df, "csv"),
                       f"{result_name}.csv", "text/csv")
    d2.download_button(
        f"⬇ {result_label} (Excel)", _to_bytes(result_df, "xlsx"), f"{result_name}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    d3.download_button("⬇ Audit (CSV)", _to_bytes(audit, "csv"), "audit.csv", "text/csv")
    d4.download_button(
        "⬇ Audit (Excel)", _to_bytes(audit, "xlsx"), "audit.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# Aplica normalização + dedup conforme a config escolhida na UI (modo v1)
def _run_clean(df, norm_config, keys, mode, threshold, block_size):
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


# ----- Modo Clean (v1): profile + normalize + dedup exato/fuzzy -----
def render_clean():
    uploaded = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx", "xls"])
    if uploaded is None:
        st.info("Upload a file to begin.")
        st.stop()
    file_bytes = uploaded.getvalue()
    try:
        sheets = _sheets(file_bytes, uploaded.name)
        sheet = None
        if len(sheets) > 1:
            sheet = st.selectbox("Worksheet", sheets, index=0)
        df = _load(file_bytes, uploaded.name, sheet)
    except DataCleanerError as e:
        st.error(str(e))
        st.stop()
    except Exception as e:
        st.error(f"Could not read the file: {e}")
        st.stop()

    st.subheader("1 · Profile")
    p = profile_table(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows", p["n_rows"])
    c2.metric("Columns", p["n_cols"])
    c3.metric("Exact duplicate rows", p["exact_duplicates"])
    prof_df = pd.DataFrame({
        "column": p["columns"],
        "dtype": [p["dtypes"][c] for c in p["columns"]],
        "null_%": [p["null_pct"][c] for c in p["columns"]],
    })
    st.dataframe(prof_df, use_container_width=True, hide_index=True)
    with st.expander("Preview data"):
        st.dataframe(df.head(50), use_container_width=True)

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
            help="Only records sharing the first N characters of the key are compared.")

    if st.button("Run cleaning", type="primary"):
        if not keys:
            st.warning("Select at least one key column for deduplication.")
            st.stop()
        try:
            clean, audit = _run_clean(df, norm_config, keys, mode, threshold, int(block_size))
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
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        d3.download_button("⬇ Audit (CSV)", _to_bytes(audit, "csv"), "audit.csv", "text/csv")
        d4.download_button(
            "⬇ Audit (Excel)", _to_bytes(audit, "xlsx"), "audit.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ----- Modo Deduplicate (probabilístico): 1 ficheiro, EM multi-campo -----
def render_dedupe_prob():
    df = _upload_and_read("Upload a CSV or Excel file to deduplicate", "dedup_up")
    if df is None:
        st.info("Upload a file to begin.")
        st.stop()
    st.caption(f"{len(df)} rows · {len(df.columns)} columns")

    st.subheader("Match configuration")
    config = _comparison_ui(list(df.columns), "dedup")
    threshold = st.slider("Match probability threshold", 0.50, 0.99, 0.90, 0.01, key="dedup_thr")

    if st.button("Run deduplication", type="primary"):
        if not config:
            st.warning("Choose at least one column to compare.")
            st.stop()
        try:
            with st.spinner("Training the probabilistic model…"):
                clean, audit, chart = dedupe_records(
                    df, {"comparisons": config, "threshold": threshold}, with_chart=True)
        except DataCleanerError as e:
            st.error(str(e))
            st.stop()
        removed = len(df) - len(clean)
        st.success(f"Done. {removed} probable duplicate(s) removed — {len(clean)} remain.")
        _show_probabilistic_result(clean, audit, chart, "Cleaned data", "deduplicated")


# ----- Modo Link: 2 ficheiros, pares A↔B -----
def render_link():
    col_a, col_b = st.columns(2)
    with col_a:
        df_a = _upload_and_read("File A", "link_a")
    with col_b:
        df_b = _upload_and_read("File B", "link_b")
    if df_a is None or df_b is None:
        st.info("Upload both files to begin.")
        st.stop()
    st.caption(f"A: {len(df_a)} rows · B: {len(df_b)} rows")

    common = [c for c in df_a.columns if c in df_b.columns]
    if not common:
        st.error("The two files share no common columns to compare.")
        st.stop()

    st.subheader("Match configuration")
    config = _comparison_ui(common, "link")
    threshold = st.slider("Match probability threshold", 0.50, 0.99, 0.90, 0.01, key="link_thr")

    if st.button("Run linking", type="primary"):
        if not config:
            st.warning("Choose at least one column to compare.")
            st.stop()
        try:
            with st.spinner("Training the probabilistic model…"):
                pairs, audit, chart = link_records(
                    df_a, df_b, {"comparisons": config, "threshold": threshold}, with_chart=True)
        except DataCleanerError as e:
            st.error(str(e))
            st.stop()
        st.success(f"Done. {len(pairs)} matching pair(s) above the threshold.")
        _show_probabilistic_result(pairs, audit, chart, "Matched pairs", "matched_pairs")


st.title("🧹 Data Cleaner")
st.caption("Profile, normalize, deduplicate and link any CSV or Excel file.")

MODE = st.radio(
    "Mode", ["Clean (v1)", "Deduplicate (probabilistic)", "Link two files"],
    horizontal=True,
    help="Clean = exact/fuzzy dedup · Deduplicate = probabilistic multi-field · Link = match two files",
)

if MODE == "Clean (v1)":
    render_clean()
elif MODE == "Deduplicate (probabilistic)":
    render_dedupe_prob()
else:
    render_link()
