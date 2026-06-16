# 🧹 Data Cleaner

Profile, normalize and deduplicate any CSV or Excel file — a reusable Python engine
wrapped in a Streamlit app. Built to speed up data-cleaning gigs and deliver a
deduplicated, **auditable** dataset to clients.

## Features

- **Profile** — rows, columns, dtypes, % nulls per column, exact-duplicate count.
- **Normalize** — per-column `trim`, `lowercase`, `email` (trim + lowercase),
  `phone` (digits only). Nulls become normalized empty strings.
- **Deduplicate**
  - *Exact* — drop identical rows on the chosen key columns.
  - *Fuzzy* — `rapidfuzz` token-sort similarity above a threshold, with **blocking**
    by key prefix so large files (45k+ rows) don't compare everything-with-everything.
- **Audit trail** — a downloadable table of every duplicate group: which record was
  kept and which were removed.
- **Download** cleaned data and audit as CSV or Excel.

## Project structure

```
cleaner/        # Engine — independent of the UI, fully unit-tested
  io.py         # read/write CSV & Excel, sheet selection, clear errors
  profile.py    # DataFrame profile
  normalize.py  # configurable normalization
  dedup.py      # exact + fuzzy dedup with blocking, shared audit schema
  errors.py     # clear, UI-friendly exceptions
app.py          # Streamlit UI: upload → profile → controls → preview → download
tests/          # pytest, incl. in-process app tests (streamlit AppTest)
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the app

```powershell
streamlit run app.py
```

Then open the URL Streamlit prints (default http://localhost:8501).

## Run the tests

```powershell
pytest -q
```

## Use the engine directly

```python
import pandas as pd
from cleaner.normalize import normalize
from cleaner.dedup import dedup_exact, dedup_fuzzy

df = pd.read_csv("contacts.csv")
df = normalize(df, {"name": ["trim", "lowercase"], "email": ["email"]})
clean, audit = dedup_fuzzy(df, keys=["name"], threshold=85, block_size=1)
```

## Out of scope (v1)

- No probabilistic / ML record linkage (planned for v2).
- No database or API connections — uploaded files only.
- No persistence, login or multi-user.
- Exports limited to CSV and Excel.

### Known trade-off — fuzzy blocking

Blocking groups records by the first character(s) of the normalized key. Near-duplicates
whose prefix differs (a typo on the first character, or fully swapped word order that
changes the first character) fall into different blocks and are never compared. This is
the deliberate cost that makes 45k-row fuzzy matching feasible.
