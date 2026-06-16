import random

import pandas as pd
import pytest

from cleaner.errors import ColumnNotFoundError, InvalidConfigError
from cleaner.dedup import AUDIT_COLUMNS
from cleaner.linkage import (
    PROB_AUDIT_COLUMNS,
    build_settings,
    dedupe_records,
    link_records,
)


# Fixture sintética com sinal claro: N pessoas, cada uma com 2-3 registos
# variados (typos no nome, email alternativo). Determinística (seed própria).
# EM precisa de volume + variação para treinar (plan §6, aviso T1).
def _make_dupes(n_people=20, seed=0):
    rng = random.Random(seed)
    first = ["Ana", "Joao", "Maria", "Rui", "Carlos", "Sofia", "Pedro", "Ines",
             "Luis", "Rita", "Tiago", "Marta", "Nuno", "Sara", "Bruno",
             "Catarina", "Diogo", "Beatriz", "Hugo", "Vera"]
    last = ["Silva", "Pereira", "Costa", "Mendes", "Lopes", "Marques", "Alves",
            "Fonseca", "Santos", "Dias"]

    def typo(s):
        if len(s) < 4:
            return s
        i = rng.randint(1, len(s) - 2)
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]

    rows = []
    uid = 0
    for f in first[:n_people]:
        l = rng.choice(last)
        name0, email0 = f"{f} {l}", f"{f.lower()}.{l.lower()}@mail.com"
        for k in range(rng.choice([2, 3])):
            name = name0 if k == 0 else (typo(name0) if rng.random() < 0.5 else name0)
            email = email0 if rng.random() < 0.7 else f"{f.lower()}@alt.com"
            rows.append({"unique_id": uid, "name": name, "email": email, "person": f})
            uid += 1
    return pd.DataFrame(rows)


def _dedupe_config(threshold=0.5, seed=42):
    return {
        "comparisons": {"name": "name", "email": "email"},
        "threshold": threshold,
        "seed": seed,
    }


# §3: registos prováveis da mesma pessoa são agrupados/removidos;
# auditoria lista cada grupo com match_probability.
def test_dedupe_groups_probable_duplicates():
    df = _make_dupes()
    clean, audit = dedupe_records(df, _dedupe_config(threshold=0.5))
    assert len(clean) < len(df)              # houve fusões
    assert len(audit) > 0                    # grupos reportados
    assert "match_probability" in audit.columns
    assert audit["match_probability"].between(0, 1).all()
    # pureza: nunca funde pessoas diferentes (sem falsos positivos no fixture)
    kept_people = clean["person"]
    assert kept_people.nunique() == df["person"].nunique()


# §3: threshold mais alto → nº de matches (removidos) menor ou igual (monótono)
def test_dedupe_threshold_monotonic():
    df = _make_dupes()
    _, audit_low = dedupe_records(df, _dedupe_config(threshold=0.5))
    _, audit_high = dedupe_records(df, _dedupe_config(threshold=0.99))
    removed_low = int(audit_low["n_duplicates"].sum())
    removed_high = int(audit_high["n_duplicates"].sum())
    assert removed_high <= removed_low


# §3: mesma input + mesma seed → resultado idêntico (reprodutível)
def test_dedupe_reproducible_with_seed():
    df = _make_dupes()
    clean1, audit1 = dedupe_records(df, _dedupe_config(threshold=0.5, seed=42))
    clean2, audit2 = dedupe_records(df, _dedupe_config(threshold=0.5, seed=42))
    pd.testing.assert_frame_equal(clean1, clean2)
    pd.testing.assert_frame_equal(audit1, audit2)


# §5: coluna de comparação inexistente → erro claro
def test_dedupe_missing_column_raises():
    df = _make_dupes()
    cfg = {"comparisons": {"nope": "name"}, "threshold": 0.5}
    with pytest.raises(ColumnNotFoundError):
        dedupe_records(df, cfg)


# §5/§4: config sem colunas de comparação → erro claro
def test_dedupe_empty_comparisons_raises():
    df = _make_dupes()
    with pytest.raises(InvalidConfigError):
        dedupe_records(df, {"comparisons": {}, "threshold": 0.5})


# ---- T4: link_records (2 ficheiros) ----

# Dois ficheiros com correspondências conhecidas: cada pessoa comum aparece
# em A (original) e B (com typo no nome); cada lado tem exclusivos.
def _make_link_pair(n_common=14, seed=1):
    df = _make_dupes(n_people=20, seed=seed)
    # 1 registo por pessoa, ordenado, determinístico
    one = df.sort_values("unique_id").groupby("person", sort=False).first().reset_index()
    people = list(one["person"])
    common = people[:n_common]
    a_people = common + people[n_common:n_common + 3]      # comuns + exclusivos A
    b_people = common + people[n_common + 3:]              # comuns + exclusivos B

    def build(plist, mangle):
        rows = []
        for uid, p in enumerate(plist):
            r = one[one["person"] == p].iloc[0]
            name = r["name"]
            if mangle and len(name) > 4:
                name = name[:2] + name[3] + name[2] + name[4:]  # typo no lado B
            rows.append({"unique_id": uid, "name": name, "email": r["email"], "person": p})
        return pd.DataFrame(rows)

    return build(a_people, False), build(b_people, True), set(common)


def _link_config(threshold=0.5, seed=42):
    return {"comparisons": {"name": "name", "email": "email"},
            "threshold": threshold, "seed": seed}


# §3: liga registos correspondentes entre 2 ficheiros, com match_probability
def test_link_finds_known_pairs():
    df_a, df_b, common = _make_link_pair()
    pairs, audit = link_records(df_a, df_b, _link_config(threshold=0.5))
    assert len(pairs) > 0
    assert "match_probability" in pairs.columns
    assert pairs["match_probability"].between(0, 1).all()
    # os pares ligam mesma pessoa (pureza) e cobrem parte dos comuns
    a_person = df_a.set_index("unique_id")["person"]
    b_person = df_b.set_index("unique_id")["person"]
    matched_people = {a_person[a] for a, b in zip(pairs["index_a"], pairs["index_b"])
                      if a_person[a] == b_person[b]}
    assert matched_people  # pelo menos um par correto
    assert all(a_person[a] == b_person[b]
               for a, b in zip(pairs["index_a"], pairs["index_b"]))  # 0 falsos+


# §3: threshold mais alto → menos ou iguais pares (monótono)
def test_link_threshold_monotonic():
    df_a, df_b, _ = _make_link_pair()
    pairs_low, _ = link_records(df_a, df_b, _link_config(threshold=0.5))
    pairs_high, _ = link_records(df_a, df_b, _link_config(threshold=0.99))
    assert len(pairs_high) <= len(pairs_low)


# §5: 0 colunas a comparar → erro claro
def test_link_empty_comparisons_raises():
    df_a, df_b, _ = _make_link_pair()
    with pytest.raises(InvalidConfigError):
        link_records(df_a, df_b, {"comparisons": {}, "threshold": 0.5})


# §5: coluna em falta num dos ficheiros → erro claro
def test_link_missing_column_raises():
    df_a, df_b, _ = _make_link_pair()
    with pytest.raises(ColumnNotFoundError):
        link_records(df_a, df_b.drop(columns=["email"]), _link_config())


# ---- T5: auditoria compatível com v1 ----

# §3: auditoria do dedupe usa o schema do v1 + match_probability, com "key"
def test_dedupe_audit_schema_matches_v1():
    df = _make_dupes()
    _, audit = dedupe_records(df, _dedupe_config(threshold=0.5))
    assert list(audit.columns) == PROB_AUDIT_COLUMNS
    # schema do v1 é prefixo do schema probabilístico (compatível para juntar)
    assert PROB_AUDIT_COLUMNS[:len(AUDIT_COLUMNS)] == AUDIT_COLUMNS
    assert audit.iloc[0]["method"] == "probabilistic"
    assert audit.iloc[0]["key"]  # key não vazia (valores das colunas comparadas)


# §5: sem pares acima do threshold → output == input, auditoria vazia com schema
def test_dedupe_no_matches_empty_audit():
    df = _make_dupes()
    clean, audit = dedupe_records(df, _dedupe_config(threshold=0.999))
    assert len(clean) == len(df)          # output = input
    assert audit.empty
    assert list(audit.columns) == PROB_AUDIT_COLUMNS


# ---- T7: match-weights chart (motor) ----

# §3: with_chart=True devolve o waterfall de match-weights (Altair) para a app
def test_dedupe_with_chart_returns_altair():
    df = _make_dupes()
    clean, audit, chart = dedupe_records(df, _dedupe_config(threshold=0.5), with_chart=True)
    assert "altair" in type(chart).__module__   # objeto embeddable em st.altair_chart


def test_link_with_chart_returns_altair():
    df_a, df_b, _ = _make_link_pair()
    pairs, audit, chart = link_records(df_a, df_b, _link_config(threshold=0.5), with_chart=True)
    assert "altair" in type(chart).__module__


# T2 §4: config conhecida → settings válidas do Splink
def test_build_settings_maps_comparison_types():
    sc = build_settings({"name": "name", "email": "email"})
    d = sc.create_settings_dict("duckdb")  # gera/valida o dict do Splink
    assert d["link_type"] == "dedupe_only"
    assert len(d["comparisons"]) == 2
    outputs = [c["output_column_name"] for c in d["comparisons"]]
    assert outputs == ["name", "email"]


# Os 5 tipos curados mapeiam todos para comparisons válidas do Splink
def test_build_settings_all_comparison_types():
    cfg = {"a": "exact", "b": "name", "c": "email", "d": "phone", "e": "date"}
    d = build_settings(cfg).create_settings_dict("duckdb")
    assert len(d["comparisons"]) == 5


# link_type link_only para o modo de 2 ficheiros (T4)
def test_build_settings_link_only():
    sc = build_settings({"email": "email"}, link_type="link_only")
    assert sc.create_settings_dict("duckdb")["link_type"] == "link_only"


# Sem blocking explícito → uma regra por cada coluna de comparação
def test_blocking_defaults_to_comparison_columns():
    d = build_settings({"name": "name", "email": "email"}).create_settings_dict("duckdb")
    rules = [r["blocking_rule"] for r in d["blocking_rules_to_generate_predictions"]]
    assert len(rules) == 2
    assert any("name" in r for r in rules)
    assert any("email" in r for r in rules)


# Blocking explícito é respeitado (não deriva das comparações)
def test_blocking_explicit_columns():
    d = build_settings(
        {"name": "name", "email": "email"}, blocking_columns=["email"]
    ).create_settings_dict("duckdb")
    rules = d["blocking_rules_to_generate_predictions"]
    assert len(rules) == 1
    assert "email" in rules[0]["blocking_rule"]


# §5: tipo de comparação desconhecido → erro claro
def test_unknown_comparison_type_raises():
    with pytest.raises(InvalidConfigError):
        build_settings({"name": "bogus"})


# §5: 0 colunas a comparar → erro claro (suporta T4 §5)
def test_empty_comparison_config_raises():
    with pytest.raises(InvalidConfigError):
        build_settings({})
