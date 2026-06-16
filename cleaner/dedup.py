import pandas as pd
from rapidfuzz import fuzz

from cleaner.errors import ColumnNotFoundError

# Schema fixo da auditoria — partilhado entre dedup exato e fuzzy
AUDIT_COLUMNS = [
    "group_id",
    "method",
    "key",
    "kept_index",
    "removed_indices",
    "n_duplicates",
]


# Confirma que todas as colunas-chave existem (§5)
def _validate_keys(df, keys):
    missing = [k for k in keys if k not in df.columns]
    if missing:
        raise ColumnNotFoundError(
            f"Key column(s) {missing} not found. Available: {list(df.columns)}"
        )


# Junta as colunas-chave numa string; NaN → "" (não funde com dados reais, §5)
def _combined_key(df, keys):
    return df[keys].astype("string").fillna("").agg(" | ".join, axis=1)


# Constrói o DataFrame de auditoria com o schema fixo (vazio se sem grupos)
def _audit_df(rows):
    return pd.DataFrame(rows, columns=AUDIT_COLUMNS)


# Remove linhas idênticas nas colunas-chave; mantém a 1ª ocorrência.
# Devolve (df_limpo, df_auditoria com um registo por grupo duplicado).
def dedup_exact(df, keys):
    _validate_keys(df, keys)
    key = _combined_key(df, keys)

    # Agrupa índices por chave, preservando ordem de aparição
    groups = {}
    for idx, k in zip(df.index, key):
        groups.setdefault(k, []).append(idx)

    rows = []
    gid = 0
    for k, members in groups.items():
        if len(members) > 1:
            gid += 1
            kept, removed = members[0], members[1:]
            rows.append(
                {
                    "group_id": gid,
                    "method": "exact",
                    "key": k,
                    "kept_index": kept,
                    "removed_indices": ",".join(str(i) for i in removed),
                    "n_duplicates": len(removed),
                }
            )

    kept_idx = [members[0] for members in groups.values()]
    clean = df.loc[kept_idx]
    return clean, _audit_df(rows)


# Dedup fuzzy: agrupa registos semelhantes acima do threshold (0-100).
# Blocking por prefixo da chave NORMALIZADA (lower) para não comparar tudo-com-tudo.
# Clustering guloso: cada registo compara só com os representantes já vistos no bloco.
def dedup_fuzzy(df, keys, threshold=85, scorer=None, block_size=1):
    _validate_keys(df, keys)
    if scorer is None:
        scorer = fuzz.token_sort_ratio
    key = _combined_key(df, keys)
    mkey = key.str.lower()  # chave de matching: blocking + scoring

    # Agrupa por prefixo (bloco); só compara registos do mesmo bloco
    blocks = {}
    for idx, mk in zip(df.index, mkey):
        blocks.setdefault(mk[:block_size], []).append((idx, mk))

    removed_set = set()
    rows = []
    gid = 0
    for members in blocks.values():
        reps = []  # representantes do bloco: {idx, key, removed[]}
        for idx, mk in members:
            match = next((r for r in reps if scorer(mk, r["key"]) >= threshold), None)
            if match is None:
                reps.append({"idx": idx, "key": mk, "removed": []})
            else:
                match["removed"].append(idx)
                removed_set.add(idx)
        for r in reps:
            if r["removed"]:
                gid += 1
                rows.append(
                    {
                        "group_id": gid,
                        "method": "fuzzy",
                        "key": r["key"],
                        "kept_index": r["idx"],
                        "removed_indices": ",".join(str(i) for i in r["removed"]),
                        "n_duplicates": len(r["removed"]),
                    }
                )

    clean = df.loc[[i for i in df.index if i not in removed_set]]
    return clean, _audit_df(rows)
