import numpy as np
import pandas as pd

from cleaner.profile import profile_table


# Fixture sintética com nulos e duplicados conhecidos
def _sample():
    return pd.DataFrame(
        {
            "name": ["Ana", "Beto", "Ana", None],
            "age": [30, 25, 30, 40],
        }
    )


def test_profile_row_and_col_counts():
    p = profile_table(_sample())
    assert p["n_rows"] == 4
    assert p["n_cols"] == 2
    assert p["columns"] == ["name", "age"]


def test_profile_dtypes_are_strings():
    p = profile_table(_sample())
    assert set(p["dtypes"]) == {"name", "age"}
    assert all(isinstance(v, str) for v in p["dtypes"].values())


def test_profile_null_pct_per_column():
    p = profile_table(_sample())
    # name tem 1 nulo em 4 = 25%; age não tem nulos
    assert p["null_pct"]["name"] == 25.0
    assert p["null_pct"]["age"] == 0.0


def test_profile_exact_duplicates_count():
    # ("Ana", 30) aparece 2x → 1 linha redundante
    p = profile_table(_sample())
    assert p["exact_duplicates"] == 1


def test_profile_no_duplicates():
    df = pd.DataFrame({"x": [1, 2, 3]})
    assert profile_table(df)["exact_duplicates"] == 0
