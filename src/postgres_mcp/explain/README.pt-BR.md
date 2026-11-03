> [English](README.md) | **Português (Brasil)**

# Ferramentas Explain do PostgreSQL

Este módulo fornece ferramentas para analisar planos de execução de consultas do PostgreSQL.

## Ferramentas

### ExplainPlanTool

Fornece métodos para gerar diferentes tipos de planos EXPLAIN.

## Uso

A ferramenta explain está integrada ao servidor PostgreSQL MCP e pode ser usada pela API MCP por meio da função:

- `explain_query`

Esta função aceita parâmetros para controlar seu comportamento:
- `sql` - A consulta SQL a ser explicada (obrigatório)
- `analyze` - Quando verdadeiro, executa a consulta para obter estatísticas reais (padrão: false)
- `hypothetical_indexes` - Lista opcional de índices a simular sem criá-los

## Benefícios

- **Compreensão de consultas**: ajuda a entender como o PostgreSQL executa as consultas
- **Análise de desempenho**: identifica gargalos e oportunidades de otimização
- **Teste de índices**: testa índices hipotéticos sem realmente criá-los
