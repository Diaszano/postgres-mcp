# Testes do PostgreSQL MCP

Este diretório contém a suíte de testes do pacote PostgreSQL MCP.

## Executando os Testes

Para executar todos os testes:

```bash
uv run --frozen --group dev pytest
```

Para executar um arquivo de teste específico:

```bash
uv run --frozen --group dev pytest tests/unit/test_obfuscate_password.py
```

Para executar apenas a suíte unitária:

```bash
uv run --frozen --group dev pytest -q tests/unit
```

## Estrutura de Testes

- **Testes Unitários** (`tests/unit/`): Testes para componentes individuais sem dependência de Docker.
- **Testes de Integração** (`tests/integration/`): Testes com contêiner descartável do PostgreSQL e extensão HypoPG.
- **Testes de Desempenho** (`tests/performance/`): Benchmarks de memória e justiça de pool (opt-in via `--run-performance`).

## Ambiente de Integração Multi-Database e HypoPG

Os testes de integração requerem o Docker daemon em execução. A fixture `multidb_postgres` inicia um contêiner descartável em porta aleatória local com credenciais geradas.

- Imagem: `postgres-hypopg:16` (ou definida via `MULTIDB_PG_IMAGE`). A suíte exige estritamente HypoPG; ausência de Docker ou da extensão resulta em falha explícita, nunca em skip silencioso.
- Bancos: `app_development`, `app_testing`, `analytics` (visíveis) e `blocked_db` (acesso revogado para `PUBLIC` e para o role do MCP).
- Role: `mcp_test_role` sem privilégios de superusuário nem `CREATEDB`.
