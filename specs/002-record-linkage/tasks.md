# Tasks: Record Linkage (data-cleaner v2)

> **Spec:** ./spec.md | **Plan:** ./plan.md
> Regra: cada tarefa é implementável e verificável numa sessão curta. TDD: um RED→GREEN por comportamento.

## Convenção de estados

- `[ ]` por fazer
- `[~]` em curso (só uma de cada vez)
- `[x]` feita E validada contra os critérios da spec
- `[!]` bloqueada — anotar porquê

## Tarefas

- [x] **T1 — Setup Splink + confirmação de API**
  - O que faz: adicionar `splink` ao requirements; instalar no venv; confirmar que `import splink`, `DuckDBAPI`, `comparison_library` importam e correm um dedupe trivial. Confirmar a API v4 na doc oficial (narada) e anotar as assinaturas reais a usar.
  - Valida: import sem erro + nota das assinaturas reais (anti-alucinação, plan §5)
  - Ficheiros: requirements.txt, (nota de API no topo de cleaner/linkage.py)
  - FEITO (2026-06-16): splink 4.0.16 + duckdb 1.5.3 + igraph 1.0.0 instalados (wheels, sem build C); dedupe trivial end-to-end OK com pandas 3.0.3/numpy 2.4.6; API v4 confirmada por narada e anotada no topo de cleaner/linkage.py.

- [x] **T2 — Builder de comparisons + blocking**
  - O que faz: função interna que mapeia a config curada (Exact/Name/Email/Phone/Date por coluna) para `comparisons` e blocking rules do Splink. Seed fixa.
  - Valida: pytest — config conhecida → settings válidas do Splink
  - Ficheiros: cleaner/linkage.py, tests/test_linkage.py
  - Depende de: T1
  - FEITO (2026-06-16): `build_settings(comparison_config, blocking_columns, link_type)` em cleaner/linkage.py; `COMPARISON_BUILDERS` mapeia exact/name/email/phone/date → comparison_library do Splink 4; blocking deriva das colunas de comparação se não explícito; `InvalidConfigError` (errors.py) para tipo desconhecido / config vazia; `DEFAULT_SEED=42`. Validação: 7 testes em tests/test_linkage.py via `SettingsCreator.create_settings_dict("duckdb")`; suite 48/48 PASS.

- [x] **T3 — `dedupe_records` (1 ficheiro)**
  - O que faz: recebe df + config (colunas, comparações, threshold, seed) → treina (EM) → prediz → clusteriza → devolve (df_limpo, auditoria com `match_probability`).
  - Valida: §3 (dedupe probabilístico), §3 (threshold monótono), §3 (reprodutibilidade)
  - Ficheiros: cleaner/linkage.py, tests/test_linkage.py
  - Depende de: T2
  - FEITO (2026-06-16): `dedupe_records(df, config)` em linkage.py — id interno `__dc_uid`, treino EM por cada coluna de blocking (seed fixa), predict+cluster ao threshold; auditoria com group_id/method=probabilistic/kept/removed/n_duplicates/match_probability (min do cluster). EM treina com fixture sintética `_make_dupes()` (~50 reg, sinal parcial). Validação: 5 testes (dedupe+pureza, monotonia, reprodutibilidade seed, coluna em falta, config vazia); suite linkage 12/12. Nota: colunas de id no predict seguem `unique_id_column_name` → `__dc_uid_l/_r`.

- [x] **T4 — `link_records` (2 ficheiros)**
  - O que faz: recebe df_a, df_b + colunas a comparar + threshold → devolve pares A↔B acima do threshold com `match_probability`.
  - Valida: §3 (link 2 ficheiros), §5 (0 colunas → erro)
  - Ficheiros: cleaner/linkage.py, tests/test_linkage.py
  - Depende de: T2
  - FEITO (2026-06-16): `link_records(df_a, df_b, config)` link_only com `input_table_aliases=["A","B"]`; pares via source_dataset (robusto à ordem l/r), output ordenado por match_probability. **Correção crítica de `_train`:** pré-filtrar colunas de blocking para só treinar as que têm pares exatos — uma EMTrainingException de coluna sem pares CORROMPE o estado do linker e faz a chamada seguinte crashar (SQL operando vazio). Erro claro se nenhuma coluna treinável (§5). Validação: 4 testes link (pares+pureza, monotonia, config vazia, coluna em falta); suite linkage 16/16.

- [x] **T5 — Auditoria compatível com v1**
  - O que faz: auditoria de saída com schema do v1 (group_id, method="probabilistic", kept, removed) + coluna `match_probability`; casos sem matches → auditoria vazia + flag de aviso.
  - Valida: §3 (download auditoria), §5 (sem matches)
  - Ficheiros: cleaner/linkage.py, tests/test_linkage.py
  - Depende de: T3, T4
  - FEITO (2026-06-16): `PROB_AUDIT_COLUMNS = AUDIT_COLUMNS(v1) + ["match_probability"]` (v1 é prefixo → auditorias juntam-se sem reformatar); `key` adicionada via `_row_key` (valores das colunas comparadas do registo mantido). Sem matches → output=input, auditoria vazia com schema correto. Threshold capado a 0.999 (Splink rebenta SQL com 1.0 exato). Validação: 2 testes (schema=v1+prob, sem-matches); suite linkage 18/18.

- [x] **T6 — App: modos, uploads, config, threshold, run**
  - O que faz: app.py ganha seletor de modo (Clean v1 / Deduplicate-prob / Link); upload(s); config de comparação por coluna; slider de threshold; botão run → motor. Erros claros na UI.
  - Valida: §3 (ambos os modos, end-to-end), §5 (erros)
  - Ficheiros: app.py
  - Depende de: T5
  - FEITO (2026-06-17): `st.radio` de modo no topo (default "Clean (v1)" → testes v1 intactos); `render_clean`/`render_dedupe_prob`/`render_link`; `_comparison_ui` (tipo por coluna), slider threshold 0.50-0.99, `_upload_and_read` (1 ou 2 ficheiros). Erros via DataCleanerError → st.error; sem colunas → st.warning. Validação: AppTest end-to-end dedupe+link + erro (tests/test_app_linkage.py 3/3); smoke v1 4/4.

- [x] **T7 — App: match-weights chart + downloads**
  - O que faz: embeber o waterfall de match weights do Splink; preview do resultado + auditoria; downloads (CSV/Excel). Lidar com caso sem matches (sem chart).
  - Valida: §3 (match weights chart), §3 (downloads)
  - Ficheiros: app.py
  - Depende de: T6
  - FEITO (2026-06-17): `dedupe_records`/`link_records` ganham `with_chart=True` → devolvem 3-tupla com `linker.visualisations.match_weights_chart()` (Altair VConcatChart, confirmado por probe); API 2-tupla intacta para os testes. `_show_probabilistic_result` faz preview + auditoria + `st.altair_chart` + 4 downloads (CSV/Excel). Sem matches → st.warning, sem chart. Validação: motor with_chart (2 testes Altair) + AppTest verifica secção "Match weights".

- [x] **T-final — Validação completa**
  - Correr todos os critérios de aceitação, um a um (pytest + AppTest + teste manual). README atualizado com o modo v2. Mudar o estado da spec para "Implementada" e apagar `specs/.ativa`.
  - FEITO (2026-06-17): suite **64/64 PASS** (45.34s). Mapa critérios §3→testes: (1) dedupe modo→test_app_dedupe_prob_end_to_end+test_dedupe_groups_probable_duplicates; (2) link modo→test_app_link_end_to_end+test_link_finds_known_pairs; (3) match-weights chart→test_dedupe/link_with_chart_returns_altair+AppTest "Match weights"; (4) threshold monótono→test_dedupe/link_threshold_monotonic; (5) downloads→AppTest+_to_bytes; (6) reprodutibilidade seed→test_dedupe_reproducible_with_seed; (7) erros→missing_column/empty_comparisons/no_matches/no_columns_warns. README+requirements (versões pinadas) atualizados. py_compile OK. Boot do servidor Streamlit bloqueado pelo sandbox (EPERM uv_spawn) — coberto pelos AppTests in-process (app.py real via ScriptRunner). Estado spec→Implementada; gate `.ativa` apagado.

## Registo de desvios

| Data | Desvio encontrado | Resolução |
|---|---|---|
