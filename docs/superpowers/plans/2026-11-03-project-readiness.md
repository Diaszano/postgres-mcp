# Project Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validar e corrigir instalação, manutenção e entrega do fork Diaszano/postgres-mcp com evidências reproduzíveis.

**Architecture:** Preservar módulos e automações existentes. Executar etapas sequenciais, corrigindo causas demonstradas e atualizando documentação junto das mudanças. Não criar novas APIs de aplicação para organizar o repositório.

**Tech Stack:** Python >=3.12, uv, pytest, Ruff, Pyright, PostgreSQL/HypoPG, Docker, GitHub Actions, Python Semantic Release e GHCR.

**Spec:** [desenho aprovado](../specs/2026-11-03-project-readiness-design.md).

## Global Constraints

- Não inclui funcionalidades novas do MCP, reescrita arquitetural, troca de linguagem, expansão arbitrária de matrizes ou publicação no PyPI.
- Preservar licença e atribuição upstream. Não apagar histórico, tags, releases ou dados.
- Cobrir PG16/17 com HypoPG nos caminhos obrigatórios; PG18 permanece experimental até haver evidência para promovê-lo.
- PR não recebe credenciais de publicação; não alterar credenciais.
- Antes de merge, publicação de release/imagem ou alteração de regras remotas, apresentar resultado concreto e efeitos para aprovação final, salvo autorização explícita posterior.
- Falta de acesso ou execução externa permanece pendência, nunca aprovação presumida.
- Não introduzir dependências ou workflows sem lacuna demonstrada; manter contratos MCP, segurança SQL e isolamento de bancos.

## Review Focus

1. PR de fork, título editado e rerun por outro ator: convenções devem continuar válidas sem conceder escrita; tarefa 4.
2. Falha real do versionador: execução deve falhar, sem se passar por ausência de nova versão; tarefa 5.
3. Recuperação de release antiga: não mover latest nem aliases de versões mais recentes para trás; tarefa 6.
4. Instalação fora do checkout: executar código do wheel do fork, sem imports acidentais da árvore; tarefa 2.
5. Mantenedor único e release automatizado: regras devem proteger sem exigir aprovação do próprio autor ou bypass fictício; tarefa 7.

## Mapa de arquivos e sequência

| Tarefa | Arquivos sob responsabilidade | Entrega |
|---|---|---|
| 1 | `docs/project-readiness.md` (novo) | Diagnóstico e matriz de evidências |
| 2 | `README.md`, `README.pt-BR.md`, `tests/README.md`, `tests/README.pt-BR.md`, `tests/unit/test_documentation_contract.py`, `tests/release/test_smoke.py`, `Dockerfile`, `docker-entrypoint.sh` se necessário | Instalação e uso demonstrados |
| 3 | Módulos e testes existentes identificados no diagnóstico; `justfile`, `CONTRIBUTING.md` | Correções internas delimitadas e comandos locais |
| 4 | `.github/workflows/ci.yml`, `.github/dependabot.yml`, `scripts/ci/check_pr_metadata.py`, `tests/release/test_pr_metadata.py`, `tests/release/test_ci_workflow.py`, `tests/release/test_ci_release_gate.py`, `CONTRIBUTING.md` | CI e convenções coerentes |
| 5 | `.github/workflows/release.yml`, `.github/workflows/security.yml`, `scripts/release/build.sh`, `pyproject.toml`, `tests/release/test_release_workflow.py`, `tests/release/test_release_build.py`, `tests/release/test_security_failures.py` | Release bloqueante e rastreável |
| 6 | `.github/workflows/retry-publish.yml`, `scripts/ci/promote_image.sh`, `scripts/ci/scan_image.sh`, `tests/release/test_image_promotion.py`, `tests/release/test_publish_recovery.py`, `tests/release/test_image_scan.py` | Promoção e recuperação seguras |
| 7 | `docs/github-settings.md`, `docs/ci-cd.md`, `docs/release-checklist.md`, `SECURITY.md`, `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`, `docs/superpowers/plans/README.md`, `tests/release/test_github_settings.py`, `tests/release/test_release_docs.py` | Documentação e proposta de governança |
| 8 | `docs/project-readiness.md` | Verificação final e entrega revisável |

Os três blocos de entrega são uso/qualidade (1–3), automação (4–6) e governança/fechamento (7–8). Cada tarefa pode ser revisada e mantida independentemente. Não refazer os planos de outubro: usar seus testes e implementação como baseline.

### Task 1: Diagnóstico local e remoto

**Interfaces:** Consome checkout e conexão GitHub; produz `docs/project-readiness.md` com critério, estado, evidência e próxima ação.

- [ ] Usar `superpowers:using-git-worktrees` antes da implementação; preservar a branch documental e mudanças existentes. Ler instruções locais aplicáveis e registrar SHA inicial.
- [ ] Verificar Python, uv, Docker e autenticação sem imprimir tokens. Se uv não estiver disponível, verificar instalação existente fora do PATH; instalar ferramenta somente se necessário, pela distribuição oficial e sem mudar dependências do projeto.
- [ ] Consultar metadata, branch padrão, colaboradores relevantes, checks recentes, releases, regras, opções de merge e GHCR via plugin GitHub; usar gh apenas onde o plugin não cobrir. Registrar acesso negado como pendência, sem concluir que regras inexistem.
- [ ] Executar separadamente `uv lock --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run pytest -q tests/unit tests/release` e `uv build`. Registrar códigos de saída e resumo, inclusive skips relevantes.
- [ ] Criar relatório com achados priorizados por segurança, instalação, entrega e manutenção. Inspecionar falhas segundo `superpowers:systematic-debugging`; delimitar arquivos/callers antes de qualquer correção.
- [ ] Commit: `docs: record project readiness baseline`. Não registrar segredos ou logs com URIs reais.

### Task 2: Instalação e fluxo MCP do fork

**Interfaces:** Consome wheel de `uv build` e configuração existente; produz comandos documentados de instalação do fork. Nenhuma nova assinatura pública.

- [ ] Ler CLI, Dockerfile, entrypoint real e fixtures de integração para identificar um fluxo descartável já suportado; confirmar o caminho do entrypoint antes de editá-lo.
- [ ] Se houver erro de comportamento, adicionar regressão no teste proprietário e demonstrar falha antes da correção. Para documentação simples, corrigir instruções e usar verificação manual reproduzível, sem teste de strings decorativas.
- [ ] Criar venv temporário fora do checkout, instalar o wheel pelo caminho absoluto e executar `postgres-mcp --help` nesse diretório. Verificar com `importlib.metadata.version('postgres-mcp')` e `postgres_mcp.__file__` que a versão é a do build e o módulo está no venv. Registrar comando e resultado em `docs/project-readiness.md`.
- [ ] Construir imagem local sem push; executar help e o cliente MCP existente contra PostgreSQL descartável. Conferir descoberta das ferramentas, SELECT permitido, operação de escrita rejeitada em modo restrito e erro estruturado sem credenciais. Usar testes wire existentes para asserções, sem novo cliente customizado.
- [ ] Corrigir README inglês/pt-BR para diferenciar upstream de fork e usar somente canal verificado. Não apresentar `pip install postgres-mcp` como instalação do fork sem provar sua origem.
- [ ] Rodar `uv run pytest -q tests/unit/test_documentation_contract.py tests/release/test_smoke.py` e os testes de integração MCP/segurança envolvidos. Commit: `docs: document verified fork installation` ou `fix: ...` se houver correção funcional.

### Task 3: Qualidade interna e comandos locais

**Interfaces:** Consome achados da tarefa 1; mantém assinaturas e retornos públicos atuais.

- [ ] Para cada defeito bloqueante, registrar módulo, callers e teste proprietário antes de editar. Se não houver defeito demonstrado, registrar que nenhuma refatoração é necessária e seguir.
- [ ] Adicionar o menor teste que reproduz cada defeito; executar o teste e confirmar a falha pela causa esperada.
- [ ] Corrigir a causa no módulo compartilhado. Preservar validação, cancelamento, limpeza de recursos e mensagens de erro seguras; evitar movimentações cosméticas.
- [ ] Rodar o teste proprietário e suíte conectada. Falhas de baseline não relacionadas ficam identificadas, sem ampliar escopo silenciosamente.
- [ ] Reconciliar `justfile` e CONTRIBUTING com os comandos realmente usados na CI, incluindo testes de release; verificar `just --list` se disponível e `uv run pytest -q tests/unit/test_developer_commands.py`.
- [ ] Commit por correção: `fix(<modulo>): <causa corrigida>`; para comandos, `chore: align local verification commands`.

### Task 4: Convenções, eventos e permissões da CI

**Interfaces:** Preservar `validate_pr(title: str, head_ref: str, actor: str) -> list[str]`; saída vazia indica válido. CI consome resultado via código de saída. Manter convenções documentadas, reconciliando eventual diferença de `revert/`.

- [ ] Nos testes de metadata, cobrir título válido/inválido, breaking change, branch humana e branch Dependabot; usar identidade do autor da PR para autorização de branch bot, não o ator que disparou edição/rerun. Confirmar o comportamento esperado antes de alterar callers.
- [ ] Adicionar `test_ci_revalidates_edited_pr_title` em `test_ci_workflow.py`: eventos incluem opened, synchronize, reopened e edited; verificar valores extraídos do YAML com BaseLoader. Confirmar falha atual.
- [ ] Adicionar `test_fork_pr_has_no_release_permissions` em `test_ci_release_gate.py`: publicação só em push de main, jobs de PR sem escrita e entradas via env. Examinar permissões do caller/reusable: permitir escrita somente no job de entrega e somente fora de PR.
- [ ] Corrigir eventos/env/permissões mínimos. Manter gate obrigatório PG16/17 e PG18 experimental. Conferir versão de uv capaz de ler o lockfile e optar por pin coerente; conferir documentação oficial atual antes de alterar versões/actions.
- [ ] Rodar `uv run pytest -q tests/release/test_pr_metadata.py tests/release/test_ci_workflow.py tests/release/test_ci_release_gate.py tests/release/test_dependabot_config.py tests/release/test_action_security.py`.
- [ ] Atualizar CONTRIBUTING com título convencional, squash e comandos verificados. Commit: `ci: enforce pull request conventions consistently`.

### Task 5: Versionamento e falhas de release

**Interfaces:** Preservar outputs `released`, `tag`, `release_sha`, `version` do reusable; `released=false` significa execução bem-sucedida sem incremento, nunca erro mascarado.

- [ ] Ler testes de bootstrap/build e documentação oficial da versão fixada do Python Semantic Release. Verificar semântica de `version --print`, modo noop, geração de commit/tag e publish antes de escolher comandos.
- [ ] Adicionar `test_versioning_failure_stops_release` em `test_security_failures.py`: executar trecho/script de versionamento com ferramenta substituída que retorna erro; exigir saída não zero e nenhuma chamada de publish. Usar padrão de subprocess/fakes já existente; evitar framework novo.
- [ ] Cobrir também execução bem-sucedida sem versão nova e execução com incremento que produz outputs consistentes. Demonstrar falha dos casos afetados antes da correção.
- [ ] Remover supressão incondicional por `|| true`, corrigir sequência de versionamento/publicação conforme CLI oficial, validar baseline e garantir versão/lock/changelog no commit esperado. Não criar helpers se o workflow existente resolver claramente.
- [ ] Verificar que wheel/sdist são do commit/tag divulgado e metadados batem; executar `uv run pytest -q tests/release/test_release_workflow.py tests/release/test_release_bootstrap.py tests/release/test_release_build.py tests/release/test_release_metadata.py tests/release/test_security_failures.py`.
- [ ] Tornar scan agendado bloqueante para HIGH/CRITICAL, sem suprimir falha operacional. Testar configuração em `test_security_failures.py`; exceções, se indispensáveis, devem ter justificativa, escopo e validade, sem ignore global.
- [ ] Usar dry-run/noop sem tokens de escrita para verificar decisões de versão. Commit: `fix(release): propagate versioning and security failures`.

### Task 6: Scan, promoção e recuperação

**Interfaces:** Preservar `scan_image.sh IMAGE@sha256:DIGEST` e `promote_image.sh repository digest tag` salvo necessidade demonstrada de parâmetro de política; falha retorna não zero. Recuperação continua recebendo tag existente.

- [ ] Substituir testes que apenas recalculam regex/aliases por execução real do script com docker/trivy falsos em PATH, gravando argv em arquivo temporário.
- [ ] Adicionar casos de digest/tag inválido, scanner ausente, falha de scan amd64/arm64: exigir saída não zero e zero chamadas de promoção; no sucesso verificar digest exato e aliases efetivamente enviados.
- [ ] Testar recuperação de tag antiga contra versão estável mais nova: permitir reparar somente aliases da versão solicitada sem alterar latest, major ou minor que já apontem para versão posterior; garantir rerun idempotente e erro explícito se não for possível determinar estado necessário. Definir comparação SemVer com utilitário existente, sem comparação lexicográfica.
- [ ] Implementar a menor política que cumpra os testes; não sobrescrever tag imutável com digest diferente. Verificar concorrência entre recuperação e entrega normal para impedir corrida em aliases.
- [ ] Instalar scanner fixado e verificável nos jobs que o usam; conferir fonte oficial e permissões. Usar commit exato da release nos passos que consomem scripts/artefatos, validar input antes de interpolação shell e testar tentativa de input malicioso sem execução.
- [ ] Executar `uv run pytest -q tests/release/test_image_promotion.py tests/release/test_publish_recovery.py tests/release/test_image_scan.py tests/release/test_ghcr_manifest.py tests/release/test_cd_smoke.py tests/release/test_action_security.py` e `bash -n` em cada script alterado.
- [ ] Commit: `fix(release): make image promotion and recovery safe`. Documentar recuperação e rollback por digest sem publicar.

### Task 7: Governança aplicável e documentação

**Interfaces:** Consome nomes efetivos de checks e permissões remotas da tarefa 1; produz proposta concreta, ainda não aplicada, em `docs/github-settings.md`.

- [ ] Documentar checks pelo nome real exibido no GitHub, incluindo ambas integrações obrigatórias. Não exigir apenas identificadores YAML se não corresponderem ao contexto de status real.
- [ ] Preparar ajustes de squash/title, deleção de branches após merge, proteção de main/tags e acesso GHCR. Remover afirmação de bypass por mensagem de commit se GitHub não a suportar; validar solução suportada para release bot sem criar credencial.
- [ ] Cobrir mantenedor único em `test_github_settings.py`: proposta não depende de autoaprovação; registrar evidência remota ou payload de revisão para regras. Não criar teste que apenas afirme um número de reviewers sem considerar colaboradores reais.
- [ ] Reconciliar SECURITY, CODEOWNERS, templates, ci-cd e checklist com as tarefas 2–6. Substituir digest ilustrativo que pareça artefato real por placeholder explicitamente rotulado. Atualizar índices de planos para separar histórico de evidência atual.
- [ ] Executar `uv run pytest -q tests/release/test_github_settings.py tests/release/test_release_docs.py tests/release/test_repository_governance.py tests/release/test_repository_conventions.py tests/unit/test_documentation_contract.py`.
- [ ] Commit: `docs: align repository governance with verified delivery`. Apresentar diff/payload e impacto das configurações remotas para aprovação antes da aplicação.

### Task 8: Verificação final e entrega

**Interfaces:** Consome todas as mudanças; produz matriz final, commits revisáveis e lista explícita de ações externas pendentes.

- [ ] Invocar `superpowers:verification-before-completion`. Reexecutar lock, lint, formato, tipos, testes unitários/de release e build contra a árvore final. Resultados anteriores não substituem a verificação final de arquivos alterados depois.
- [ ] Construir imagens HypoPG com `bash scripts/ci/build_hypopg_image.sh 16` e depois 17; executar `MULTIDB_PG_IMAGE=postgres-hypopg:16 uv run pytest -q tests/integration` e equivalente 17. Confirmar que testes obrigatórios não foram apenas skipped; se infraestrutura impedir, registrar impedimento.
- [ ] Repetir smoke do wheel/container se build/runtime mudou desde tarefa 2. Testes de performance existentes só são obrigatórios se uma correção afetou memória, timeout ou concorrência; não iniciar benchmark sem hipótese.
- [ ] Fazer revisão do diff conectado aos callers, segurança e comportamento; seguir o método de execução escolhido para revisão independente. Corrigir bloqueantes e repetir checks afetados.
- [ ] Atualizar matriz com comandos, SHA, resultados e links remotos disponíveis. Separar validado localmente, validado no GitHub e pendente de autorização/acesso. Commit: `docs: record readiness verification results`.
- [ ] Entregar resumo das correções e riscos, branch/commits e proposta concreta de PR/merge/configuração/publicação. Só executar ações externas sujeitas à aprovação após autorização explícita. Evidência remota é necessária para declarar CD validada ponta a ponta.

## Autorrevisão do plano

- Cobertura: etapas 1–6 do desenho mapeadas às tarefas 1–8; exclusões e aprovações preservadas.
- Interfaces: APIs MCP inalteradas; validate_pr, scripts e outputs existentes preservados ou migração mínima coberta pelos callers.
- Review Focus: cinco condições mapeadas aos testes/verificações das tarefas 2, 4, 5, 6 e 7.
- Escopo adaptativo: defeitos internos desconhecidos exigem reprodução e delimitação antes da correção; nenhuma refatoração genérica autorizada pelo plano.
- O plano não afirma baseline verde nem acesso remoto validado. Nenhuma implementação de produto foi feita durante sua redação.
