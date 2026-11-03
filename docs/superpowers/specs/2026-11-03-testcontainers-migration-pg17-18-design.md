# Design Doc: Migração para Testcontainers e Suporte a PostgreSQL 17 e 18

Data: 2026-11-03
Status: Proposto para aprovação

## 1. Intenção e Motivação

O projeto `postgres-mcp` atualmente utiliza o SDK `docker` de forma manual para gerenciar contêineres de teste tanto na suíte geral/unitária (`tests/utils.py`) quanto na suíte de integração multi-banco (`tests/integration/conftest.py`). Essa abordagem manual sofre com:
1. Risco de contêineres órfãos ("leaks") quando testes são interrompidos ou falham abruptamente, consumindo portas e recursos do host.
2. Código imperativo duplicado de polling (`pg_isready`), mapeamento de portas e tratamento de timeouts.
3. Matriz de testes locais restrita a versões antigas (12, 15, 16), enquanto PostgreSQL 17 já é versão estável de mercado e PostgreSQL 18 está disponível.

A intenção é modernizar e unificar a infraestrutura de testes adotando o `testcontainers-python`, garantindo descarte automático de contêineres e estendendo a matriz de testes para cobrir PostgreSQL 12, 15, 16, 17 e 18.

## 2. Objetivos, Não-Objetivos e Anti-Objetivos

### Objetivos
- Adicionar `testcontainers[postgres]` ao grupo de dependências `dev` no `pyproject.toml` e atualizar o `uv.lock`.
- Migrar e unificar o gerenciamento de ciclo de vida de contêineres em `tests/utils.py` e `tests/integration/conftest.py` usando Testcontainers.
- Garantir a ativação automática do Ryuk reaper do Testcontainers para prevenir vazamento de contêineres e volumes em cancelamentos/erros.
- Expandir a fixture multiversão em `tests/conftest.py` para incluir PostgreSQL 17 e 18 (`["postgres:12", "postgres:15", "postgres:16", "postgres:17", "postgres:18"]`).
- Suportar a instalação e execução das extensões `hypopg` e `pg_stat_statements` em todas as versões da matriz (12 a 18).
- Manter 100% de compatibilidade e sucesso em todas as suítes existentes (`unit`, `release`, `integration`).

### Não-Objetivos
- Alterar o código de produto da aplicação em `src/postgres_mcp/`.
- Substituir o banco real por mocks ou emuladores.
- Alterar ferramentas, parâmetros ou schemas expostos pelo servidor MCP.

### Anti-Objetivos
- Não introduzir skips silenciosos quando o Docker estiver disponível.
- Não degradar a performance das suítes de teste com builds repetidos de imagens quando a imagem local já estiver presente em cache.

## 3. Restrições e Premissas

- Ambiente de execução baseado em `uv` (`uv sync --group dev`, `uv run pytest`).
- Imagens customizadas com `hypopg` devem ser resolvidas localmente (usando o `Dockerfile.postgres-hypopg` ou script existente `build_hypopg_image.sh` sob demanda).
- Compatibilidade estrita com Docker daemon local e ambientes de CI (GitHub Actions).

## 4. Abordagens Consideradas

1. **Manter Docker SDK manual e refinar scripts:**
   - Adicionar tratadores manuais de sinal (`atexit`, signal traps) e refinar `tests/utils.py`.
   - *Trade-off:* Requer reinvenção de um mecanismo de reaping que o Testcontainers já resolve de maneira madura; mantém ~200 linhas de código frágil de infraestrutura.
2. **Migração e Unificação com Testcontainers (Escolhida):**
   - Substituir o controle manual em `tests/utils.py` e `tests/integration/conftest.py` por instâncias de `PostgresContainer` / `DockerContainer` do Testcontainers.
   - *Trade-off:* Adiciona dependência de `testcontainers` ao ambiente de dev, mas garante descarte seguro de recursos via Ryuk e simplifica drasticamente a lógica de conexão e prontidão.

## 5. Arquitetura e Decisões de Implementação

- **Dependência:** Inclusão de `testcontainers[postgres]` em `[dependency-groups.dev]` no `pyproject.toml`. O pacote `docker` direto pode ser mantido ou aproveitado transitivamente pelo próprio testcontainers.
- **Unificação de Fixtures:**
  - `tests/utils.py`: Refatorar `create_postgres_container(version: str)` para instanciar a imagem `postgres-hypopg:{version}` através do Testcontainers, aproveitando métodos nativos de espera e resolução de URL/portas.
  - `tests/integration/conftest.py`: Refatorar `_multidb_container` para usar a abstração do Testcontainers com as variáveis de ambiente e configurações pré-carregadas (`shared_preload_libraries=pg_stat_statements`).
- **Suporte a PG 17 e 18:**
  - `tests/conftest.py`: Atualizar parâmetro da fixture para `["postgres:12", "postgres:15", "postgres:16", "postgres:17", "postgres:18"]`.
  - Garantir que o build das imagens `postgres-hypopg:17` e `postgres-hypopg:18` funcione transparentemente usando os pacotes apt `postgresql-17-hypopg` e `postgresql-18-hypopg`.

## 6. O que fica a cargo do Executor (Builder)

- Detalhes de parametrização fina do container (ex: flags de comando para `shared_preload_libraries` e timeout do wait-strategy).
- Implementação exata da fixture `MultiDbPostgres` adaptada ao ciclo de vida do Testcontainers.
- Execução e validação de `uv sync`, `pytest tests/unit`, `pytest tests/integration` e linting.
