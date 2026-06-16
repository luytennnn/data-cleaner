from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


# Boot do app sem ficheiro carregado: corre o script real in-process, sem crash.
def test_app_boots_without_upload():
    at = AppTest.from_file(APP).run()
    assert not at.exception
    # Sem upload mostra o aviso inicial e para
    assert any("Upload a file to begin" in i.value for i in at.info)


# Título e caption renderizam
def test_app_renders_title():
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert any("Data Cleaner" in t.value for t in at.title)


def _set_multiselect(at, label, value):
    for ms in at.multiselect:
        if ms.label == label:
            ms.set_value(value)
            return
    raise AssertionError(f"multiselect '{label}' not found")


# End-to-end na app: upload com duplicados → dedup exato → sucesso + auditoria
def test_app_full_dedup_flow():
    csv = b"name,city\nAna,Lisboa\nBeto,Porto\nAna,Lisboa\n"
    at = AppTest.from_file(APP)
    at.run()
    at.file_uploader[0].upload("contacts.csv", csv, "text/csv")
    at.run()
    # Profile aparece com 3 linhas e 1 duplicado exato
    assert any(m.value == "3" for m in at.metric)
    _set_multiselect(at, "Key columns for deduplication", ["name", "city"])
    at.run()
    at.button[0].click()
    at.run()
    assert not at.exception
    assert any("duplicate row(s) removed" in s.value for s in at.success)


# §5: ficheiro só com cabeçalho → erro claro na UI, sem rebentar
def test_app_empty_file_shows_error():
    at = AppTest.from_file(APP)
    at.run()
    at.file_uploader[0].upload("empty.csv", b"name,city\n", "text/csv")
    at.run()
    assert not at.exception
    assert any("no data" in e.value.lower() for e in at.error)
