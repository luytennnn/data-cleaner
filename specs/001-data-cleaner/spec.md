# Spec: Data Cleaner — motor de limpeza/deduplicação + app Streamlit

> **Estado:** Implementada (2026-06-16)
> **Data:** 2026-06-16
> **Projeto:** data-cleaner

## 1. Objetivo

Ferramenta agnóstica que recebe qualquer CSV ou Excel, faz profile dos dados, normaliza campos, deduplica registos (exato + fuzzy configurável) e devolve um ficheiro limpo mais um ficheiro de auditoria do que foi fundido/removido. Motor Python reutilizável, embrulhado numa app Streamlit, para acelerar gigs de limpeza de dados e servir de peça de portfólio.

## 2. Utilizador e contexto

O Francisco (freelancer), perante um ficheiro de contactos/registos de um cliente, querendo entregar um dataset deduplicado e justificável sem programar do zero a cada gig. Também o visitante do portfólio que experimenta a app online.

## 3. Critérios de aceitação

- [x] Quando carrego um CSV ou .xlsx, então a app mostra um profile: nº linhas, nº colunas, tipos, % nulos por coluna e contagem de duplicados exatos.
- [x] Quando escolho colunas-chave e ativo dedup exato, então o output remove linhas idênticas nessas colunas e o nº de linhas removidas bate certo com o reportado.
- [x] Quando ativo dedup fuzzy com um threshold, então registos semelhantes acima do threshold (ex.: "João Silva" vs "joao silva") são agrupados como duplicados.
- [x] Quando aplico normalização (lowercase/trim/standardizar email e telefone), então os valores no output refletem a normalização escolhida.
- [x] Quando termino, então posso descarregar o ficheiro limpo E um ficheiro de auditoria que lista cada grupo de duplicados e que registo foi mantido.
- [x] Quando o ficheiro não tem a coluna que escolhi ou está vazio/corrompido, então a app mostra erro claro e não rebenta.

## 4. Fora de scope

- Não faz matching probabilístico/ML (dedupe, recordlinkage) — fica para v2.
- Não liga a bases de dados nem APIs; só ficheiros carregados.
- Não persiste dados entre sessões nem tem login/multi-utilizador.
- Não faz transformações arbitrárias de negócio (cálculos, joins entre ficheiros).
- Não exporta para formatos além de CSV e Excel.

## 5. Casos limite (edge cases)

| Cenário | Comportamento esperado |
|---|---|
| Ficheiro vazio ou só com cabeçalho | Erro claro "ficheiro sem dados", sem crash |
| Coluna-chave escolhida não existe | Erro claro a listar colunas disponíveis |
| Valores nulos nas colunas-chave | Nulos tratados como string vazia normalizada; não fundem registos com dados reais |
| Excel com várias sheets | Usa a 1ª sheet por defeito; permite escolher qual |
| Dataset grande (ex.: 45k+ linhas) com fuzzy | Usa blocking (1ª letra/prefixo da chave) para não comparar tudo-com-tudo |
| Telefones com formatos mistos (+351, espaços, traços) | Normalização extrai só dígitos antes de comparar |

## 6. Perguntas em aberto

(vazio — pré-requisito para "Aprovada")
