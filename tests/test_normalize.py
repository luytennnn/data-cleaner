import pandas as pd
import pytest

from cleaner.errors import ColumnNotFoundError, DataCleanerError
from cleaner.normalize import normalize


def test_lowercase_and_trim():
    df = pd.DataFrame({"name": ["  Ana  ", "BETO"]})
    out = normalize(df, {"name": ["trim", "lowercase"]})
    assert out["name"].tolist() == ["ana", "beto"]


# email = trim + lowercase
def test_email_standardization():
    df = pd.DataFrame({"email": ["  Ana@X.PT ", "BETO@x.pt"]})
    out = normalize(df, {"email": ["email"]})
    assert out["email"].tolist() == ["ana@x.pt", "beto@x.pt"]


# §5: telefones com +351, espaços e traços → só dígitos
def test_phone_keeps_only_digits():
    df = pd.DataFrame({"phone": ["+351 912 345-678", "(351) 913.111.222"]})
    out = normalize(df, {"phone": ["phone"]})
    assert out["phone"].tolist() == ["351912345678", "351913111222"]


# §5: nulos tratados como string vazia normalizada
def test_nulls_become_empty_string():
    df = pd.DataFrame({"name": ["Ana", None]})
    out = normalize(df, {"name": ["lowercase"]})
    assert out["name"].tolist() == ["ana", ""]


# Colunas não listadas ficam intactas
def test_unlisted_columns_untouched():
    df = pd.DataFrame({"name": ["  Ana  "], "age": [30]})
    out = normalize(df, {"name": ["trim"]})
    assert out["age"].tolist() == [30]
    assert out["name"].tolist() == ["Ana"]


# Não muta o DataFrame original
def test_does_not_mutate_input():
    df = pd.DataFrame({"name": ["  Ana  "]})
    normalize(df, {"name": ["trim"]})
    assert df["name"].tolist() == ["  Ana  "]


def test_missing_column_raises():
    df = pd.DataFrame({"name": ["Ana"]})
    with pytest.raises(ColumnNotFoundError):
        normalize(df, {"nope": ["trim"]})


def test_unknown_operation_raises():
    df = pd.DataFrame({"name": ["Ana"]})
    with pytest.raises(DataCleanerError):
        normalize(df, {"name": ["uppercase_unknown"]})
