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
- `test_mcp_result_wire.py`: também verifica descoberta das ferramentas, SELECT e rejeição de escrita restrita por uma sessão cliente MCP.
- **Testes de Desempenho** (`tests/performance/`): Benchmarks de memória e justiça de pool (opt-in via `--run-performance`).

## Ambiente de Integração Multi-Database, Multi-Versão e HypoPG

O harness de testes utiliza `testcontainers-python` para gerenciar as instâncias PostgreSQL com descarte e liberação automática de recursos (via Ryuk reaper).
A matriz multiversão de testes cobre as versões `12`, `15`, `16`, `17` e `18` do PostgreSQL.

Os testes de integração requerem o Docker daemon em execução. A fixture `multidb_postgres` inicia um contêiner descartável do PostgreSQL via Testcontainers em porta aleatória local com credenciais geradas.

- Imagem: `postgres-hypopg:16` (ou definida via `MULTIDB_PG_IMAGE`, com suporte a 16, 17 e 18). A suíte exige estritamente HypoPG; ausência de Docker ou da extensão resulta em falha explícita, nunca em skip silencioso.
- Bancos: `app_development`, `app_testing`, `analytics` (visíveis) e `blocked_db` (acesso revogado para `PUBLIC` e para o role do MCP).
- Role: `mcp_test_role` sem privilégios de superusuário nem `CREATEDB`.

Para validar o contrato MCP com o PostgreSQL descartável:

```bash
uv run --frozen --group dev pytest -q tests/integration/test_mcp_result_wire.py
```
