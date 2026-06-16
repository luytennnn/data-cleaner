# Tasks: Data Cleaner

> **Spec:** ./spec.md | **Plan:** ./plan.md
> Regra: cada tarefa é implementável e verificável numa sessão curta. TDD: um RED→GREEN por comportamento.

## Convenção de estados

- `[ ]` por fazer
- `[~]` em curso (só uma de cada vez)
- `[x]` feita E validada contra os critérios da spec
- `[!]` bloqueada — anotar porquê

## Tarefas

- [x] **T1 — Setup do projeto**
  - O que faz: venv, requirements.txt (pandas, rapidfuzz, openpyxl, streamlit, pytest), .gitignore, estrutura de pastas `cleaner/` e `tests/`.
  - Valida: `pip install` corre; `import` dos pacotes sem erro.
  - Ficheiros: requirements.txt, .gitignore, cleaner/__init__.py, tests/__init__.py

- [x] **T2 — IO: ler/escrever CSV e Excel**
  - O que faz: `cleaner/io.py` com ler (CSV/.xlsx, escolher sheet) e escrever; erro claro em ficheiro vazio/sem dados.
  - Valida: §3 (carregar CSV/xlsx), §5 (vazio, multi-sheet)
  - Ficheiros: cleaner/io.py, tests/test_io.py

- [x] **T3 — Profile do DataFrame**
  - O que faz: `cleaner/profile.py` → nº linhas, colunas, tipos, % nulos por coluna, contagem de duplicados exatos.
  - Valida: §3 (profile)
  - Ficheiros: cleaner/profile.py, tests/test_profile.py
  - Depende de: T1

- [x] **T4 — Normalização configurável**
  - O que faz: `cleaner/normalize.py` → lowercase, trim, standardizar email (lower/trim) e telefone (só dígitos), por config de colunas.
  - Valida: §3 (normalização), §5 (telefones mistos, nulos)
  - Ficheiros: cleaner/normalize.py, tests/test_normalize.py
  - Depende de: T1

- [x] **T5 — Dedup exato**
  - O que faz: `cleaner/dedup.py::dedup_exact` → remove linhas idênticas nas colunas-chave; devolve (df_limpo, df_auditoria com grupos).
  - Valida: §3 (dedup exato + auditoria), §5 (coluna ausente → erro)
  - Ficheiros: cleaner/dedup.py, tests/test_dedup.py
  - Depende de: T4

- [x] **T6 — Dedup fuzzy com blocking**
  - O que faz: `dedup.py::dedup_fuzzy` → rapidfuzz acima de threshold, blocking por prefixo da chave; estende auditoria.
  - Valida: §3 (dedup fuzzy), §5 (blocking em dataset grande)
  - Ficheiros: cleaner/dedup.py, tests/test_dedup.py
  - Depende de: T5

- [x] **T7 — App Streamlit**
  - O que faz: `app.py` → upload → profile → controlos (colunas-chave, normalizações, exato/fuzzy, threshold) → preview → download limpo + auditoria (CSV/Excel). Erros claros na UI.
  - Valida: §3 (todos, end-to-end na UI), §5 (erros)
  - Ficheiros: app.py
  - Depende de: T6

- [x] **T-final — Validação completa**
  - Correr todos os critérios de aceitação da spec, um a um, com evidência (pytest + teste manual da app).
  - README.md com como correr. Atualizar estado da spec para "Implementada".

## Registo de desvios

| Data | Desvio encontrado | Resolução |
|---|---|---|
| 2026-06-16 | Teste T6 inicial afirmava que "Joao Silva"/"Silva Joao" fundem por fuzzy — contradiz o plan §5 (ordem trocada que muda o prefixo cai em blocos distintos). | Corrigido o TESTE (não o motor): blocking mantém-nos separados (trade-off aceite). Adicionado teste do word-order dentro do mesmo bloco para cobrir a robustez do token_sort_ratio. |
