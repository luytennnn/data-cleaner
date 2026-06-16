from cleaner.errors import ColumnNotFoundError, DataCleanerError


# Coerce para texto: NaN/None → "" (string vazia normalizada, §5)
def _coerce(s):
    return s.astype("string").fillna("")


# Operações de normalização disponíveis (config da UI escolhe por coluna)
_OPS = {
    "trim": lambda s: s.str.strip(),
    "lowercase": lambda s: s.str.lower(),
    # email = trim + lowercase
    "email": lambda s: s.str.strip().str.lower(),
    # telefone = só dígitos (remove +, espaços, traços, parênteses)
    "phone": lambda s: s.str.replace(r"\D", "", regex=True),
}


# Aplica as operações por coluna; devolve novo DataFrame (não muta o input)
def normalize(df, config):
    out = df.copy()
    for col, ops in config.items():
        if col not in out.columns:
            raise ColumnNotFoundError(
                f"Column '{col}' not found. Available: {list(out.columns)}"
            )
        s = _coerce(out[col])
        for op in ops:
            if op not in _OPS:
                raise DataCleanerError(
                    f"Unknown normalization '{op}'. Valid: {list(_OPS)}"
                )
            s = _OPS[op](s)
        out[col] = s
    return out
