> [English](README.md) | **Português (Brasil)**

# Testes do PostgreSQL MCP

Este diretório contém os testes do pacote PostgreSQL MCP.

## Executando os testes

Para executar todos os testes:

```bash
uv run --frozen --group dev pytest
```

Para executar um arquivo de teste específico:

```bash
uv run --frozen --group dev pytest tests/unit/test_obfuscate_password.py
```

Para executar um teste específico:

```bash
uv run --frozen --group dev pytest tests/unit/test_db_conn_pool.py::test_pool_connect_success
```

## Estrutura dos testes

- **Testes unitários** (`tests/unit/`): testes de componentes e funções individuais
  - `test_obfuscate_password.py`: testes da funcionalidade de ofuscação de senha
  - `test_db_conn_pool.py`: testes do pool de conexões com o banco de dados
  - `test_sql_driver.py`: testes do driver SQL e do tratamento de transações
  - `test_database_config.py`, `test_access_mode.py`, `test_transport.py`: configuração multi-database, padrões do modo de acesso e transportes
  - `test_multidb_server.py`: roteamento multi-database, `list_databases`, modo restricted, verificações de extensão por banco e o contrato das ferramentas MCP (nove ferramentas mais `list_databases`, `database` opcional, annotations, padrões legados)

## Ambiente de integração multi-database

`tests/integration/test_multi_database_integration.py` precisa de um daemon do Docker em execução. A fixture de sessão `multidb_postgres` (`tests/integration/conftest.py`) inicia um contêiner PostgreSQL descartável em uma porta aleatória de `127.0.0.1`, com uma senha gerada, e o remove ao final. Ela nunca se conecta a um banco local ou de usuário, e a ausência do daemon do Docker é um erro de teste, não um skip.

- Bancos: `app_development`, `app_testing`, `analytics` (visíveis) e `blocked_db` (`CONNECT` revogado de `PUBLIC` e da role do MCP). Cada banco visível tem sua própria tabela marcadora.
- Role: `mcp_test_role` não é superusuária e não tem `CREATEDB`. DDL, grants e `REVOKE` são executados apenas pela conexão de administrador da fixture, dentro do contêiner.
- Imagem: `postgres-hypopg:16` se existir localmente (construa-a com as execuções de `tests/utils.py`), caso contrário `postgres:16`. Substitua com `MULTIDB_PG_IMAGE`. `pg_stat_statements` existe apenas em `app_development`. Os testes que precisam do `hypopg` são ignorados individualmente quando a imagem não o possui.

```bash
uv run --frozen --group dev pytest -q tests/integration/test_multi_database_integration.py
```

Portanto, a suíte completa (`uv run --frozen --group dev pytest -q`) também precisa do Docker; apenas os testes unitários (`tests/unit`) não precisam.
