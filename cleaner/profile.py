import pandas as pd


# Resumo do DataFrame para a UI mostrar antes de limpar
def profile_table(df):
    n_rows = len(df)
    # % de nulos por coluna, arredondada a 2 casas
    null_pct = {
        col: round(df[col].isna().mean() * 100, 2) if n_rows else 0.0
        for col in df.columns
    }
    return {
        "n_rows": n_rows,
        "n_cols": df.shape[1],
        "columns": list(df.columns),
        "dtypes": {col: str(dt) for col, dt in df.dtypes.items()},
        "null_pct": null_pct,
        # duplicados exatos = linhas redundantes (exclui a 1ª ocorrência)
        "exact_duplicates": int(df.duplicated().sum()),
    }
