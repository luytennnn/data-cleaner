from pathlib import Path

import pandas as pd

from cleaner.errors import EmptyDataError, UnsupportedFormatError

# Extensões reconhecidas por tipo
_CSV_EXT = {".csv"}
_EXCEL_EXT = {".xlsx", ".xls"}


# Extensão a partir de path, string ou file-like (upload Streamlit tem .name)
def _ext(source):
    name = getattr(source, "name", source)
    return Path(str(name)).suffix.lower()


# Lê CSV ou Excel para DataFrame; sheet só se aplica a Excel.
# Aceita caminho, string ou objeto file-like (upload da app).
def read_table(path, sheet=None):
    ext = _ext(path)
    if ext in _CSV_EXT:
        df = pd.read_csv(path)
    elif ext in _EXCEL_EXT:
        df = pd.read_excel(path, sheet_name=sheet if sheet is not None else 0)
    else:
        raise UnsupportedFormatError(
            f"Unsupported file format '{ext}'. Use CSV or Excel (.xlsx/.xls)."
        )
    if df.empty:
        raise EmptyDataError("File has no data rows (empty or header only).")
    return df


# Nomes das sheets de um Excel; CSV não tem sheets → lista vazia
def list_sheets(path):
    if _ext(path) in _EXCEL_EXT:
        return pd.ExcelFile(path).sheet_names
    return []


# Escreve DataFrame em CSV ou Excel conforme a extensão
def write_table(df, path):
    path = Path(path)
    ext = path.suffix.lower()
    if ext in _CSV_EXT:
        df.to_csv(path, index=False)
    elif ext in _EXCEL_EXT:
        df.to_excel(path, index=False)
    else:
        raise UnsupportedFormatError(
            f"Unsupported file format '{ext}'. Use CSV or Excel (.xlsx/.xls)."
        )
    return path
