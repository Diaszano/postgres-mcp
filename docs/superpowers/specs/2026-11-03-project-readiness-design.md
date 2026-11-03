# Organização e prontidão do postgres-mcp

Data: 2026-11-03
Status: proposta para aprovação; abordagem incremental escolhida pelo mantenedor.

## Intenção

Tornar o fork Diaszano/postgres-mcp confiável para instalar, usar, contribuir,
manter e publicar. Traduzir “100% usável” em critérios verificáveis, sem prometer
ausência de defeitos ou compatibilidade com ambientes não testados.

O mantenedor pediu validação e evolução de CI/CD, organização do projeto e do
código, Conventional Commits, branches e documentação. Escolheu validar e
corrigir por etapas, aproveitando o que já existe.

## Estado observado

- Árvore de trabalho limpa em main na inspeção inicial.
- Python >=3.12, uv.lock, Ruff, Pyright, pytest e empacotamento Hatchling.
- Código organizado em serviços de aplicação, SQL, segurança, paginação,
  limites, observabilidade e ferramentas de análise de PostgreSQL.
- CI com convenções, lint, tipos, testes unitários e de release, pacote e
  integração com PostgreSQL 16/17; PostgreSQL 18 experimental.
- Release reutilizável com Python Semantic Release, GHCR multiarch e recuperação
  de publicação; scripts de scan e promoção por digest já existem.
- CONTRIBUTING, SECURITY, CODEOWNERS, Dependabot, templates e documentação
  operacional já existem. Seus arquivos não comprovam configurações remotas.
- README mistura identidade upstream, instalação pelo PyPI e imagem do fork.
- Scanner agendado usa exit-code 0; a promoção de imagem usa script com scan
  bloqueante. São caminhos distintos e precisam de avaliação separada.
- Planos anteriores registram trabalho concluído, mas não substituem execução
  atual de testes nem evidência de publicação real.
- gh e Docker encontrados no ambiente; uv não foi encontrado no PATH da
  inspeção. Disponibilidade do daemon e credenciais ainda não verificadas.

## Objetivos e limites

1. Uma instalação documentada entrega comprovadamente o código deste fork.
2. Um colaborador reproduz os checks obrigatórios a partir de checkout limpo.
3. PRs seguem convenções coerentes com squash merge e versionamento automático.
4. Releases e imagens derivam de código verificado e têm recuperação documentada.
5. Configurações efetivas do GitHub correspondem às políticas documentadas.
6. Mudanças de código resolvem problemas encontrados, preservando contratos MCP,
   segurança SQL, isolamento de bancos e compatibilidade documentada.

Não inclui funcionalidades novas do MCP, reescrita arquitetural, troca de
linguagem, expansão arbitrária de matrizes ou publicação no PyPI. Preservar
licença e atribuição upstream. Não apagar histórico, tags, releases ou dados.
Não transformar esta iniciativa em refatoração estética ou adicionar serviços
pagos, dependências e workflows sem necessidade demonstrada.

## Abordagens consideradas

1. **Validar e corrigir por etapas (escolhida):** diagnóstico, instalação/uso,
   qualidade interna, CI/convenções, publicação e consolidação documental e
   remota. Dá evidência por etapa e limita regressões; exige acompanhar pendências.
2. **CI/CD e GitHub primeiro:** estabiliza entrega mais cedo, mas posterga
   problemas de instalação e experiência de uso.
3. **Reorganização ampla:** uniformiza tudo de uma vez, mas amplia diff, risco
   e custo de revisão sem evidência de necessidade.

## Execução por etapas e critérios de aceitação

### 1. Diagnóstico reproduzível

Inventariar configuração local e remota, branch padrão, permissões, regras,
checks recentes, releases e GHCR. Usar conexão GitHub disponível; complementar
com gh para capacidades ausentes. Registrar achados por impacto, evidência,
correção e estado. Verificar ferramentas sem expor credenciais.

Executar baseline de lockfile, lint, formato, tipos, testes unitários/de release
e build. Identificar pré-requisitos de integração antes de executá-la. Falhas e
checks indisponíveis ficam explícitos; corrigir causas, sem enfraquecer checks
para obter verde. Critério: inventário e resultados atuais rastreáveis.

### 2. Instalação e uso

Conferir instruções Python, Docker e configuração MCP contra artefatos do fork.
Preferir código-fonte e wheel próprios enquanto não houver canal publicado
verificado. Validar CLI e ao menos um fluxo MCP real com PostgreSQL descartável,
incluindo execução permitida, rejeição de operação proibida e resposta de erro.
Critério: instruções reproduzíveis e origem/versionamento identificáveis.

### 3. Organização e qualidade do código

Inspecionar responsabilidades, imports, acoplamento e tratamento de erros nos
caminhos relevantes aos achados. Reutilizar módulos existentes; corrigir apenas
problemas com impacto explicado. Manter testes de regressão para lógica nova ou
defeitos corrigidos; não mover diretórios sem benefício concreto. Critério:
problemas bloqueantes corrigidos com contratos e segurança preservados.

### 4. CI e convenções

Reconciliar nomes reais de checks e regras do GitHub. Validar branches segundo
CONTRIBUTING, título convencional de PR e mensagem final de squash. A proposta
é preservar prefixes e tipos atuais; não exigir que commits intermediários de
uma PR sejam reescritos se o squash já garante a história principal.

Verificar eventos de PR, inclusive edição de título, exceções de bots,
permissões mínimas, entradas não confiáveis, lockfile e isolamento da publicação.
Avaliar scan agendado e bloqueio de release com política coerente e exceções
explícitas, limitadas e justificadas. Garantir disponibilidade do scanner nos
runners de publicação. Adicionar checks apenas para lacunas demonstradas.
Critério: falhas obrigatórias bloqueiam entrega e PR não recebe credenciais de
publicação; a política é reproduzível localmente onde aplicável.

### 5. Release e recuperação

Preservar SemVer e GHCR existentes, condicionados à validação. Conferir baseline
de tags, versão do pacote, changelog/lockfile, commit exato, assets, arquitetura,
scan, smoke, concorrência, promoção de aliases e recuperação de versão antiga
sem rebaixar latest. Primeiro validar com dry-run e testes sem publicação.
Critério: caminho demonstrado até onde as permissões permitirem; publicação
real só recebe estado validado após evidência remota dos artefatos e execução.

### 6. Documentação e GitHub

Atualizar documentação junto de cada mudança e consolidar README em inglês e
pt-BR, contribuição, comandos, segurança, CI/CD, release e troubleshooting.
Distinguir instruções do fork de referências upstream e procedimentos futuros
de comportamentos já disponíveis. Indexar planos anteriores sem apagá-los.

Preparar regras de branch/tag, squash e checks com valores reais antes de
aplicá-las. Considerar o mantenedor único: não ativar exigência de aprovação
impossível de satisfazer pelo próprio autor; ajustar revisões à composição real
dos colaboradores, mantendo checks e proteção contra force push/deleção.
Critério: diferenças entre GitHub e documentação resolvidas ou identificadas
com impedimento e instrução concreta de aplicação.

## Verificação e conclusão

Manter uma matriz curta de critérios com estados verificado, falhou ou pendente
e evidência por comando/run/artefato. Cobrir PG16/17 com HypoPG nos caminhos
obrigatórios; PG18 permanece experimental até haver evidência para promovê-lo.
Verificar instalação do wheel fora da árvore do código e smoke do container,
além dos testes existentes. Selecionar clientes MCP conforme os exemplos
documentados; não alegar compatibilidade universal.

“Concluído” exige baseline obrigatória passando, instalação/uso demonstrados,
documentação coerente e ausência de bloqueantes conhecidos. Falta de acesso ou
de execução externa permanece pendência, nunca aprovação presumida. Entrega
local pode estar pronta para revisão enquanto publicação remota segue pendente.

## Autorização e decisões deixadas ao executor

Esta aprovação autoriza o planejamento. Depois, implementar as correções no
escopo acordado, incluindo testes e documentação, com mudanças revisáveis.
Antes de merge, publicação de release/imagem ou alteração de regras remotas,
apresentar o resultado concreto e seus efeitos para aprovação final, salvo
autorização explícita posterior. Não alterar credenciais nem publicar no PyPI.

Escolhas propostas pelo agente: manter stack e módulos atuais, squash com
título convencional, matriz de PostgreSQL atual e correções pequenas por etapa.
O executor decide ferramentas auxiliares já disponíveis, agrupamento das
correções e testes proporcionais; ampliações funcionais pedem novo escopo.

## Relação com desenhos anteriores

Complementa o desenho de 2026-10-25 sobre CI/CD e governança e o de 2026-10-23
sobre segurança/paginação. Revalida suas alegações e implementação; não reabre
contratos do produto nem considera planos antigos evidência atual de sucesso.
