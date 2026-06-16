import pandas as pd
import pytest

from cleaner.errors import EmptyDataError, UnsupportedFormatError
from cleaner.io import list_sheets, read_table, write_table


# Fixture sintética: pequeno CSV legítimo de teste (não dados de cliente)
def _write_csv(path, rows="name,email\nAna,ana@x.pt\nBeto,beto@x.pt\n"):
    path.write_text(rows, encoding="utf-8")
    return path


def test_read_csv_returns_dataframe(tmp_path):
    f = _write_csv(tmp_path / "in.csv")
    df = read_table(f)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["name", "email"]
    assert len(df) == 2


# §3: carregar .xlsx — usa a 1ª sheet por defeito
def test_read_excel_default_first_sheet(tmp_path):
    f = tmp_path / "in.xlsx"
    with pd.ExcelWriter(f) as w:
        pd.DataFrame({"name": ["Ana"], "email": ["ana@x.pt"]}).to_excel(
            w, sheet_name="Primeira", index=False
        )
        pd.DataFrame({"x": [99]}).to_excel(w, sheet_name="Segunda", index=False)
    df = read_table(f)
    assert list(df.columns) == ["name", "email"]
    assert df.iloc[0]["name"] == "Ana"


# §5: Excel com várias sheets — permite escolher qual
def test_read_excel_choose_sheet(tmp_path):
    f = tmp_path / "in.xlsx"
    with pd.ExcelWriter(f) as w:
        pd.DataFrame({"name": ["Ana"]}).to_excel(w, sheet_name="Primeira", index=False)
        pd.DataFrame({"x": [99]}).to_excel(w, sheet_name="Segunda", index=False)
    df = read_table(f, sheet="Segunda")
    assert list(df.columns) == ["x"]
    assert df.iloc[0]["x"] == 99


# §5: lista as sheets para a UI deixar escolher
def test_list_sheets(tmp_path):
    f = tmp_path / "in.xlsx"
    with pd.ExcelWriter(f) as w:
        pd.DataFrame({"a": [1]}).to_excel(w, sheet_name="Primeira", index=False)
        pd.DataFrame({"b": [2]}).to_excel(w, sheet_name="Segunda", index=False)
    assert list_sheets(f) == ["Primeira", "Segunda"]


# list_sheets num CSV não tem sheets
def test_list_sheets_csv_returns_empty(tmp_path):
    f = _write_csv(tmp_path / "in.csv")
    assert list_sheets(f) == []


# §5: ficheiro vazio ou só cabeçalho → erro claro, sem crash
def test_read_empty_csv_raises(tmp_path):
    f = tmp_path / "empty.csv"
    f.write_text("name,email\n", encoding="utf-8")  # só cabeçalho
    with pytest.raises(EmptyDataError):
        read_table(f)


def test_read_unsupported_format_raises(tmp_path):
    f = tmp_path / "in.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        read_table(f)


# Round-trip: escrever e reler CSV preserva os dados
def test_write_read_csv_roundtrip(tmp_path):
    df = pd.DataFrame({"name": ["Ana", "Beto"], "n": [1, 2]})
    out = tmp_path / "out.csv"
    write_table(df, out)
    back = read_table(out)
    pd.testing.assert_frame_equal(back, df)


# Round-trip: escrever e reler Excel preserva os dados
def test_write_read_excel_roundtrip(tmp_path):
    df = pd.DataFrame({"name": ["Ana", "Beto"], "n": [1, 2]})
    out = tmp_path / "out.xlsx"
    write_table(df, out)
    back = read_table(out)
    pd.testing.assert_frame_equal(back, df)


def test_write_unsupported_format_raises(tmp_path):
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(UnsupportedFormatError):
        write_table(df, tmp_path / "out.txt")
