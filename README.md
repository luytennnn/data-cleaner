# 🧹 Data Cleaner

Profile, normalize, deduplicate and **link** any CSV or Excel file — a reusable Python
engine wrapped in a Streamlit app. Built to speed up data-cleaning gigs and deliver a
deduplicated, **auditable** dataset to clients.

Three modes, chosen at the top of the app:

- **Clean (v1)** — profile, normalize and exact/fuzzy dedup.
- **Deduplicate (probabilistic)** — multi-field probabilistic matching within one file.
- **Link two files** — match corresponding records across two files (e.g. old CRM × new export).

## Features

- **Profile** — rows, columns, dtypes, % nulls per column, exact-duplicate count.
- **Normalize** — per-column `trim`, `lowercase`, `email` (trim + lowercase),
  `phone` (digits only). Nulls become normalized empty strings.
- **Deduplicate (v1)**
  - *Exact* — drop identical rows on the chosen key columns.
  - *Fuzzy* — `rapidfuzz` token-sort similarity above a threshold, with **blocking**
    by key prefix so large files (45k+ rows) don't compare everything-with-everything.
- **Record linkage (v2)** — probabilistic matching with [Splink 4](https://moj-analytical-services.github.io/splink/)
  (DuckDB backend). Pick a comparison type per column (`exact`, `name`, `email`,
  `phone`, `date`); the unsupervised Fellegi-Sunter / EM model scores each pair with a
  `match_probability`, and a **match-weights waterfall chart** shows how much each field
  contributed. Two modes: *deduplicate* one file or *link* two files. Fixed seed →
  reproducible results.
- **Audit trail** — a downloadable table of every duplicate group / matched pair: which
  record was kept, which were removed, and the `match_probability`.
- **Download** cleaned data / matched pairs and audit as CSV or Excel.

## Project structure

```
cleaner/        # Engine — independent of the UI, fully unit-tested
  io.py         # read/write CSV & Excel, sheet selection, clear errors
  profile.py    # DataFrame profile
  normalize.py  # configurable normalization
  dedup.py      # exact + fuzzy dedup with blocking, shared audit schema
  linkage.py    # v2: probabilistic dedupe/link over Splink 4 (DuckDB), match-weights chart
  errors.py     # clear, UI-friendly exceptions
app.py          # Streamlit UI: mode selector → upload(s) → config → preview → chart → download
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

### Probabilistic record linkage (v2)

```python
import pandas as pd
from cleaner.linkage import dedupe_records, link_records

config = {"comparisons": {"name": "name", "email": "email"}, "threshold": 0.9, "seed": 42}

# Deduplicate one file
clean, audit = dedupe_records(pd.read_csv("contacts.csv"), config)

# Link two files (pairs above the threshold, with match_probability)
pairs, audit = link_records(pd.read_csv("crm_old.csv"), pd.read_csv("export_new.csv"), config)
```

The audit schema extends the v1 schema with a `match_probability` column, so v1 and v2
audits concatenate without reformatting.

## Out of scope

- Linking more than two files at once; backends other than DuckDB (Spark, Athena…).
- No database or API connections — uploaded files only.
- No persistence of the trained model, login or multi-user.
- Supervised ML with hand labels (v2 uses unsupervised EM — no manual labelling).
- Exports limited to CSV and Excel.

### Known trade-off — fuzzy blocking

Blocking groups records by the first character(s) of the normalized key. Near-duplicates
whose prefix differs (a typo on the first character, or fully swapped word order that
changes the first character) fall into different blocks and are never compared. This is
the deliberate cost that makes 45k-row fuzzy matching feasible.
