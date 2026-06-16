# Record linkage probabilístico (data-cleaner v2) — motor sobre Splink 4 (DuckDB).
# v1 (io/profile/normalize/dedup) fica INTACTO; este módulo só acrescenta.
#
# ---------------------------------------------------------------------------
# NOTA DE API — Splink 4.0.16 (confirmado na doc oficial, 2026-06-16, narada)
# https://moj-analytical-services.github.io/splink/getting_started.html
# A API mudou MUITO do v3 → v4; não assumir assinaturas antigas. Resumo real:
#
# Imports (tudo a partir de `splink`, sem submódulo `duckdb`):
#   from splink import DuckDBAPI, Linker, SettingsCreator, block_on
#   import splink.comparison_library as cl
#
# Backend + Linker:
#   db_api = DuckDBAPI()
#   linker = Linker(df, settings, db_api)            # link_only: Linker([df_a, df_b], ...)
#
# Settings:
#   SettingsCreator(link_type="dedupe_only"|"link_only"|"link_and_dedupe",
#                   comparisons=[...],
#                   blocking_rules_to_generate_predictions=[block_on("col"), ...])
#
# Comparisons (cl.*):
#   cl.ExactMatch(col_name)
#   cl.NameComparison(col_name)
#   cl.EmailComparison(col_name)
#   cl.LevenshteinAtThresholds(col_name, [1, 2])
#   cl.DateOfBirthComparison(col_name, input_is_string=True)   # input_is_string OBRIGATÓRIO
#
# Blocking:
#   block_on("col1", "col2")                          # variadic posicional (v3 usava SQL)
#
# Treino (namespace linker.training):
#   linker.training.estimate_probability_two_random_records_match(deterministic_rules, recall=...)
#   linker.training.estimate_u_using_random_sampling(max_pairs=1e6, seed=42)   # seed EXISTE
#   linker.training.estimate_parameters_using_expectation_maximisation(block_on("col"))
#
# Predição (namespace linker.inference):
#   linker.inference.predict(threshold_match_probability=0.9)  -> SplinkDataFrame
#   .as_pandas_dataframe()  -> colunas inc. unique_id_l, unique_id_r, match_probability
#
# Clustering (namespace linker.clustering):
#   linker.clustering.cluster_pairwise_predictions_at_threshold(preds, 0.9)
#   .as_pandas_dataframe() -> cluster_id + colunas originais
#
# Visualização (namespace linker.visualisations):
#   linker.visualisations.match_weights_chart()       # waterfall Altair p/ T7
#
# Runtime confirmado: splink 4.0.16 + duckdb 1.5.3 + igraph 1.0.0 a correr com
# pandas 3.0.3 / numpy 2.4.6 / Python 3.13 no Windows (wheels, sem build C).
# Dedupe trivial end-to-end OK; EM com fixtures minúsculas é instável (plan §6) → T3.
# ---------------------------------------------------------------------------

import logging

import pandas as pd
from splink import DuckDBAPI, Linker, SettingsCreator, block_on
import splink.comparison_library as cl

from cleaner.dedup import AUDIT_COLUMNS
from cleaner.errors import ColumnNotFoundError, DataCleanerError, InvalidConfigError

# Auditoria probabilística = schema do v1 (dedup) + match_probability.
# v1 é prefixo → as auditorias juntam-se sem reformatar (plan §2).
PROB_AUDIT_COLUMNS = AUDIT_COLUMNS + ["match_probability"]

# Splink é verboso (INFO por iteração do EM) — silenciar abaixo de WARNING.
logging.getLogger("splink").setLevel(logging.WARNING)

# Seed fixa por defeito → resultados reprodutíveis (spec §3, plan §2)
DEFAULT_SEED = 42

# Coluna de id interna do motor — evita colidir com colunas do utilizador.
_UID = "__dc_uid"

# Tipos de comparação curados → fábrica do comparison_library do Splink 4.
# Esconde os internos do Splink ao utilizador da app (plan §2).
COMPARISON_BUILDERS = {
    "exact": lambda col: cl.ExactMatch(col),
    "name": lambda col: cl.NameComparison(col),
    "email": lambda col: cl.EmailComparison(col),
    "phone": lambda col: cl.LevenshteinAtThresholds(col, [1, 2]),
    "date": lambda col: cl.DateOfBirthComparison(col, input_is_string=True),
}

COMPARISON_TYPES = tuple(COMPARISON_BUILDERS)


# Mapeia {coluna: tipo} para a lista de comparisons do Splink.
def _build_comparisons(comparison_config):
    if not comparison_config:
        raise InvalidConfigError("Choose at least one column to compare.")
    comparisons = []
    for col, ctype in comparison_config.items():
        builder = COMPARISON_BUILDERS.get(ctype)
        if builder is None:
            raise InvalidConfigError(
                f"Unknown comparison type '{ctype}' for column '{col}'. "
                f"Valid types: {list(COMPARISON_TYPES)}"
            )
        comparisons.append(builder(col))
    return comparisons


# Blocking rules: gera só pares candidatos onde uma coluna bate exato.
# Sem blocking explícito → uma regra por cada coluna de comparação (trade-off:
# evita comparar tudo-com-tudo; pares onde nenhuma coluna bate exato escapam).
def _build_blocking(comparison_config, blocking_columns):
    cols = blocking_columns if blocking_columns else list(comparison_config)
    return [block_on(c) for c in cols]


# Constrói o SettingsCreator do Splink a partir da config curada.
# link_type: "dedupe_only" (1 ficheiro) ou "link_only" (2 ficheiros).
def build_settings(
    comparison_config, blocking_columns=None, link_type="dedupe_only",
    unique_id_column=None,
):
    kwargs = {}
    if unique_id_column is not None:
        kwargs["unique_id_column_name"] = unique_id_column
    return SettingsCreator(
        link_type=link_type,
        comparisons=_build_comparisons(comparison_config),
        blocking_rules_to_generate_predictions=_build_blocking(
            comparison_config, blocking_columns
        ),
        **kwargs,
    )


# Confirma que todas as colunas de comparação existem no df (§5)
def _validate_columns(df, comparison_config, label="DataFrame"):
    missing = [c for c in comparison_config if c not in df.columns]
    if missing:
        raise ColumnNotFoundError(
            f"Comparison column(s) {missing} not found in {label}. "
            f"Available: {list(df.columns)}"
        )


# Colunas de blocking que produzem ≥1 par exato (logo treináveis no EM sem
# rebentar). frames=[df] no dedupe; frames=[df_a, df_b] no link.
def _blocking_cols_with_pairs(frames, cols):
    out = []
    for c in cols:
        if len(frames) == 1:
            if frames[0][c].dropna().duplicated().any():
                out.append(c)
        elif set(frames[0][c].dropna()) & set(frames[1][c].dropna()):
            out.append(c)
    return out


# Sequência de treino do Splink 4 (confirmada na nota de API no topo).
# Treina o EM bloqueando por cada coluna COM pares exatos → deixa as outras
# variar (sinal m). Pré-filtra as colunas: uma rule sem pares lança uma exceção
# que corrompe o estado do linker (chamadas seguintes falham), por isso nunca
# se tenta uma coluna sem pares. Erro claro se nenhuma coluna for treinável (§5).
def _train(linker, comparison_config, blocking_columns, seed, frames):
    cols = blocking_columns if blocking_columns else list(comparison_config)
    trainable = _blocking_cols_with_pairs(frames, cols)
    if not trainable:
        raise DataCleanerError(
            "Not enough exact matches on any column to train the model. "
            "Choose columns that share some exact values, or clean the data first."
        )
    det_rules = [f'l."{c}" = r."{c}"' for c in trainable]
    linker.training.estimate_probability_two_random_records_match(det_rules, recall=0.9)
    linker.training.estimate_u_using_random_sampling(max_pairs=1e6, seed=seed)
    for c in trainable:
        linker.training.estimate_parameters_using_expectation_maximisation(block_on(c))
    return len(trainable)


# Dedup probabilístico de 1 ficheiro. config: comparisons (col→tipo), threshold,
# seed, blocking (opcional). Devolve (df_limpo, auditoria com match_probability).
# with_chart=True → devolve também o waterfall de match-weights (Altair) para a app.
def dedupe_records(df, config, with_chart=False):
    comparison_config = config.get("comparisons") or {}
    # cap a <1.0: o Splink rebenta o SQL com threshold exatamente 1.0
    threshold = min(config.get("threshold", 0.9), 0.999)
    seed = config.get("seed", DEFAULT_SEED)
    blocking = config.get("blocking")
    if not comparison_config:
        raise InvalidConfigError("Choose at least one column to compare.")
    _validate_columns(df, comparison_config)

    work = df.copy()
    work[_UID] = range(len(work))  # id interno posicional
    settings = build_settings(
        comparison_config, blocking, link_type="dedupe_only", unique_id_column=_UID
    )
    try:
        linker = Linker(work, settings, DuckDBAPI())
        _train(linker, comparison_config, blocking, seed, [work])
        preds = linker.inference.predict(threshold_match_probability=threshold)
        clusters = linker.clustering.cluster_pairwise_predictions_at_threshold(
            preds, threshold
        )
        cdf = clusters.as_pandas_dataframe()
        pdf = preds.as_pandas_dataframe()
    except DataCleanerError:
        raise  # mensagem já clara (ex.: sem pares para treinar)
    except Exception as e:  # §5: EM não converge / dados insuficientes
        raise DataCleanerError(
            f"Probabilistic matching failed (insufficient data or no convergence): {e}"
        )

    clean, audit = _build_dedupe_result(
        df, work, cdf, pdf, threshold, list(comparison_config)
    )
    if with_chart:
        return clean, audit, linker.visualisations.match_weights_chart()
    return clean, audit


# Junta os valores das colunas comparadas num registo → "key" da auditoria (v1)
def _row_key(df, idx, columns):
    vals = df.loc[idx, columns].astype("string").fillna("")
    return " | ".join(vals.tolist())


# Constrói (df_limpo, auditoria) a partir dos clusters e predições do Splink.
# match_probability do grupo = ligação mais fraca (min) que o sustenta — explicável.
def _build_dedupe_result(df, work, cdf, pdf, threshold, columns):
    uid_to_index = dict(zip(work[_UID], work.index))  # id interno → índice original
    uid_to_cluster = dict(zip(cdf[_UID], cdf["cluster_id"]))

    # min(match_probability) por cluster, só de pares dentro do mesmo cluster.
    # Colunas de id seguem o unique_id_column_name → "__dc_uid_l"/"__dc_uid_r".
    cluster_prob = {}
    for uid_l, uid_r, prob in zip(
        pdf[_UID + "_l"], pdf[_UID + "_r"], pdf["match_probability"]
    ):
        cl_l, cl_r = uid_to_cluster.get(uid_l), uid_to_cluster.get(uid_r)
        if cl_l is not None and cl_l == cl_r:
            cluster_prob[cl_l] = min(cluster_prob.get(cl_l, 1.0), prob)

    # Membros por cluster, em ordem de índice original
    members = {}
    for uid, cid in sorted(uid_to_cluster.items(), key=lambda kv: uid_to_index[kv[0]]):
        members.setdefault(cid, []).append(uid_to_index[uid])

    rows = []
    removed = set()
    gid = 0
    for cid, idxs in members.items():
        if len(idxs) > 1:
            gid += 1
            kept, drop = idxs[0], idxs[1:]
            removed.update(drop)
            rows.append({
                "group_id": gid,
                "method": "probabilistic",
                "key": _row_key(df, kept, columns),
                "kept_index": kept,
                "removed_indices": ",".join(str(i) for i in drop),
                "n_duplicates": len(drop),
                "match_probability": round(float(cluster_prob.get(cid, threshold)), 4),
            })

    audit = pd.DataFrame(rows, columns=PROB_AUDIT_COLUMNS)
    clean = df.loc[[i for i in df.index if i not in removed]]
    return clean, audit


# Liga registos correspondentes entre 2 ficheiros (link_only). config: comparisons,
# threshold, seed, blocking. Devolve (pares acima do threshold, auditoria).
# with_chart=True → devolve também o waterfall de match-weights (Altair).
def link_records(df_a, df_b, config, with_chart=False):
    comparison_config = config.get("comparisons") or {}
    # cap a <1.0: o Splink rebenta o SQL com threshold exatamente 1.0
    threshold = min(config.get("threshold", 0.9), 0.999)
    seed = config.get("seed", DEFAULT_SEED)
    blocking = config.get("blocking")
    if not comparison_config:
        raise InvalidConfigError("Choose at least one column to compare.")
    _validate_columns(df_a, comparison_config, label="file A")
    _validate_columns(df_b, comparison_config, label="file B")

    a = df_a.copy()
    b = df_b.copy()
    a[_UID] = range(len(a))
    b[_UID] = range(len(b))
    idx_a = dict(zip(a[_UID], df_a.index))  # id interno → índice original A
    idx_b = dict(zip(b[_UID], df_b.index))

    settings = build_settings(
        comparison_config, blocking, link_type="link_only", unique_id_column=_UID
    )
    try:
        linker = Linker([a, b], settings, DuckDBAPI(), input_table_aliases=["A", "B"])
        _train(linker, comparison_config, blocking, seed, [a, b])
        preds = linker.inference.predict(threshold_match_probability=threshold)
        pdf = preds.as_pandas_dataframe()
    except DataCleanerError:
        raise  # mensagem já clara (ex.: sem pares para treinar)
    except Exception as e:  # §5: dados insuficientes / sem convergência
        raise DataCleanerError(
            f"Probabilistic linking failed (insufficient data or no convergence): {e}"
        )

    pairs, audit = _build_link_result(pdf, idx_a, idx_b, threshold)
    if with_chart:
        return pairs, audit, linker.visualisations.match_weights_chart()
    return pairs, audit


# Constrói (pares, auditoria) do predict link_only. Usa source_dataset para
# atribuir cada lado a A/B, independente da ordem l/r do Splink.
def _build_link_result(pdf, idx_a, idx_b, threshold):
    rows = []
    for _, r in pdf.iterrows():
        if r["source_dataset_l"] == "A":
            ua, ub = r[_UID + "_l"], r[_UID + "_r"]
        else:
            ua, ub = r[_UID + "_r"], r[_UID + "_l"]
        rows.append({
            "index_a": idx_a[ua],
            "index_b": idx_b[ub],
            "match_probability": round(float(r["match_probability"]), 4),
        })

    pairs = pd.DataFrame(rows, columns=["index_a", "index_b", "match_probability"])
    pairs = pairs.sort_values("match_probability", ascending=False).reset_index(drop=True)
    audit = pairs.copy()
    audit.insert(0, "method", "link")
    return pairs, audit
