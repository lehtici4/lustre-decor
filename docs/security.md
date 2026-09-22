# Segurança

## Controles aplicados

**Infraestrutura**

- PostgreSQL sem porta publicada e isolado em rede interna (`database_net`, `internal: true`).
- Backend sem porta publicada no host, em ambos os perfis (dev e produção local).
- Frontend/`waf` vinculados somente à interface de loopback (`127.0.0.1`).
- Containers da aplicação executados por usuários sem privilégios (inclui o `waf`, via imagem base do OWASP CRS, que já roda como o usuário `nginx`).
- Linux capabilities removidas dos containers da aplicação (`cap_drop: ALL`).
- Filesystems do backend e do frontend somente para leitura, com `/tmp` em `tmpfs`. O `waf` é a exceção: a própria imagem do ModSecurity/CRS renderiza sua configuração (Nginx e regras do CRS) a cada início, escrevendo em `/etc/nginx` e `/etc/modsecurity.d` — ver "Limites atuais".
- `no-new-privileges` habilitado em todos os serviços.
- Segredos (chave do Django, senhas do banco) montados como arquivos via Docker Secrets, fora do contexto de build e do Git.
- Privilégio mínimo no PostgreSQL: o backend em execução normal usa o papel `lustre_app_runtime`, restrito a `SELECT/INSERT/UPDATE/DELETE` (sem DDL). Migrações usam o papel dono do banco (`lustre_app`), acionado só durante o `migrate` — ver `infra/postgres/init-app-role.sh` e `backend/docker/entrypoint*.sh`.
- TLS terminado no `waf` do perfil de produção local (certificado autoassinado — ver README, "TLS local"); porta 8080 só redireciona para 8443, nenhum dado sensível trafega em HTTP. Imagem base do `waf` com versão pinada (`owasp/modsecurity-crs:4.28.0-nginx-alpine-202608131208`), não uma tag flutuante.
- WAF na frente de toda requisição: Nginx + ModSecurity 3 + OWASP Core Rule Set (imagem `owasp/modsecurity-crs:nginx`, `nginx/Dockerfile`), nível de paranoia 1, em modo de bloqueio ativo (não só detecção). Cobre injeção de SQL, XSS, path traversal e outras classes de ataque genéricas antes da requisição chegar ao backend ou aos estáticos.

**Autenticação e autorização**

- Sessões do Django com cookies `HttpOnly` e `SameSite=Lax`; `Secure` habilitado na configuração de produção.
- CSRF exigido em toda operação autenticada que altera estado (não exigido em cadastro/login, que ocorrem sem sessão prévia).
- RBAC mínimo: cliente vs. staff/admin (`is_staff`).
- Autorização por objeto: um cliente não acessa carrinho ou pedido de outro usuário, mesmo manipulando IDs — tentativas são negadas com 404 e geram log `forbidden_object_access`.
- MFA (TOTP) obrigatório para contas de staff/superusuário no Django Admin (`django-otp` + `django-two-factor-auth`).
- MFA (TOTP) obrigatório também no login da loja para **todas** as contas, com códigos de backup (sem e-mail no laboratório); a sessão só nasce após o segundo fator e a API exige sessão verificada (`IsAuthenticatedWithMfa`). Exceção única: a conta de avaliação `teste@pucparana.com` (`MFA_EXEMPT_USERS`). Ver [Autenticação](authentication.md).
- Throttling de login: 5 tentativas/min por IP no DRF (`ScopedRateThrottle`) **e** rate limiting adicional no `waf` (`limit_req`, defesa em profundidade) no perfil de produção. Verificação do MFA: 10/min em ambos.
- Fail2ban no host da DMZ banindo na camada de rede (hooks input **e** forward do nftables, para alcançar o container publicado) IPs com falhas de login/MFA, insistência após 429, bloqueios repetidos do ModSecurity e SSH — ver [Detecção](deteccao.md).
- Validação de senha via validadores padrão do Django (tamanho mínimo, senha comum, similaridade com dados do usuário, senha só numérica).

**Aplicação**

- CORS, `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` configurados explicitamente por ambiente (os três precisam do endereço real usado pra acessar a aplicação — ver README, "Publicando na rede do laboratório").
- `DEBUG` desativado na configuração-base (só habilitado em `development`).
- Headers de segurança no Django (`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`) e espelhados no `waf` para conteúdo estático.
- ORM do Django em todas as queries (sem SQL bruto).
- Validação de entrada via serializers do DRF em todos os endpoints.
- Regras de negócio isoladas em `apps/core/services/`, separadas das views — reduz a chance de checagens de autorização serem esquecidas ao duplicar lógica.
- Cabeçalho `Host` recebido pelo `waf` validado contra uma allowlist explícita antes de ser repassado ao backend (proteção contra Host header injection/bypass de `ALLOWED_HOSTS`).
- `Content-Security-Policy` e `Permissions-Policy` configurados no `waf` (achados do OWASP ZAP).
- Imagem do backend baseada em Alpine (não Debian) para reduzir a superfície de pacotes de sistema operacional.

**Observabilidade**

- Logs estruturados em JSON no `stdout`, sem senha/token/segredo.
- Eventos de segurança registrados com `user_id` (nunca nome/e-mail) sempre que possível: login (sucesso/falha), logout, cadastro, bloqueio por força bruta, acesso negado por falta de permissão (genérico) e por tentativa de acessar objeto de outro usuário (específico), criação de pedido, alterações administrativas (via Django Admin).
- Auditoria do ModSecurity/CRS também em JSON no `stdout` do `waf`, uma entrada por requisição bloqueada (regra disparada, score de anomalia, IP, URI) — mesmo padrão dos logs do backend.
- Alertas por e-mail (não só log passivo) para os dois eventos de segurança mais acionáveis: bloqueio por força bruta (`request_throttled`) e tentativa de acessar carrinho/pedido de outro usuário (`forbidden_object_access`) — filtro e formatter dedicados em `backend/apps/core/logging.py`, via `AdminEmailHandler` do próprio Django. Vai para o Mailpit local por padrão (sem SMTP de verdade); depende de `DJANGO_ADMINS` estar configurado, senão só o log estruturado acontece (não quebra nada). Os demais eventos (login, logout, cadastro, pedido criado, alterações administrativas) continuam só no log — não são acionáveis o suficiente pra justificar e-mail.
- Endpoint de saúde (`/api/v1/health/`) sem detalhes internos.
- API versionada em `/api/v1/`.

## Limites atuais

O certificado TLS é autoassinado, válido só para `127.0.0.1` — um domínio real precisaria de uma CA confiável (ex.: Let's Encrypt), decisão arquitetural própria fora do escopo deste laboratório. Por isso o HSTS fica desativado por enquanto (`DJANGO_SECURE_HSTS_SECONDS=0`, sem o header no `waf`): com certificado não confiável, HSTS impede o navegador de deixar "prosseguir mesmo assim", travando o próprio acesso local — ativar junto com o certificado de CA.

O container `waf` não roda com filesystem somente leitura, diferente dos outros serviços: a imagem `owasp/modsecurity-crs:nginx` gera sua configuração (vhost do Nginx e regras do CRS, incluindo o nível de paranoia) a cada inicialização, escrevendo em `/etc/nginx` e `/etc/modsecurity.d` — é assim que ela foi desenhada para funcionar, e reimplementar esse passo em build-time só para preservar o filesystem imutável trocaria uma lógica testada do próprio projeto CRS por algo caseiro e frágil, sem ganho de segurança proporcional para um laboratório. O restante do isolamento (usuário sem privilégios, `cap_drop: ALL`, `no-new-privileges`, sem porta publicada além de loopback) continua valendo.

Toda requisição ao `waf` mostra "Host header is a numeric IP address" no log de auditoria do ModSecurity — regra 920350 do CRS, esperada aqui porque o laboratório usa `127.0.0.1` em vez de um domínio real; não bloqueia sozinha (pontuação abaixo do limite de bloqueio). Auditoria centralizada (Wazuh/Falco) permanece fora do escopo do desenvolvimento (ver [Arquitetura](architecture.md) — "Evolução prevista").

Os alertas por e-mail cobrem só eventos detectados **pelo backend** (força bruta, acesso a objeto de outro usuário). Um bloqueio do WAF (ModSecurity/CRS) não gera alerta — só o log JSON de auditoria no `stdout` do `waf`. Ligar isso a um alerta exigiria um componente lendo/encaminhando esse log (ex.: um agente tipo Wazuh/Falco assistindo o `stdout` do container), que é a mesma peça de observabilidade centralizada já deixada fora do escopo.

Docker Compose Secrets não criptografa os arquivos locais que originam os mounts. O diretório `secrets/` deve permanecer fora do controle de versão e protegido pelo sistema operacional.

## Ferramentas de análise (Semgrep, Trivy, ZAP)

Semgrep (SAST) e Trivy (SCA/imagens) já foram rodados contra o código — ver `security/semgrep/README.md` e `security/trivy/README.md` para os comandos e o histórico de achados corrigidos (Host header injection no Nginx, CVEs no `djangorestframework`, superfície de pacotes de SO reduzida trocando a imagem do backend de Debian para Alpine, e o mesmo tipo de achado na imagem do `waf`). OWASP ZAP (DAST) fica documentado em `security/zap/README.md` para rodar contra o perfil de produção local — inclui testes manuais confirmando que o WAF bloqueia SQLi, path traversal e XSS de verdade (403 + registro no CRS), não só que os headers estão presentes. Falco (driver `modern_ebpf`, no host) e Fail2ban estão em `infra/falco` e `infra/fail2ban`, com instaladores e roteiro de disparo controlado em [Detecção](deteccao.md). O Wazuh segue pendente (etapa 3.1/3.2 do plano) e passa a ler `/var/log/falco/falco.json` e os logs do Fail2ban/waf.
