> [English](README.md) | **Português (Brasil)**

<div align="center">

<img src="assets/postgres-mcp-pro.png" alt="Postgres MCP Pro Logo" width="600"/>

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PyPI - Version](https://img.shields.io/pypi/v/postgres-mcp)](https://pypi.org/project/postgres-mcp/)
[![Discord](https://img.shields.io/discord/1336769798603931789?label=Discord)](https://discord.gg/4BEHC7ZM)
[![Twitter Follow](https://img.shields.io/twitter/follow/auto_dba?style=flat)](https://x.com/auto_dba)
[![Contributors](https://img.shields.io/github/contributors/crystaldba/postgres-mcp)](https://github.com/crystaldba/postgres-mcp/graphs/contributors)

<h3>Um servidor MCP para Postgres com ajuste de índices, planos de execução, verificações de saúde e execução segura de SQL.</h3>

<div class="toc">
  <a href="#overview">Visão geral</a> •
  <a href="#demo">Demonstração</a> •
  <a href="#quick-start">Início rápido</a> •
  <a href="#technical-notes">Notas técnicas</a> •
  <a href="#mcp-server-api">API MCP</a> •
  <a href="#related-projects">Projetos relacionados</a> •
  <a href="#frequently-asked-questions">FAQ</a>
</div>

</div>

<a id="overview"></a>
## Visão geral

**Postgres MCP Pro** é um servidor open source de Model Context Protocol (MCP) criado para apoiar você e seus agentes de IA durante **todo o processo de desenvolvimento**, desde a codificação inicial, passando por testes e implantação, até o ajuste e a manutenção em produção.

O Postgres MCP Pro faz muito mais do que encapsular uma conexão com o banco de dados.

Os recursos incluem:

- **🔍 Saúde do banco de dados** - analise a saúde dos índices, a utilização de conexões, o cache de buffers, a saúde do vacuum, os limites de sequências, o atraso de replicação e muito mais.
- **⚡ Ajuste de índices** - explore milhares de índices possíveis para encontrar a melhor solução para a sua carga de trabalho, usando algoritmos de nível industrial.
- **📈 Planos de consulta** - valide e otimize o desempenho revisando planos EXPLAIN e simulando o impacto de índices hipotéticos.
- **🧠 Inteligência de esquema** - geração de SQL sensível ao contexto, baseada em um entendimento detalhado do esquema do banco de dados.
- **🛡️ Execução segura de SQL** - controle de acesso configurável, incluindo suporte ao modo somente leitura e à análise segura de SQL, o que o torna utilizável tanto em desenvolvimento quanto em produção.

O Postgres MCP Pro oferece suporte aos transportes [Standard Input/Output (stdio)](https://modelcontextprotocol.io/docs/concepts/transports#standard-input%2Foutput-stdio) e [Server-Sent Events (SSE)](https://modelcontextprotocol.io/docs/concepts/transports#server-sent-events-sse), para dar flexibilidade em diferentes ambientes.

Para mais contexto sobre por que criamos o Postgres MCP Pro, veja [nossa publicação de lançamento](https://www.crystaldba.ai/blog/post/announcing-postgres-mcp-server-pro).

<a id="demo"></a>
## Demonstração

*De inutilizável a extremamente rápido*
- **Desafio:** Geramos um aplicativo de filmes com um assistente de IA, mas o código do ORM SQLAlchemy rodava de forma dolorosamente lenta.
- **Solução:** Usando o Postgres MCP Pro com o Cursor, corrigimos os problemas de desempenho em minutos.

O que fizemos:
- 🚀 Corrigimos o desempenho - incluindo consultas do ORM, indexação e cache
- 🛠️ Corrigimos uma página quebrada - pedindo ao agente que explorasse os dados, corrigisse consultas e adicionasse conteúdo relacionado.
- 🧠 Melhoramos os filmes mais bem avaliados - explorando os dados e corrigindo a consulta do ORM para exibir resultados mais relevantes.

Veja o vídeo abaixo ou leia o [passo a passo](examples/movie-app.md).

https://github.com/user-attachments/assets/24e05745-65e9-4998-b877-a368f1eadc13




<a id="quick-start"></a>
## Início rápido

### Pré-requisitos

Antes de começar, certifique-se de ter:
1. Credenciais de acesso ao seu banco de dados.
2. Docker *ou* Python 3.12 ou superior.

#### Credenciais de acesso
 Você pode confirmar que suas credenciais de acesso são válidas usando `psql` ou uma ferramenta gráfica como o [pgAdmin](https://www.pgadmin.org/).


#### Docker ou Python

A escolha entre Docker e Python é sua.
Em geral recomendamos o Docker, porque usuários de Python podem encontrar mais problemas específicos de ambiente.
No entanto, muitas vezes faz sentido usar o método com o qual você está mais familiarizado.


### Instalação

Escolha um dos métodos a seguir para instalar o Postgres MCP Pro:

#### Opção 1: usando Docker

Baixe a imagem Docker do servidor MCP Postgres MCP Pro via GitHub Container Registry:
Essa imagem contém todas as dependências necessárias, oferecendo uma forma confiável de executar o Postgres MCP Pro em diversos ambientes.

```bash
docker pull ghcr.io/diaszano/postgres-mcp:latest
```


#### Opção 2: usando Python

Se você tem o `pipx` instalado, pode instalar o Postgres MCP Pro com:

```bash
pipx install postgres-mcp
```

Caso contrário, instale o Postgres MCP Pro com `uv`:

```bash
uv pip install postgres-mcp
```

Se precisar instalar o `uv`, consulte as [instruções de instalação do uv](https://docs.astral.sh/uv/getting-started/installation/).


### Configure seu assistente de IA

Fornecemos instruções completas para configurar o Postgres MCP Pro com o Claude Desktop.
Muitos clientes MCP têm arquivos de configuração semelhantes; você pode adaptar estes passos para o cliente da sua escolha.

#### Configuração do Claude Desktop

Você precisará editar o arquivo de configuração do Claude Desktop para adicionar o Postgres MCP Pro.
A localização desse arquivo depende do seu sistema operacional:
- MacOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

Você também pode usar o item de menu `Settings` no Claude Desktop para localizar o arquivo de configuração.

Agora você vai editar a seção `mcpServers` do arquivo de configuração.

##### Se você está usando Docker

```json
{
  "mcpServers": {
    "postgres": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "DATABASE_URI",
        "-e",
        "DATABASE_DOCKER_REMAP_LOCALHOST",
        "ghcr.io/diaszano/postgres-mcp:latest",
        "--access-mode=unrestricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://username:password@localhost:5432/dbname",
        "DATABASE_DOCKER_REMAP_LOCALHOST": "true"
      }
    }
  }
}
```

O remapeamento do host Docker fica desativado por padrão. Defina `DATABASE_DOCKER_REMAP_LOCALHOST=true` no ambiente do contêiner para remapear o host `localhost` do banco. O entrypoint usa `host.docker.internal` no MacOS/Windows ou `172.17.0.1` no Linux quando estiver acessível.

##### Se você está usando `uvx`

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uvx",
      "args": [
        "postgres-mcp",
        "--access-mode=unrestricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://username:password@localhost:5432/dbname"
      }
    }
  }
}
```


##### Se você está usando `pipx`

```json
{
  "mcpServers": {
    "postgres": {
      "command": "postgres-mcp",
      "args": [
        "--access-mode=unrestricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://username:password@localhost:5432/dbname"
      }
    }
  }
}
```


##### Se você está usando `uv`

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": [
        "run",
        "postgres-mcp",
        "--access-mode=unrestricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://username:password@localhost:5432/dbname"
      }
    }
  }
}
```


##### URI de conexão

Substitua `postgresql://...` pela [URI de conexão do seu banco de dados Postgres](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING-URIS).


##### Modo de acesso

O Postgres MCP Pro oferece suporte a vários *modos de acesso* para dar a você controle sobre as operações que o agente de IA pode executar no banco de dados:
- **Modo Unrestricted**: permite acesso total de leitura e escrita para modificar dados e esquema quando os limites de consulta estão desabilitados. É adequado para ambientes de desenvolvimento.
- **Modo Restricted**: limita as operações a transações somente leitura, valida o SQL e limita o tempo de execução. Com os limites de consulta desabilitados, `execute_sql` aceita `SELECT`, `EXPLAIN` (sem `ANALYZE`) e `SHOW`; `ANALYZE` independente e `VACUUM` são rejeitados. Habilitar os limites de consulta restringe ainda mais `execute_sql` a uma única consulta segura, somente leitura e que retorna linhas, em ambos os modos de acesso; consulte a nota de migração abaixo.

Para usar o modo restricted, substitua `--access-mode=unrestricted` por `--access-mode=restricted` nos exemplos de configuração acima.


#### Outros clientes MCP

Muitos clientes MCP têm arquivos de configuração semelhantes aos do Claude Desktop, e você pode adaptar os exemplos acima para o cliente da sua escolha.

- Se você usa o Cursor, pode navegar da `Command Palette` até `Cursor Settings` e abrir a aba `MCP` para acessar o arquivo de configuração.
- Se você usa o Windsurf, pode navegar da `Command Palette` até `Open Windsurf Settings Page` para acessar o arquivo de configuração.
- Se você usa o Goose, execute `goose configure` e selecione `Add Extension`.
- Se você usa o Qodo Gen, abra o painel Chat, clique em `Connect more tools`, clique em `+ Add new MCP` e adicione a nova configuração.

## Transporte SSE

O Postgres MCP Pro oferece suporte ao [transporte SSE](https://modelcontextprotocol.io/docs/concepts/transports#server-sent-events-sse), que permite que vários clientes MCP compartilhem um único servidor, possivelmente remoto.
Para usar o transporte SSE, você precisa iniciar o servidor com a opção `--transport=sse`.

Para um cliente local, execute o servidor na mesma máquina:

```bash
DATABASE_URI='postgresql://username:password@localhost:5432/dbname' \
  uvx postgres-mcp --access-mode=restricted --transport=sse
```

Em seguida, atualize a configuração do seu cliente MCP para chamar o servidor MCP.
Por exemplo, no `mcp.json` do Cursor ou no `cline_mcp_settings.json` do Cline você pode colocar:

```json
{
    "mcpServers": {
        "postgres": {
            "type": "sse",
            "url": "http://localhost:8000/sse"
        }
    }
}
```

Para o Windsurf, o formato em `mcp_config.json` é um pouco diferente:

```json
{
    "mcpServers": {
        "postgres": {
            "type": "sse",
            "serverUrl": "http://localhost:8000/sse"
        }
    }
}
```

## Implantação HTTP autenticada

**Migração:** SSE e Streamable HTTP continuam usando `localhost` por padrão. Endereços fora de loopback, incluindo `0.0.0.0`, `::`, IPs privados e nomes diferentes de `localhost`, agora são rejeitados antes das conexões ao banco e da inicialização HTTP, a menos que as três variáveis abaixo sejam válidas. Stdio ignora a configuração HTTP e não exige credenciais HTTP. `DATABASE_URI`, modos de acesso e parâmetros das ferramentas permanecem iguais.

| Variável | Valor obrigatório para HTTP autenticado |
| --- | --- |
| `MCP_HTTP_AUTH_TOKEN` | Um segredo bearer aleatório com pelo menos 32 caracteres ASCII imprimíveis, sem espaços. Não o coloque nos argumentos do comando nem no controle de versão. |
| `MCP_HTTP_ALLOWED_HOSTS` | Cabeçalhos Host exatos separados por vírgula, incluindo portas quando enviadas pelo cliente, como `mcp.example.com` ou `mcp.example.com:8443`. Curingas e URLs são rejeitados. |
| `MCP_HTTP_ALLOWED_ORIGINS` | Origens HTTPS exatas separadas por vírgula, como `https://client.example.com`. Caminhos, credenciais e curingas são rejeitados. |

Configure o segredo no armazenamento de segredos ou no ambiente do serviço e execute atrás de um proxy HTTPS com terminação TLS:

```bash
export MCP_HTTP_ALLOWED_HOSTS='mcp.example.com'
export MCP_HTTP_ALLOWED_ORIGINS='https://client.example.com'
# MCP_HTTP_AUTH_TOKEN e DATABASE_URI são fornecidos com segurança pelo ambiente do serviço.
uvx postgres-mcp --access-mode=restricted --transport=streamable-http
```

Use `/mcp` para Streamable HTTP ou `--transport=sse` com `/sse` e `/messages/` para SSE. Os clientes devem enviar `Authorization: Bearer <segredo>` em todas as requisições HTTP, inclusive nos POSTs de mensagens SSE. Requisições anônimas ou com token inválido recebem 401. Requisições autenticadas com Host não permitido recebem 421; com Origin não permitido, recebem 403. Clientes nativos podem omitir Origin. O SDK MCP disponibiliza a identidade estável `configured-http-client`; todos os portadores do segredo compartilham o mesmo acesso ao banco. Trata-se de uma credencial bearer previamente provisionada, sem login OAuth nem serviço de autorização por usuário. Para rotacioná-la, altere o segredo e reinicie o processo.

O proxy deve preservar Authorization, o Host público e qualquer cabeçalho Origin. Termine TLS no proxy, exponha apenas a porta HTTPS, limite conexões e requisições (incluindo streams SSE simultâneos) e impeça acesso direto ao backend com loopback ou regras de firewall. Não registre Authorization, segredos ou dados do banco nos logs do proxy. Uma declaração de ingresso confiável não habilita endereços públicos nem desativa a verificação bearer. Para um endereço privado de container/backend, use `--streamable-http-host=0.0.0.0` ou `--sse-host=0.0.0.0` **com as mesmas variáveis de autenticação** e restrinja o acesso de rede ao ingresso. Publicar a porta do container não expõe um processo vinculado ao loopback do próprio container.

O caminho de autenticação, identidade e Host/Origin é exercitado com o SDK MCP 1.25.0 nos testes focados de transporte. Terminação TLS, isolamento do proxy e limites de tráfego são responsabilidades da implantação; este repositório não instala nem verifica uma implantação de proxy.

<a id="multiple-databases-optional"></a>
## Múltiplos bancos de dados (opcional)

Por padrão, o Postgres MCP Pro conversa com o único banco de dados indicado em `DATABASE_URI`, exatamente como antes.
Defina `DATABASE_AUTO_DISCOVER=true` para permitir que o agente descubra e escolha entre os bancos de dados da mesma instância PostgreSQL.
Toda ferramenta aceita um argumento opcional `database`; quando ele é omitido, o banco de dados padrão é usado, nunca o utilizado por uma chamada anterior.

### Modo legado (padrão)

```bash
DATABASE_URI='postgresql://user:password@localhost:5432/app_development' uvx postgres-mcp
```

- Um pool de conexões, para o banco de dados da URI (uma URI passada como argumento de linha de comando continua funcionando).
- O modo de acesso padrão continua sendo `unrestricted`.
- `database` só é aceito quando é igual ao banco de dados da URI; qualquer outro nome é rejeitado com um erro (sem descoberta, sem fallback).
- `list_databases` retorna apenas esse banco de dados. Se a URI não tiver nome de banco de dados, `name` é `null`.
- `DATABASE_ALLOWED_DATABASES`, `DATABASE_EXCLUDED_DATABASES` e as configurações de descoberta/pool abaixo não têm efeito. Os limites de consulta se aplicam tanto no modo legado quanto no modo de descoberta.

### Modo de descoberta

```bash
DATABASE_URI='postgresql://dev:password@localhost:5432/postgres'
DATABASE_AUTO_DISCOVER=true
DATABASE_DEFAULT_DATABASE=app_development
DATABASE_ALLOWED_DATABASES=app_development,app_testing,analytics
DATABASE_EXCLUDED_DATABASES=postgres

uvx postgres-mcp
```

| Variável | Padrão | Significado |
|----------|--------|-------------|
| `DATABASE_URI` | obrigatória | URI de bootstrap. É usada para consultar `pg_database`, e seu host, porta, usuário, senha, TLS e demais opções são reutilizados para todos os bancos de dados; só o `dbname` muda. |
| `DATABASE_AUTO_DISCOVER` | `false` | `true`/`false`, `1`/`0` ou `yes`/`no`. Habilita a descoberta e o argumento `database`. |
| `DATABASE_DEFAULT_DATABASE` | `dbname` de `DATABASE_URI` | Banco de dados usado quando `database` é omitido. Obrigatória se a URI não tiver `dbname`. |
| `DATABASE_ALLOWED_DATABASES` | vazia (todos os elegíveis) | Lista de permissão com nomes exatos, sensíveis a maiúsculas e minúsculas. |
| `DATABASE_EXCLUDED_DATABASES` | vazia | Lista de bloqueio com nomes exatos. Ela prevalece sobre a lista de permissão. |
| `DATABASE_DISCOVERY_TTL_SECONDS` | `60` | Por quanto tempo a lista descoberta fica em cache. |
| `DATABASE_MAX_POOLS` | `4` | Número máximo de pools de bancos de dados abertos ao mesmo tempo. |
| `DATABASE_POOL_MAX_SIZE` | `2` | Número máximo de conexões por pool de banco de dados. |
| `DATABASE_POOL_IDLE_SECONDS` | `600` | Tempo ocioso após o qual um pool sem uso pode ser fechado. |
| `DATABASE_QUERY_GUARDRAILS_ENABLED` | `false` | Habilita limites de consulta e restringe `execute_sql` a uma única consulta segura, somente leitura e que retorna linhas, em ambos os modos de acesso. Consulte a orientação de migração abaixo. Transportes remotos exibem um aviso na inicialização enquanto estiver desabilitado. |
| `DATABASE_QUERY_DEFAULT_MAX_ROWS` | `200` | Número padrão máximo de linhas retornadas por uma consulta. |
| `DATABASE_QUERY_HARD_MAX_ROWS` | `5000` | Limite máximo de linhas que uma chamada da ferramenta pode solicitar. |
| `DATABASE_QUERY_DEFAULT_TIMEOUT_SECONDS` | `15` | Tempo limite padrão da consulta, em segundos. |
| `DATABASE_QUERY_HARD_TIMEOUT_SECONDS` | `60` | Tempo limite máximo que uma chamada da ferramenta pode solicitar. |
| `DATABASE_QUERY_MAX_RESULT_BYTES` | `2097152` | Tamanho máximo do JSON UTF-8 de `CallToolResult` do MCP, incluindo texto escapado, saída estruturada e metadados; exclui o envelope JSON-RPC e o enquadramento do transporte. Valor máximo configurável de 64 MiB. |
| `DATABASE_QUERY_MAX_CONCURRENCY` | `4` | Número máximo de execuções SQL simultâneas com limites; valor máximo configurável de 256. |
| `DATABASE_PAGINATION_ENABLED` | `true` | Permite paginação de consultas quando solicitada explicitamente. |
| `DATABASE_PAGINATION_DEFAULT_PAGE_SIZE` | `100` | Quantidade padrão de linhas por página; não pode exceder o tamanho máximo de página. |
| `DATABASE_PAGINATION_MAX_PAGE_SIZE` | `1000` | Tamanho máximo solicitado por página. As páginas também respeitam o saldo do limite total de linhas e o limite de bytes da resposta. |
| `DATABASE_PAGINATION_CURSOR_TTL_SECONDS` | `300` | Validade do cursor em segundos após cada página concluída. |
| `DATABASE_PAGINATION_MAX_ACTIVE_CURSORS` | `100` | Quantidade máxima de cursores armazenados; novas consultas podem remover o cursor não reservado mais antigo. |

Ambas as variáveis de lista aceitam uma lista separada por vírgulas (`app,testing`; espaços ao redor dos nomes são removidos) ou, quando o valor começa com `[`, um array JSON de strings (`["app", "name,with,comma"]`).
Use a forma JSON para nomes que contenham vírgulas. Os nomes nunca são convertidos para minúsculas nem normalizados de outra forma.
As variáveis numéricas devem ser inteiros maiores ou iguais a 1; valores inválidos interrompem o servidor na inicialização com um erro que nunca inclui a URI nem a senha. As configurações de limites de consulta também exigem inteiros positivos; os valores padrão de linhas e tempo limite não podem exceder seus limites máximos. O limite de linhas é 10.000.000 e o de tempo limite é 3.600 segundos. Os limites ficam desabilitados por padrão durante a migração.

**Migração de `execute_sql` para os limites de consulta.** Antes de definir `DATABASE_QUERY_GUARDRAILS_ENABLED=true`, migre os chamadores: o modo habilitado aceita apenas uma consulta segura, somente leitura e que retorna linhas, inclusive com `--access-mode=unrestricted`. Escritas/DDL, múltiplas instruções, `SHOW`, `EXPLAIN`, `SELECT INTO`, CTEs que modificam dados e cláusulas de bloqueio de linhas são rejeitados. Separe lotes somente leitura em chamadas individuais, use `explain_query` para planos e mova escritas ou outras instruções incompatíveis para um cliente de banco de dados separado e autorizado antes de habilitar a opção. Com a opção desabilitada e sem argumentos de limite, `execute_sql` mantém o comportamento de instruções e o formato de resultado legados. A paginação explícita usa os mesmos limites de linhas, tempo, bytes e concorrência mesmo quando a opção de limites está desabilitada.

**Paginação de consultas.** Chamadas existentes de `execute_sql(sql, database)` mantêm `pagination="none"`. Informar `page_size` sem um modo explícito gera erro. Para paginar:

```python
execute_sql("SELECT id, name FROM users ORDER BY id", "app", max_rows=250, page_size=100, pagination="keyset")
fetch_query_page(cursor="<next_cursor da resposta anterior>", page_size=100)
```

Os modos `offset` e `keyset` aceitam um SELECT conservador sobre uma única tabela, com uma coluna de ordenação ascendente incluída na projeção e verificada como única e não nula. Junções, agregações, aliases nas colunas projetadas, LIMIT/OFFSET existentes e expressões incompatíveis são rejeitados. A paginação é somente leitura em ambos os modos de acesso. `max_rows` limita toda a sequência; limites de linhas e tempo omitidos usam os padrões de consulta. O tamanho padrão de página é 100, limitado pelo saldo de linhas e pelos bytes da resposta. As configurações numéricas de paginação exigem inteiros positivos; o tamanho padrão não pode exceder o máximo. Valores inválidos interrompem a inicialização.

As páginas retornam JSON no conteúdo de texto, incluindo `rows`, `returned_rows`, `total_returned_rows`, `max_rows`, `page_size`, `truncated`, `has_more`, `next_cursor` e `expires_in_seconds`. Continue enquanto houver `next_cursor`; `has_more` pode ser nulo quando o limite de bytes impede determinar se existem mais linhas. A página final não tem cursor. Atingir `max_rows` encerra a sequência mesmo que existam mais linhas na tabela.

A continuação aceita apenas o cursor e o tamanho opcional de página, dentro do máximo configurado. SQL, banco, modo e limites totais não podem mudar. Cada página verifica novamente a autorização do banco e recebe um novo prazo; nenhuma conexão ou transação fica aberta entre páginas. A resposta informa `consistency="best_effort"`: as páginas não compartilham um snapshot. Inserções ou exclusões concorrentes podem fazer a paginação por offset repetir ou pular linhas. A paginação keyset exige uma chave de ordenação verificada como única e não nula, que permaneça estável durante toda a sequência; ela evita deslocamentos de offset, mas ainda vê alterações posteriores, e inserções anteriores à última chave não são revisitadas.

Cursores são opacos, vinculados à credencial HTTP autenticada por um hash SHA-256 (ou ao processo/sessão stdio atual) e armazenados apenas no processo servidor. Cada token de continuação é consumido no máximo uma vez: uma página concluída consome o token e emite outro quando necessário. Uma falha antes da confirmação mantém o cursor original e sua expiração, permitindo repetir a chamada enquanto ele for válido. Se a resposta se perder após a confirmação, a repetição falha com `CURSOR_INVALID`; reinicie a consulta se o próximo cursor foi perdido. Por padrão, os cursores expiram após 300 segundos (`CURSOR_EXPIRED`) e podem ser removidos ao atingir a capacidade. Reinício, encerramento, remoção por capacidade, outro processo servidor ou outra credencial autenticada invalidam a continuação (`CURSOR_INVALID`). Renovar ou rotacionar o token bearer também invalida seus cursores. Não compartilhe cursores nem suponha portabilidade entre workers.

**O que é descobrível.** Um banco de dados só é listado se não for um template, aceitar conexões, a role tiver `CONNECT` nele e passar pelas listas de permissão e de bloqueio.
O banco de dados em `DATABASE_URI` é apenas a conexão de bootstrap: ele não é especial.
Ele só pode ser usado pelas ferramentas se também for elegível, de modo que a URI pode apontar para `postgres` enquanto `postgres` está excluído.
O banco de dados padrão precisa ser elegível: se os filtros o excluírem, ou se ele não existir ou não aceitar conexões, o servidor falha com um erro de configuração em vez de escolher silenciosamente outro banco de dados.

**Modo de acesso.** Com `DATABASE_AUTO_DISCOVER=true` e sem `--access-mode`, o servidor executa em modo `restricted`.
A escrita só é habilitada por um `--access-mode=unrestricted` explícito, que registra um aviso na inicialização e continua limitado pelos privilégios reais da role do PostgreSQL.
Sem descoberta, o padrão continua sendo `unrestricted`.
O modo é global para o processo do servidor, não por banco de dados.
`restricted` é uma camada extra, não um substituto para uma role do PostgreSQL com privilégio mínimo.

**Pools sob demanda, limites e limpeza de ociosos.**
- Nenhum pool é aberto na inicialização e `list_databases` nunca abre um; um pool é criado na primeira chamada de ferramenta que tem como alvo um banco de dados (`min_size=0`, até `DATABASE_POOL_MAX_SIZE` conexões).
- No máximo `DATABASE_MAX_POOLS` pools ficam abertos. Ao atingir o limite, fecha-se o pool menos recentemente usado que não tenha chamada em andamento. Se todos os pools estiverem em uso, a chamada falha com um erro explícito de capacidade e nada é fechado.
- Um pool é mantido durante toda a duração de uma chamada de ferramenta, portanto nunca é fechado enquanto uma chamada está em execução.
- Pools ociosos há mais de `DATABASE_POOL_IDLE_SECONDS` são fechados de forma oportunista em chamadas e atualizações de catálogo posteriores; não há temporizador em segundo plano.
- Bancos de dados que desaparecem do catálogo deixam de aceitar novas chamadas e seu pool é fechado quando as chamadas em execução terminam.
- Uma falha de conexão em um banco de dados é reportada apenas para aquele banco de dados; os demais bancos de dados e o pool do banco que falhou continuam funcionando depois que o problema é corrigido. Erros comuns de SQL não invalidam um pool.
- Chamadas que aguardam um pool que está sendo aberto compartilham o resultado dessa abertura. Se a abertura falhar, elas recebem o mesmo erro em vez de cada uma tentar a conexão novamente em sequência.

**Atualização.** A lista fica em cache por `DATABASE_DISCOVERY_TTL_SECONDS`. Um banco de dados criado depois é detectado por `list_databases` com `refresh=true`, ou pela primeira chamada após a expiração do TTL, sem reiniciar o servidor.
Pedir um nome desconhecido força uma atualização antes de a chamada ser rejeitada.
As atualizações forçadas (`refresh=true` ou um nome desconhecido) ocorrem no máximo uma vez a cada 5 segundos; dentro dessa janela a lista em cache é usada, e solicitações concorrentes compartilham uma única descoberta em andamento.
Uma consulta de descoberta que não termina em 10 segundos conta como uma atualização com falha.
Se uma atualização falhar, a lista anterior é servida por um curto período de tolerância (no máximo 300 segundos), sem admitir novos nomes, e `list_databases` informa `catalog_stale: true`.
Se ainda não houver uma lista válida, a chamada falha com o erro "discovery is unavailable".
Se o banco de dados de bootstrap estiver inacessível na inicialização, o servidor ainda inicia, em estado degradado.

**Restrição à mesma instância.** Todos os bancos de dados vêm da instância indicada por `DATABASE_URI`. O argumento `database` aceita apenas um nome de banco de dados, nunca um DSN, host ou esquema, portanto não há como alcançar outro servidor, e um nome nunca é inserido no SQL. Nada se conecta a um banco de dados que não tenha sido descoberto e autorizado.
Os bancos de dados são conexões separadas: não há SQL entre bancos de dados.

**Métricas de toda a instância.**
- `get_top_queries` e as ferramentas de ajuste de índices leem `pg_stat_statements` apenas para o banco de dados selecionado (filtrado por `dbid`). A extensão deve estar instalada em cada banco de dados que você consulta; uma extensão ausente é reportada para aquele banco de dados.
- `analyze_db_health`: as verificações `connection` e `replication` descrevem a instância inteira e são rotuladas `[instance-wide]` na saída; as demais verificações são executadas no banco de dados selecionado.

### Escolhendo um banco de dados

`list_databases` aceita um argumento opcional `refresh` e retorna JSON como:

```json
[
  {"name": "analytics", "is_default": false, "connection_state": "not_connected", "catalog_stale": false},
  {"name": "app_development", "is_default": true, "connection_state": "connected", "catalog_stale": false}
]
```

`connection_state` é `connected` (pool aberto), `not_connected` (ainda sem pool) ou `unavailable` (a última tentativa de abrir um pool falhou).
Exemplos de prompts:

> Quais bancos de dados você consegue ver? Atualize a lista primeiro.

> Liste as tabelas do esquema `public` em `app_testing` e depois compare-as com `analytics`.

> Execute `SELECT current_database()` em `analytics`.

A mesma chamada, como argumentos da ferramenta: `{"sql": "SELECT current_database()", "database": "analytics"}`.

## Instalação de extensões do Postgres (opcional)

Para habilitar o ajuste de índices e a análise abrangente de desempenho, você precisa carregar as extensões `pg_stat_statements` e `hypopg` no seu banco de dados.

- A extensão `pg_stat_statements` permite que o Postgres MCP Pro analise estatísticas de execução de consultas.
Por exemplo, isso permite entender quais consultas estão lentas ou consumindo recursos significativos.
- A extensão `hypopg` permite que o Postgres MCP Pro simule o comportamento do planejador de consultas do Postgres após a adição de índices.

### Instalando extensões no AWS RDS, Azure SQL ou Google Cloud SQL

Se o seu banco de dados Postgres roda em um serviço gerenciado de um provedor de nuvem, as extensões `pg_stat_statements` e `hypopg` já devem estar disponíveis no sistema.
Nesse caso, basta executar os comandos `CREATE EXTENSION` usando uma role com privilégios suficientes:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS hypopg;
```

### Instalando extensões em um Postgres autogerenciado

Se você gerencia sua própria instalação do Postgres, talvez precise de trabalho adicional.
Antes de carregar a extensão `pg_stat_statements`, você deve garantir que ela esteja listada em `shared_preload_libraries` no arquivo de configuração do Postgres.
A extensão `hypopg` também pode exigir uma instalação adicional no nível do sistema (por exemplo, pelo seu gerenciador de pacotes), porque nem sempre acompanha o Postgres.

## Exemplos de uso

### Obter uma visão geral da saúde do banco de dados

Pergunte:
> Verifique a saúde do meu banco de dados e identifique quaisquer problemas.

### Analisar consultas lentas

Pergunte:
> Quais são as consultas mais lentas do meu banco de dados? E como posso acelerá-las?

### Obter recomendações para acelerar as coisas

Pergunte:
> Meu aplicativo está lento. Como posso torná-lo mais rápido?

### Gerar recomendações de índices

Pergunte:
> Analise a carga de trabalho do meu banco de dados e sugira índices para melhorar o desempenho.

### Otimizar uma consulta específica

Pergunte:
> Ajude-me a otimizar esta consulta: SELECT \* FROM orders JOIN customers ON orders.customer_id = customers.id WHERE orders.created_at > '2023-01-01';

<a id="mcp-server-api"></a>
## API do servidor MCP

O [padrão MCP](https://modelcontextprotocol.io/) define vários tipos de endpoints: Tools, Resources, Prompts e outros.

O Postgres MCP Pro fornece funcionalidade apenas por meio de [ferramentas MCP](https://modelcontextprotocol.io/docs/concepts/tools).
Escolhemos essa abordagem porque o [ecossistema de clientes MCP](https://modelcontextprotocol.io/clients) tem amplo suporte a ferramentas MCP.
Isso contrasta com a abordagem de outros servidores MCP para Postgres, incluindo o [Reference Postgres MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres), que usam [recursos MCP](https://modelcontextprotocol.io/docs/concepts/resources) para expor informações de esquema.


Ferramentas do Postgres MCP Pro (todas, exceto `list_databases` e `fetch_query_page`, aceitam um argumento opcional `database`, veja [Múltiplos bancos de dados](#multiple-databases-optional)):

| Nome da ferramenta | Descrição |
|--------------------|-----------|
| `list_databases` | Lista os bancos de dados que o servidor pode usar, o padrão, o estado da conexão e se a lista está desatualizada (`refresh` força uma nova consulta). Nunca abre conexões. |
| `list_schemas` | Lista todos os esquemas de banco de dados disponíveis na instância PostgreSQL. |
| `list_objects` | Lista objetos de banco de dados (tabelas, views, sequências, extensões) dentro de um esquema especificado. |
| `get_object_details` | Fornece informações sobre um objeto de banco de dados específico, por exemplo, as colunas, restrições e índices de uma tabela. |
| `execute_sql` | Executa SQL, com paginação opcional somente leitura nos modos `offset` ou `keyset`. |
| `fetch_query_page` | Continua uma consulta paginada usando apenas o cursor e o tamanho opcional de página. |
| `explain_query` | Obtém o plano de execução de uma consulta SQL, descrevendo como o PostgreSQL a processará e expondo o modelo de custos do planejador de consultas. Pode ser invocada com índices hipotéticos para simular o comportamento após a adição de índices. |
| `get_top_queries` | Informa as consultas SQL mais lentas com base no tempo total de execução, usando dados de `pg_stat_statements`. |
| `analyze_workload_indexes` | Analisa a carga de trabalho do banco de dados para identificar consultas que consomem muitos recursos e, em seguida, recomenda os índices ideais para elas. |
| `analyze_query_indexes` | Analisa uma lista de consultas SQL específicas (até 10) e recomenda os índices ideais para elas. |
| `analyze_db_health` | Executa verificações de saúde abrangentes, incluindo: taxas de acerto do cache de buffers, saúde das conexões, validação de restrições, saúde dos índices (duplicados/não utilizados/inválidos), limites de sequências e saúde do vacuum. |


<a id="related-projects"></a>
## Projetos relacionados

**Servidores MCP para Postgres**
- [Query MCP](https://github.com/alexander-zuev/supabase-mcp-server). Um servidor MCP para o Postgres do Supabase com uma arquitetura de segurança em três camadas e suporte à API de gerenciamento do Supabase.
- [PG-MCP](https://github.com/stuzero/pg-mcp-server). Um servidor MCP para PostgreSQL com opções flexíveis de conexão, planos de execução, contexto de extensões e mais.
- [Reference PostgreSQL MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres). Uma implementação simples de servidor MCP que expõe informações de esquema como recursos MCP e executa consultas somente leitura.
- [Supabase Postgres MCP Server](https://github.com/supabase-community/supabase-mcp). Este servidor MCP oferece recursos de gerenciamento do Supabase e é mantido ativamente pela comunidade do Supabase.
- [Nile MCP Server](https://github.com/niledatabase/nile-mcp-server). Um servidor MCP que dá acesso à API de gerenciamento do serviço de Postgres multi-tenant da Nile.
- [Neon MCP Server](https://github.com/neondatabase-labs/mcp-server-neon). Um servidor MCP que dá acesso à API de gerenciamento do serviço de Postgres serverless da Neon.
- [Wren MCP Server](https://github.com/Canner/wren-engine). Fornece um motor semântico que alimenta business intelligence para Postgres e outros bancos de dados.

**Ferramentas de DBA (incluindo ofertas comerciais)**
- [Aiven Database Optimizer](https://aiven.io/solutions/aiven-ai-database-optimizer). Uma ferramenta que oferece análise holística da carga de trabalho do banco de dados, otimizações de consultas e outras melhorias de desempenho.
- [dba.ai](https://www.dba.ai/). Um assistente de administração de banco de dados com IA que se integra ao GitHub para resolver problemas de código.
- [pgAnalyze](https://pganalyze.com/). Uma plataforma abrangente de monitoramento e análise para identificar gargalos de desempenho, otimizar consultas e emitir alertas em tempo real.
- [Postgres.ai](https://postgres.ai/). Uma experiência de chat interativa que combina uma extensa base de conhecimento de Postgres e o GPT-4.
- [Xata Agent](https://github.com/xataio/agent). Um agente de IA open source que monitora automaticamente a saúde do banco de dados, diagnostica problemas e fornece recomendações usando raciocínio baseado em LLM e playbooks.

**Utilitários para Postgres**
- [Dexter](https://github.com/DexterDB/dexter). Uma ferramenta para gerar e testar índices hipotéticos no PostgreSQL.
- [PgHero](https://github.com/ankane/pghero). Um painel de desempenho para Postgres, com recomendações.
O Postgres MCP Pro incorpora verificações de saúde do PgHero.
- [PgTune](https://github.com/le0pard/pgtune?tab=readme-ov-file). Heurísticas para ajustar a configuração do Postgres.

<a id="frequently-asked-questions"></a>
## Perguntas frequentes

*Como o Postgres MCP Pro é diferente de outros servidores MCP para Postgres?*
Existem muitos servidores MCP que permitem que um agente de IA execute consultas em um banco de dados Postgres.
O Postgres MCP Pro também faz isso, mas adiciona ferramentas para entender e melhorar o desempenho do seu banco de dados Postgres.
Por exemplo, ele implementa uma versão do [Anytime Algorithm of Database Tuning Advisor for Microsoft SQL Server](https://www.microsoft.com/en-us/research/wp-content/uploads/2020/06/Anytime-Algorithm-of-Database-Tuning-Advisor-for-Microsoft-SQL-Server.pdf), um algoritmo moderno, de nível industrial, para ajuste automático de índices.

| Postgres MCP Pro | Outros servidores MCP para Postgres |
|--------------|----------------------------|
| ✅ Verificações de saúde do banco de dados determinísticas | ❌ Consultas de saúde geradas por LLM e não repetíveis |
| ✅ Estratégias de busca de índices fundamentadas | ❌ Palpites de IA generativa para melhorias de indexação |
| ✅ Análise de carga de trabalho para encontrar os principais problemas | ❌ Análise de problemas inconsistente |
| ✅ Simula melhorias de desempenho | ❌ Teste por conta própria e veja se funciona |

O Postgres MCP Pro complementa a IA generativa adicionando ferramentas determinísticas e algoritmos clássicos de otimização.
A combinação é, ao mesmo tempo, confiável e flexível.


*Por que ferramentas MCP são necessárias se o LLM consegue raciocinar, gerar SQL etc.?*
Os LLMs são valiosos em tarefas que envolvem ambiguidade, raciocínio ou linguagem natural.
Em comparação com código procedural, porém, eles podem ser lentos, caros, não determinísticos e, às vezes, produzir resultados pouco confiáveis.
No caso do ajuste de bancos de dados, temos algoritmos consolidados, desenvolvidos ao longo de décadas, com eficácia comprovada.
O Postgres MCP Pro permite combinar o melhor dos dois mundos, unindo LLMs a algoritmos clássicos de otimização e outras ferramentas procedurais.

*Como vocês testam o Postgres MCP Pro?*
Os testes são essenciais para garantir que o Postgres MCP Pro seja confiável e preciso.
Estamos construindo um conjunto de cargas de trabalho adversariais geradas por IA, criadas para desafiar o Postgres MCP Pro e garantir que ele se saia bem em uma ampla variedade de cenários.

*Quais versões do Postgres são suportadas?*
Nossos testes atualmente se concentram no Postgres 15, 16 e 17.
Planejamos oferecer suporte às versões 13 a 17 do Postgres.

*Quem criou este projeto?*
Este projeto é criado e mantido pela [Crystal DBA](https://www.crystaldba.ai).

## Roadmap

*A definir*

Você e as suas necessidades são um fator decisivo para o que construímos.
Conte-nos o que você quer ver abrindo uma [issue](https://github.com/crystaldba/postgres-mcp/issues) ou um [pull request](https://github.com/crystaldba/postgres-mcp/pulls).
Você também pode falar conosco no [Discord](https://discord.gg/4BEHC7ZM).

<a id="technical-notes"></a>
## Notas técnicas

Esta seção traz uma visão geral de alto nível das considerações técnicas que influenciaram o design do Postgres MCP Pro.

### Ajuste de índices

Desenvolvedores sabem que a falta de índices é uma das causas mais comuns de problemas de desempenho em bancos de dados.
Os índices fornecem métodos de acesso que permitem ao Postgres localizar rapidamente os dados necessários para executar uma consulta.
Quando as tabelas são pequenas, os índices fazem pouca diferença, mas, à medida que o volume de dados cresce, a diferença de complexidade algorítmica entre uma varredura de tabela e uma busca por índice se torna significativa (tipicamente *O*(*n*) contra *O*(*log* *n*), potencialmente mais se houver junções entre várias tabelas).

A geração de sugestões de índices no Postgres MCP Pro ocorre em várias etapas:

1. *Identificar as consultas SQL que precisam de ajuste*.
    Se você sabe que está tendo problemas com uma consulta SQL específica, pode fornecê-la.
    O Postgres MCP Pro também pode analisar a carga de trabalho para identificar alvos de ajuste de índices.
    Para isso, ele depende da extensão `pg_stat_statements`, que registra o tempo de execução e o consumo de recursos de cada consulta.

    Uma consulta é candidata ao ajuste de índices se for uma das que mais consomem recursos, seja por execução ou em conjunto.
    No momento, usamos o tempo de execução como substituto do consumo cumulativo de recursos, mas também pode fazer sentido olhar recursos específicos, por exemplo, o número de blocos acessados ou o número de blocos lidos do disco.
    A ferramenta `analyze_query_workload` foca em consultas lentas, usando o tempo médio por execução com limites para a contagem de execuções e para o tempo médio de execução.
    Os agentes também podem chamar `get_top_queries`, que aceita um parâmetro para tempo médio ou total de execução, e então passar essas consultas para `analyze_query_indexes` a fim de obter recomendações de índices.

    Sistemas sofisticados de ajuste de índices usam "compressão de carga de trabalho" para produzir um subconjunto representativo de consultas que reflete as características da carga de trabalho como um todo, reduzindo o problema para os algoritmos seguintes.
    O Postgres MCP Pro realiza uma forma limitada de compressão de carga de trabalho ao normalizar as consultas, de modo que aquelas geradas a partir do mesmo template apareçam como uma só.
    Ele atribui o mesmo peso a cada consulta, uma simplificação que funciona quando os benefícios da indexação são grandes.

2. *Gerar índices candidatos*
    Uma vez que temos uma lista de consultas SQL que queremos melhorar por meio de indexação, geramos uma lista de índices que talvez queiramos adicionar.
    Para isso, analisamos o SQL e identificamos as colunas usadas em filtros, junções, agrupamentos ou ordenações.

    Para gerar todos os índices possíveis, precisamos considerar combinações dessas colunas, porque o Postgres oferece suporte a [índices multicoluna](https://www.postgresql.org/docs/current/indexes-multicolumn.html).
    Na implementação atual, incluímos apenas uma permutação de cada possível índice multicoluna, selecionada aleatoriamente.
    Fazemos essa simplificação para reduzir o espaço de busca, porque as permutações costumam ter desempenho equivalente.
    No entanto, esperamos melhorar nessa área.

3. *Buscar a configuração ótima de índices*.
    Nosso objetivo é encontrar a combinação de índices que equilibre da melhor forma os benefícios de desempenho contra os custos de armazenar e manter esses índices.
    Estimamos a melhoria de desempenho usando os recursos de "e se?" fornecidos pela extensão `hypopg`.
    Ela simula como o otimizador de consultas do Postgres executará uma consulta após a adição de índices e informa as mudanças com base no modelo de custos real do Postgres.

    Um desafio é que gerar planos de consulta geralmente exige conhecimento dos valores específicos dos parâmetros usados na consulta.
    A normalização de consultas, necessária para reduzir as consultas em consideração, remove as constantes dos parâmetros.
    Os valores de parâmetros fornecidos por meio de variáveis de bind também não estão disponíveis para nós.

    Para resolver esse problema, produzimos constantes realistas, que podemos fornecer como parâmetros, por amostragem das estatísticas da tabela.
    Na versão 16, o Postgres adicionou a [funcionalidade de plano de execução genérico](https://www.postgresql.org/docs/current/sql-explain.html), mas ela tem limitações, por exemplo, em torno de cláusulas `LIKE`, que a nossa implementação não tem.

    A estratégia de busca é crítica, porque avaliar todas as combinações possíveis de índices só é viável em situações simples.
    Isso é o que mais distingue as várias abordagens de indexação.
    Adaptando a abordagem do algoritmo Anytime da Microsoft, empregamos uma estratégia de busca gulosa (greedy), ou seja, encontramos a melhor solução com um índice e depois o melhor índice a adicionar a ela para produzir uma solução com dois índices.
    Nossa busca termina quando o orçamento de tempo se esgota ou quando uma rodada de exploração não produz ganhos acima do limite mínimo de melhoria de 10%.

4. *Análise de custo-benefício*.
    Diante de duas alternativas de indexação, uma que produz melhor desempenho e outra que exige mais espaço, como decidimos qual escolher?
    Tradicionalmente, os assistentes de índices pedem um orçamento de armazenamento e otimizam o desempenho em relação a esse orçamento.
    Nós também recebemos um orçamento de armazenamento, mas realizamos uma análise de custo-benefício ao longo de toda a otimização.

    Formulamos isso como o problema de selecionar um ponto ao longo da [fronteira de Pareto](https://en.wikipedia.org/wiki/Pareto_front), o conjunto de escolhas para as quais melhorar uma métrica de qualidade necessariamente piora outra.
    Em um mundo ideal, poderíamos querer avaliar o custo do armazenamento e o benefício do melhor desempenho em termos monetários.
    No entanto, existe uma abordagem mais simples e mais prática: olhar as mudanças em termos relativos.
    A maioria das pessoas concordaria que uma melhoria de desempenho de 100x vale a pena, mesmo que o custo de armazenamento seja 2x.
    Em nossa implementação, usamos um parâmetro configurável para definir esse limite.
    Por padrão, exigimos que a mudança no log (base 10) da melhoria de desempenho seja 2x a diferença no log do custo de espaço.
    Isso equivale a permitir, no máximo, um aumento de 10x no espaço para uma melhoria de desempenho de 100x.

Nossa implementação é mais próxima do [Anytime Algorithm](https://www.microsoft.com/en-us/research/wp-content/uploads/2020/06/Anytime-Algorithm-of-Database-Tuning-Advisor-for-Microsoft-SQL-Server.pdf) encontrado no Microsoft SQL Server.
Em comparação com o [Dexter](https://github.com/ankane/dexter/), uma ferramenta de indexação automática para Postgres, pesquisamos um espaço maior e usamos heurísticas diferentes.
Isso nos permite gerar soluções melhores ao custo de um tempo de execução maior.

Também mostramos o trabalho feito em cada rodada da busca, incluindo uma comparação dos planos de consulta antes e depois da adição de cada índice.
Isso dá ao LLM contexto adicional que ele pode usar ao responder às recomendações de indexação.

### Experimental: ajuste de índices por LLM

O Postgres MCP Pro inclui um recurso experimental de ajuste de índices baseado em [Optimization by LLM](https://arxiv.org/abs/2309.03409).
Em vez de usar heurísticas para explorar possíveis configurações de índices, fornecemos o esquema do banco de dados e os planos de consulta a um LLM e pedimos que ele proponha configurações de índices.
Em seguida, usamos o `hypopg` para prever o desempenho com os índices propostos e devolvemos esses resultados ao LLM para produzir um novo conjunto de sugestões.
Repetimos esse processo até que várias rodadas de iteração não produzam mais melhorias.

A otimização de índices por LLM tem vantagens quando o espaço de busca de índices é grande ou quando é preciso considerar índices com muitas colunas.
Assim como as abordagens tradicionais baseadas em busca, ela depende da precisão das previsões de desempenho do `hypopg`.

Para realizar a otimização de índices por LLM, você deve fornecer uma chave de API da OpenAI definindo a variável de ambiente `OPENAI_API_KEY`.


### Saúde do banco de dados

As verificações de saúde do banco de dados identificam oportunidades de ajuste e necessidades de manutenção antes que elas levem a problemas críticos.
Na versão atual, o Postgres MCP Pro adapta as verificações de saúde do banco de dados diretamente do [PgHero](https://github.com/ankane/pghero).
Estamos trabalhando para validar totalmente essas verificações e podemos estendê-las no futuro.

- *Saúde dos índices*. Procura índices não utilizados, índices duplicados e índices inchados (bloated). Índices inchados fazem uso ineficiente das páginas do banco de dados.
  O autovacuum do Postgres limpa as entradas de índice que apontam para tuplas mortas e as marca como reutilizáveis. No entanto, ele não compacta as páginas do índice e, com o tempo, as páginas do índice podem conter poucas referências a tuplas vivas.
- *Taxa de acerto do cache de buffers*. Mede a proporção de leituras do banco de dados atendidas pelo cache de buffers em vez do disco.
  Uma taxa de acerto baixa deve ser investigada, pois muitas vezes não é ideal em termos de custo e leva à degradação do desempenho da aplicação.
- *Saúde das conexões*. Verifica o número de conexões com o banco de dados e informa sua utilização.
  O maior risco é ficar sem conexões, mas um número alto de conexões ociosas ou bloqueadas também pode indicar problemas.
- *Saúde do vacuum*. O vacuum é importante por muitos motivos.
  Um dos críticos é evitar o wraparound do ID de transação, que pode fazer o banco de dados parar de aceitar escritas.
  O mecanismo de controle de concorrência multiversão (MVCC) do Postgres exige um ID de transação único para cada transação.
  No entanto, como o Postgres usa um inteiro de 32 bits com sinal para os IDs de transação, ele precisa reutilizá-los após no máximo 2 bilhões de transações.
  Para isso, ele "congela" (freeze) os IDs de transação de transações históricas, definindo todos eles com um valor especial que indica um passado distante.
  Quando os registros são gravados em disco pela primeira vez, eles recebem visibilidade para um intervalo de IDs de transação.
  Antes de reutilizar esses IDs de transação, o Postgres deve atualizar os registros em disco, "congelando-os" para remover as referências aos IDs de transação que serão reutilizados.
  Esta verificação procura tabelas que precisam de vacuum para evitar o wraparound do ID de transação.
- *Saúde da replicação*. Verifica a saúde da replicação monitorando o atraso entre o primário e as réplicas, verificando o status da replicação e acompanhando o uso dos slots de replicação.
- *Saúde das restrições*. Durante a operação normal, o Postgres rejeita quaisquer transações que causariam uma violação de restrição.
  No entanto, restrições inválidas podem ocorrer após o carregamento de dados ou em cenários de recuperação. Esta verificação procura quaisquer restrições inválidas.
- *Saúde das sequências*. Procura sequências que estejam em risco de exceder seu valor máximo.


### Biblioteca cliente do Postgres

O Postgres MCP Pro usa o [psycopg3](https://www.psycopg.org/) para se conectar ao Postgres com E/S assíncrona.
Por baixo dos panos, o psycopg3 usa a biblioteca [libpq](https://www.postgresql.org/docs/current/libpq.html) para se conectar ao Postgres, dando acesso ao conjunto completo de recursos do Postgres e a uma implementação subjacente totalmente suportada pela comunidade do Postgres.

Alguns outros servidores MCP baseados em Python usam o [asyncpg](https://github.com/MagicStack/asyncpg), que pode simplificar a instalação ao eliminar a dependência da `libpq`.
O Asyncpg também é provavelmente [mais rápido](https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/) que o psycopg3, mas não validamos isso por conta própria.
[Benchmarks mais antigos](https://gistpreview.github.io/?0ed296e93523831ea0918d42dd1258c2) relatam uma diferença de desempenho maior, sugerindo que o psycopg3, mais novo, reduziu a diferença à medida que amadurece.

Equilibrando essas considerações, escolhemos o `psycopg3` em vez do `asyncpg`.
Continuamos abertos a rever essa decisão no futuro.


### Configuração de conexão

Assim como o [Reference PostgreSQL MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres), o Postgres MCP Pro recebe as informações de conexão com o Postgres na inicialização.
Isso é conveniente para usuários que sempre se conectam ao mesmo banco de dados, mas pode ser trabalhoso quando os usuários trocam de banco de dados.

Uma abordagem alternativa, adotada pelo [PG-MCP](https://github.com/stuzero/pg-mcp-server), é fornecer os detalhes de conexão por meio de chamadas de ferramentas MCP no momento do uso.
Isso é mais conveniente para usuários que trocam de banco de dados e permite que um único servidor MCP atenda simultaneamente vários usuários finais.

Deve haver uma abordagem melhor do que qualquer uma dessas duas.
Ambas têm fraquezas de segurança: poucos clientes MCP armazenam a configuração do servidor MCP com segurança (uma exceção é o Goose), e as credenciais fornecidas por meio de ferramentas MCP passam pelo LLM e são armazenadas no histórico do chat.
Ambas também têm problemas de usabilidade em alguns cenários.


### Informações de esquema

O objetivo da ferramenta de informações de esquema é fornecer ao agente de IA chamador as informações de que ele precisa para gerar SQL correto e eficiente.
Por exemplo, suponha que um usuário pergunte: "Quantos voos decolaram de San Francisco e pousaram em Paris no último ano?"
O agente de IA precisa encontrar a tabela que armazena os voos, as colunas que armazenam a origem e os destinos e, talvez, uma tabela que mapeie códigos de aeroportos para localizações de aeroportos.


*Por que fornecer ferramentas de informações de esquema se os LLMs geralmente são capazes de gerar o SQL para obter essas informações diretamente do Postgres?*

Nossa experiência com o Claude indica que o LLM chamador é muito bom em gerar SQL para explorar o esquema do Postgres consultando o [catálogo do sistema do Postgres](https://www.postgresql.org/docs/current/catalogs.html) e o [information schema](https://www.postgresql.org/docs/current/information-schema.html) (uma visão de metadados de banco de dados padronizada pelo ANSI).
No entanto, não sabemos se outros LLMs fazem isso de forma tão confiável e competente.

*Seria melhor fornecer informações de esquema usando [recursos MCP](https://modelcontextprotocol.io/docs/concepts/resources) em vez de [ferramentas MCP](https://modelcontextprotocol.io/docs/concepts/tools)?*

O [Reference PostgreSQL MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres) usa recursos para expor informações de esquema em vez de ferramentas.
Navegar por recursos é semelhante a navegar por um sistema de arquivos, então essa abordagem é natural em muitos aspectos.
No entanto, o suporte a recursos é menos difundido do que o suporte a ferramentas no ecossistema de clientes MCP (veja [exemplos de clientes](https://modelcontextprotocol.io/clients)).
Além disso, embora o padrão MCP diga que os recursos podem ser acessados tanto por agentes de IA quanto por usuários humanos finais, alguns clientes só oferecem suporte à navegação humana na árvore de recursos.


### Execução protegida de SQL

A IA amplifica desafios antigos de proteger bancos de dados contra uma série de ameaças, que vão de erros simples a ataques sofisticados de agentes mal-intencionados.
Seja a ameaça acidental ou maliciosa, aplica-se um arcabouço de segurança semelhante, com objetivos que se enquadram em três categorias: confidencialidade, integridade e disponibilidade.
A conhecida tensão entre conveniência e segurança também é evidente e acentuada.

O modo de execução protegida de SQL do Postgres MCP Pro foca na integridade.
No contexto do MCP, nossa maior preocupação é o SQL gerado por LLM causar danos, por exemplo, modificação ou exclusão não intencional de dados, ou outras mudanças que possam contornar o processo de gestão de mudanças de uma organização.

A forma mais simples de garantir integridade é assegurar que todo o SQL executado no banco de dados seja somente leitura.
Uma maneira de fazer isso é criar um usuário de banco de dados com permissões de acesso somente leitura.
Embora seja uma boa abordagem, muitos a consideram trabalhosa na prática.
O Postgres não oferece uma forma de colocar uma conexão ou sessão em modo somente leitura, então o Postgres MCP Pro usa uma abordagem mais complexa para garantir a execução de SQL somente leitura sobre uma conexão de leitura e escrita.

O Postgres MCP oferece um modo de transação somente leitura que impede modificações de dados e de esquema.
Assim como o [Reference PostgreSQL MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres), usamos transações somente leitura para fornecer execução protegida de SQL.

Para tornar esse mecanismo robusto, precisamos garantir que o SQL não contorne de alguma forma o modo de transação somente leitura, por exemplo, emitindo uma instrução `COMMIT` ou `ROLLBACK` e iniciando em seguida uma nova transação.

Por exemplo, o LLM pode contornar o modo de transação somente leitura emitindo uma instrução `ROLLBACK` e iniciando em seguida uma nova transação.
Por exemplo:
```sql
ROLLBACK; DROP TABLE users;
```

Para evitar casos como esse, analisamos o SQL antes da execução usando a biblioteca [pglast](https://pglast.readthedocs.io/).
Rejeitamos qualquer SQL que contenha instruções `commit` ou `rollback`.
Felizmente, as linguagens de procedimentos armazenados populares do Postgres, incluindo PL/pgSQL e PL/Python, não permitem instruções `COMMIT` ou `ROLLBACK`.
Se você tem linguagens de procedimentos armazenados inseguras habilitadas no seu banco de dados, nossas proteções de somente leitura podem ser contornadas.

No momento, o Postgres MCP Pro oferece dois níveis de proteção para o banco de dados, um em cada extremo do espectro conveniência/segurança.
- "Unrestricted" oferece máxima flexibilidade.
É adequado para ambientes de desenvolvimento em que velocidade e flexibilidade são primordiais e em que não há necessidade de proteger dados valiosos ou sensíveis.
- "Restricted" oferece um equilíbrio entre flexibilidade e segurança.
É adequado para ambientes de produção em que o banco de dados está exposto a usuários não confiáveis e em que é importante proteger dados valiosos ou sensíveis.

O modo Unrestricted se alinha à abordagem do [modo auto-run do Cursor](https://docs.cursor.com/chat/tools#auto-run), em que o agente de IA opera com supervisão ou aprovações humanas limitadas.
Esperamos que o auto-run seja usado em ambientes de desenvolvimento em que as consequências de erros são baixas, em que os bancos de dados não contêm dados valiosos ou sensíveis e em que podem ser recriados ou restaurados a partir de backups quando necessário.

Projetamos o modo Restricted para ser conservador, pecando pelo lado da segurança mesmo que isso possa ser inconveniente.
O modo Restricted é limitado a operações somente leitura, e limitamos o tempo de execução das consultas para evitar que consultas de longa duração afetem o desempenho do sistema.
Podemos adicionar medidas no futuro para garantir que o modo Restricted seja seguro para uso com bancos de dados de produção.


## Desenvolvimento do Postgres MCP Pro

As instruções abaixo são para desenvolvedores que querem trabalhar no Postgres MCP Pro, ou para usuários que preferem instalar o Postgres MCP Pro a partir do código-fonte.

### Configuração do ambiente de desenvolvimento local

1. **Instale o uv**:

   ```bash
   curl -sSL https://astral.sh/uv/install.sh | sh
   ```

2. **Clone o repositório**:

   ```bash
   git clone https://github.com/crystaldba/postgres-mcp.git
   cd postgres-mcp
   ```

3. **Instale as dependências**:

   ```bash
   uv pip install -e .
   uv sync
   ```

4. **Execute o servidor**:
   ```bash
   uv run postgres-mcp "postgres://user:password@localhost:5432/dbname"
   ```
