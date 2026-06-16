# Plan: Data Cleaner

> **Spec associada:** ./spec.md
> **Data:** 2026-06-16

## 1. Constraints do projeto (herdadas)

- Stack: Python 3.13 + Pandas + rapidfuzz + openpyxl + Streamlit. venv local.
- PT-PT nos comentários (1 linha, sem docstrings multi-linha); UI da app em inglês (clientes Upwork).
- Sem dependências novas além das acima sem aprovação.
- Módulo de motor independente da UI (motor testável sem Streamlit).
- Windows 11, 8GB RAM — atenção a memória com ficheiros grandes.

## 2. Decisões técnicas desta feature

| Decisão | Alternativa rejeitada | Porquê |
|---|---|---|
| Dedup exato + fuzzy (rapidfuzz) configurável | Probabilístico (dedupe/recordlinkage) | Mais rápido, explicável ao cliente; ML é over-engineering p/ v1 |
| Motor = módulo `cleaner/` puro (recebe DataFrame + dict de config, devolve DataFrame + auditoria) | Lógica dentro do app.py | Motor reutilizável e testável sem browser |
| Config como dict passado pela UI | Ficheiro YAML/JSON | É o ponto da app; CLI/YAML fica p/ depois |
| Blocking por prefixo da chave no fuzzy | Comparar todos-com-todos (O(n²)) | 45k registos rebentaria memória/tempo |
| Auditoria = DataFrame de grupos (group_id, mantido, removidos) | Só log de texto | Cliente quer ver o que foi fundido, ficheiro descarregável |

## 3. Impacto no código existente

Projeto novo, sem código existente. Estrutura:

- `cleaner/profile.py` → profile do DataFrame (linhas, colunas, tipos, nulos, dups exatos)
- `cleaner/normalize.py` → normalização configurável (lowercase, trim, email, telefone)
- `cleaner/dedup.py` → dedup exato e fuzzy com blocking; devolve (df_limpo, df_auditoria)
- `cleaner/io.py` → ler CSV/Excel, escrever CSV/Excel
- `app.py` → Streamlit: upload → profile → controlos → preview → download
- `tests/` → pytest por módulo
- `requirements.txt`, `.gitignore`, `README.md`

## 4. Estratégia de validação

| Critério (spec §3) | Método de validação |
|---|---|
| Profile | pytest: DataFrame conhecido → asserts em contagens/nulos/dups |
| Dedup exato | pytest: input com dups conhecidos → nº linhas após bate certo |
| Dedup fuzzy | pytest: "João Silva"/"joao silva" agrupados acima do threshold |
| Normalização | pytest: valores normalizados conforme config |
| Download limpo + auditoria | pytest no motor (auditoria correta) + teste manual na app |
| Erros (coluna ausente, vazio) | pytest: levanta erro claro; teste manual na app |

## 5. Riscos

- Fuzzy em ficheiros grandes pode ser lento → blocking obrigatório + limite/aviso de linhas.
- rapidfuzz scorers: confirmar API na documentação antes de usar (token_sort_ratio vs ratio).
- Streamlit re-executa o script a cada interação → cuidado com recomputar dedup pesado (usar cache).
- Dados de teste: criar fixtures sintéticas pequenas nos testes (não são "dados reais de cliente", são fixtures de teste legítimas).
- Blocking por prefixo pode gerar falsos negativos: duplicados cujo início difere (typo no 1º caráter "Ana"/"Ena", ordem trocada "Joao Silva"/"Silva Joao") caem em blocos distintos e nunca se comparam. Trade-off aceite em v1 (é o que torna 45k viável). Mitigação: usar a chave NORMALIZADA (T4) para derivar o prefixo, recuperando casos de maiúsculas/acentos.
