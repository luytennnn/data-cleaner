# Plan: Record Linkage (data-cleaner v2)

> **Spec associada:** ./spec.md
> **Data:** 2026-06-16

## 1. Constraints do projeto (herdadas)

- Stack: Python 3.13 + Pandas 3 + numpy 2 + **Splink 4 (DuckDB)** + Streamlit. venv local.
- Dependência nova aprovada: `splink` (traz `duckdb`, `igraph`). Sem outras sem aprovação.
- PT-PT nos comentários (1 linha, sem docstrings multi-linha); UI da app em inglês.
- Motor (`cleaner/`) independente da UI — testável sem Streamlit.
- v1 (io/profile/normalize/dedup) fica INTACTO; o v2 acrescenta `cleaner/linkage.py`.
- Windows 11, 8GB RAM — DuckDB é leve, mas controlar `max_pairs` do EM.

## 2. Decisões técnicas desta feature

| Decisão | Alternativa rejeitada | Porquê |
|---|---|---|
| Splink 4 + DuckDB | recordlinkage | recordlinkage exige `pandas<3` (temos 3.0.3) e parou em 2023 |
| Splink 4 + DuckDB | dedupe | dedupe precisa de labeling interativo (mau em app stateless) + build C no Windows |
| EM não-supervisionado | Classificador supervisionado | Sem labels manuais; pesos Fellegi-Sunter explicáveis ao cliente |
| Seed fixa no EM/random sampling | Default aleatório | Resultados e testes reprodutíveis (critério §3) |
| `cleaner/linkage.py` espelha a interface do `dedup.py` | Lógica no app.py | Motor reutilizável e testável sem browser |
| App constrói `comparisons` + blocking a partir de config curada | Expor settings cruas do Splink | UX para não-especialistas; esconde internos do Splink |
| Auditoria com schema compatível com v1 + `match_probability` | Schema novo | Reusa o padrão de auditoria descarregável do v1 |

## 3. Impacto no código existente

- `cleaner/linkage.py` (NOVO) → `dedupe_records(df, config)` e `link_records(df_a, df_b, config)`; devolvem (resultado, auditoria).
- `cleaner/linkage.py` → builder interno: config curada (Exact/Name/Email/Phone/Date) → `comparisons` + blocking rules do Splink.
- `tests/test_linkage.py` (NOVO) → pytest por comportamento.
- `app.py` → seletor de modo (Clean v1 / Deduplicate-prob / Link); uploads (1 ou 2); config de comparação; threshold; match-weights chart; downloads.
- `requirements.txt` → `+ splink`.
- v1: `io.py`, `profile.py`, `normalize.py`, `dedup.py`, `errors.py` NÃO mudam (exceto talvez novas exceções em `errors.py`).

## 4. Estratégia de validação

| Critério (spec §3) | Método de validação |
|---|---|
| Dedupe probabilístico | pytest: fixture com duplicados prováveis → grupos esperados acima do threshold |
| Link 2 ficheiros | pytest: A/B com correspondências conhecidas → pares esperados |
| Match weights chart | AppTest: chart presente após run; teste manual visual |
| Threshold monótono | pytest: nº matches a threshold alto ≤ nº a threshold baixo |
| Download output + auditoria | pytest no motor + AppTest na app |
| Reprodutibilidade (seed) | pytest: duas corridas com a mesma seed → resultado idêntico |
| Erros (vazio, coluna, sem matches) | pytest: erro/aviso claro; AppTest na UI |

## 5. Riscos

- **API Splink 4 mudou muito face ao v3** → confirmar na documentação oficial (agente `narada`) ANTES de escrever lógica; não assumir assinaturas de v3.
- **Instalação no Windows** (duckdb, igraph wheels) → a T1 confirma `import splink` + `DuckDBAPI` no venv antes de tudo; se falhar, revisitar a spec.
- **Compat runtime com pandas 3 / numpy 2** → metadata permite, mas confirmar em execução na T1.
- **EM não-determinístico** sem seed → fixar seed em `estimate_u_using_random_sampling` e no EM.
- **8GB RAM** → limitar `max_pairs` do estimate_u; aviso acima de ~100k linhas.
- **Embeber charts Altair do Splink no Streamlit** → confirmar o objeto retornado (`st.altair_chart` vs spec JSON) na T7.
- **Fixtures de teste**: sintéticas pequenas (legítimas, não dados de cliente); EM com poucos dados pode ser instável → fixtures com sinal claro de duplicação.
