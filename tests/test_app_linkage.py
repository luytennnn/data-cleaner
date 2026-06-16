from pathlib import Path

from streamlit.testing.v1 import AppTest

from tests.test_linkage import _make_dupes, _make_link_pair

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _set_radio(at, label, value):
    for r in at.radio:
        if r.label == label:
            r.set_value(value)
            return
    raise AssertionError(f"radio '{label}' not found")


def _set_multiselect(at, label, value):
    for ms in at.multiselect:
        if ms.label == label:
            ms.set_value(value)
            return
    raise AssertionError(f"multiselect '{label}' not found")


def _set_selectbox(at, label, value):
    for sb in at.selectbox:
        if sb.label == label:
            sb.set_value(value)
            return
    raise AssertionError(f"selectbox '{label}' not found")


def _set_slider(at, label, value):
    for s in at.slider:
        if s.label == label:
            s.set_value(value)
            return
    raise AssertionError(f"slider '{label}' not found")


# §3: modo Deduplicate (probabilístico) end-to-end → sucesso, auditoria, downloads
def test_app_dedupe_prob_end_to_end():
    csv = _make_dupes().to_csv(index=False).encode()
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    _set_radio(at, "Mode", "Deduplicate (probabilistic)")
    at.run()
    at.file_uploader[0].upload("data.csv", csv, "text/csv")
    at.run()
    _set_multiselect(at, "Columns to compare", ["name", "email"])
    at.run()
    _set_selectbox(at, "Comparison type for 'name'", "name")
    _set_selectbox(at, "Comparison type for 'email'", "email")
    _set_slider(at, "Match probability threshold", 0.50)
    at.run()
    at.button[0].click()
    at.run()
    assert not at.exception
    assert any("removed" in s.value for s in at.success)
    # T7: a secção de match-weights (chart) e auditoria renderiza até ao fim
    assert any("Match weights" in m.value for m in at.markdown)
    assert any("Audit" in m.value for m in at.markdown)


# §5: run sem escolher colunas → aviso claro, sem crash
def test_app_dedupe_prob_no_columns_warns():
    csv = _make_dupes().to_csv(index=False).encode()
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    _set_radio(at, "Mode", "Deduplicate (probabilistic)")
    at.run()
    at.file_uploader[0].upload("data.csv", csv, "text/csv")
    at.run()
    at.button[0].click()
    at.run()
    assert not at.exception
    assert any("at least one column" in w.value.lower() for w in at.warning)


# §3: modo Link end-to-end com 2 ficheiros → sucesso e pares
def test_app_link_end_to_end():
    df_a, df_b, _ = _make_link_pair()
    csv_a = df_a.to_csv(index=False).encode()
    csv_b = df_b.to_csv(index=False).encode()
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    _set_radio(at, "Mode", "Link two files")
    at.run()
    at.file_uploader[0].upload("a.csv", csv_a, "text/csv")
    at.file_uploader[1].upload("b.csv", csv_b, "text/csv")
    at.run()
    _set_multiselect(at, "Columns to compare", ["name", "email"])
    at.run()
    _set_selectbox(at, "Comparison type for 'name'", "name")
    _set_selectbox(at, "Comparison type for 'email'", "email")
    _set_slider(at, "Match probability threshold", 0.50)
    at.run()
    at.button[0].click()
    at.run()
    assert not at.exception
    assert any("matching pair" in s.value for s in at.success)
