# Spec: Record Linkage — matching probabilístico (data-cleaner v2)

> **Estado:** Implementada (2026-06-17)
> **Data:** 2026-06-16
> **Projeto:** data-cleaner

## 1. Objetivo

Adicionar matching probabilístico multi-campo ao data-cleaner, além do fuzzy determinístico do v1. Dois modos: **deduplicar** registos prováveis dentro de um ficheiro, e **ligar** registos correspondentes entre dois ficheiros — com pesos por campo explicáveis ao cliente.

## 2. Utilizador e contexto

O Francisco (freelancer) que precisa de fundir registos onde uma só chave fuzzy não chega (ex.: mesmo cliente com nome, email e telefone todos ligeiramente diferentes), ou de cruzar duas listas (ex.: CRM antigo × export novo). Também o visitante do portfólio que vê a app justificar cada match com pesos.

## 3. Critérios de aceitação

- [ ] Quando escolho o modo **Deduplicate**, carrego 1 ficheiro, seleciono colunas + tipo de comparação por coluna e um threshold, então o output agrupa/remove os duplicados prováveis e a auditoria lista cada grupo com a `match_probability`.
- [ ] Quando escolho o modo **Link**, carrego 2 ficheiros e indico as colunas a comparar, então o output lista os pares A↔B acima do threshold com a `match_probability`.
- [ ] Quando o modelo está treinado, então a app mostra o gráfico de **match weights** (waterfall do Splink) com a contribuição de cada campo.
- [ ] Quando ajusto o threshold de match-probability, então o nº de matches muda de forma monótona (threshold mais alto → menos ou iguais matches).
- [ ] Quando termino, então descarrego o output E a auditoria (CSV/Excel) com a `match_probability` por par/grupo.
- [ ] Quando a corrida é repetida com a mesma input e a mesma seed, então os matches são idênticos (reprodutível).
- [ ] Quando o ficheiro está vazio, falta uma coluna escolhida, ou não há pares acima do threshold, então a app mostra mensagem clara e não rebenta.

## 4. Fora de scope

- Ligar mais de 2 ficheiros em simultâneo.
- Backends além do DuckDB (Spark, Athena, Postgres).
- Persistir o modelo treinado entre sessões.
- Matching incremental/streaming.
- ML supervisionado com labels manuais (usa-se EM não-supervisionado — sem labeling humano).
- Substituir o fuzzy/exato do v1 — o v2 acrescenta um modo, não remove os existentes.

## 5. Casos limite (edge cases)

| Cenário | Comportamento esperado |
|---|---|
| Sem pares acima do threshold | Output = input; auditoria vazia; aviso "no matches above threshold" |
| Modo Link com 0 colunas a comparar | Erro claro a pedir pelo menos uma coluna |
| Dataset grande (>100k linhas) | Aviso de que o EM pode demorar; corre na mesma (DuckDB) |
| Colunas com muitos nulos | Nulos contam como não-comparáveis; não inflacionam o match |
| EM não converge / dados insuficientes | Captura o erro do Splink e mostra mensagem clara |
| Ficheiro vazio ou só cabeçalho | Erro claro "ficheiro sem dados", sem crash (reusa io.py do v1) |

## 6. Perguntas em aberto

(vazio — pré-requisito para "Aprovada")
