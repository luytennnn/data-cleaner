import pandas as pd
import pytest

from cleaner.errors import ColumnNotFoundError
from cleaner.dedup import AUDIT_COLUMNS, dedup_exact, dedup_fuzzy


def test_exact_removes_identical_key_rows():
    df = pd.DataFrame({"name": ["Ana", "Beto", "Ana"], "city": ["Lisboa", "Porto", "Lisboa"]})
    clean, audit = dedup_exact(df, ["name", "city"])
    assert len(clean) == 2
    assert clean["name"].tolist() == ["Ana", "Beto"]


# §3: nº removido reportado bate certo com o que saiu
def test_exact_removed_count_matches():
    df = pd.DataFrame({"name": ["Ana", "Ana", "Ana", "Beto"]})
    clean, audit = dedup_exact(df, ["name"])
    removed_reported = int(audit["n_duplicates"].sum())
    assert removed_reported == len(df) - len(clean) == 2


# §3: auditoria lista grupo, registo mantido e removidos
def test_exact_audit_contents():
    df = pd.DataFrame({"name": ["Ana", "Beto", "Ana"]})
    clean, audit = dedup_exact(df, ["name"])
    assert list(audit.columns) == AUDIT_COLUMNS
    assert len(audit) == 1  # um grupo duplicado
    row = audit.iloc[0]
    assert row["method"] == "exact"
    assert row["kept_index"] == 0
    assert row["removed_indices"] == "2"
    assert row["n_duplicates"] == 1


def test_exact_keeps_first_occurrence():
    df = pd.DataFrame({"name": ["Ana", "Ana"], "note": ["keep", "drop"]})
    clean, _ = dedup_exact(df, ["name"])
    assert clean["note"].tolist() == ["keep"]


def test_exact_dedups_only_on_keys():
    # mesma chave, outras colunas diferentes → ainda funde (keep first)
    df = pd.DataFrame({"name": ["Ana", "Ana"], "age": [30, 99]})
    clean, _ = dedup_exact(df, ["name"])
    assert len(clean) == 1
    assert clean.iloc[0]["age"] == 30


def test_exact_no_duplicates_empty_audit():
    df = pd.DataFrame({"name": ["Ana", "Beto"]})
    clean, audit = dedup_exact(df, ["name"])
    assert len(clean) == 2
    assert len(audit) == 0
    assert list(audit.columns) == AUDIT_COLUMNS


# §5: coluna-chave inexistente → erro claro a listar colunas
def test_exact_missing_key_raises():
    df = pd.DataFrame({"name": ["Ana"]})
    with pytest.raises(ColumnNotFoundError):
        dedup_exact(df, ["nope"])


# ---- Dedup fuzzy ----

# §3: registos semelhantes acima do threshold são agrupados
def test_fuzzy_groups_similar_names():
    df = pd.DataFrame({"name": ["João Silva", "joao silva", "Maria"]})
    clean, audit = dedup_fuzzy(df, ["name"], threshold=85)
    assert len(clean) == 2
    assert clean["name"].tolist() == ["João Silva", "Maria"]
    assert len(audit) == 1
    assert audit.iloc[0]["method"] == "fuzzy"
    assert audit.iloc[0]["kept_index"] == 0
    assert audit.iloc[0]["removed_indices"] == "1"


# token_sort_ratio é robusto a ordem de palavras DENTRO do mesmo bloco.
# (Ordem trocada que muda o 1º caráter cai em blocos distintos — trade-off do
# blocking documentado no plan §5; ver test abaixo.)
def test_fuzzy_handles_word_order_same_block():
    df = pd.DataFrame({"name": ["Maria Joao Silva", "Maria Silva Joao"]})
    clean, _ = dedup_fuzzy(df, ["name"], threshold=90)
    assert len(clean) == 1


# Trade-off do blocking (plan §5): ordem trocada que muda o prefixo não funde
def test_fuzzy_word_swap_across_blocks_not_merged():
    df = pd.DataFrame({"name": ["Joao Silva", "Silva Joao"]})
    clean, _ = dedup_fuzzy(df, ["name"], threshold=90, block_size=1)
    assert len(clean) == 2


# Abaixo do threshold não agrupa
def test_fuzzy_below_threshold_not_grouped():
    df = pd.DataFrame({"name": ["joao silva", "maria costa"]})
    clean, audit = dedup_fuzzy(df, ["name"], threshold=85)
    assert len(clean) == 2
    assert len(audit) == 0


# §5: blocking por prefixo — semelhantes em blocos diferentes NÃO se comparam
def test_fuzzy_blocking_prevents_cross_block_match():
    # "ana"/"ena" são parecidos mas começam por letras diferentes → blocos distintos
    df = pd.DataFrame({"name": ["ana", "ena"]})
    clean, _ = dedup_fuzzy(df, ["name"], threshold=50, block_size=1)
    assert len(clean) == 2  # blocking impede a fusão (trade-off aceite, plan §5)


# Blocking usa a chave normalizada (lower) → maiúsculas não separam blocos
def test_fuzzy_blocking_case_insensitive():
    df = pd.DataFrame({"name": ["João Silva", "joao silva"]})
    clean, _ = dedup_fuzzy(df, ["name"], threshold=85, block_size=1)
    assert len(clean) == 1  # "J" e "j" caem no mesmo bloco


def test_fuzzy_missing_key_raises():
    df = pd.DataFrame({"name": ["Ana"]})
    with pytest.raises(ColumnNotFoundError):
        dedup_fuzzy(df, ["nope"])
