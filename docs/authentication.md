# Autenticação e Zero Trust

## Sprint 1: Django Nativo (Atual)

- Backend: Django com django-otp (TOTP) + django-two-factor-auth
- Login: Formulário padrão → Two-Factor
- Fluxo: Usuário autentica direto na aplicação, sessão em DB
- Variáveis: ENABLE_OIDC=false (padrão)

### MFA obrigatório no login da loja (TOTP)

Toda conta precisa de segundo fator para entrar na loja (SPA), não só o staff
no Django Admin. Como o laboratório não tem serviço de e-mail, o fator é um
**app autenticador** (TOTP, RFC 6238) e a recuperação é por **8 códigos de
backup** de uso único, mostrados uma única vez na ativação.

Fluxo (a sessão só é criada **depois** do segundo fator):

1. `POST /api/v1/auth/login/` com usuário e senha corretos:
   - conta isenta → sessão criada, responde o usuário (como antes);
   - conta com TOTP → `{"mfa_required": true, "stage": "verify"}`;
   - conta nova (sem TOTP) → `{"mfa_required": true, "stage": "setup", "qr_code", "secret", "otpauth_uri"}`.
     Um segredo novo é gerado a cada tentativa até a confirmação.
2. `POST /api/v1/auth/mfa/verify/` com `{"token": "123456"}` (ou um código de
   backup) → cria a sessão já verificada. Na ativação, a resposta traz
   `backup_codes`.

Proteções: desafio pendente expira em 5 min (`MFA_PENDING_TTL`) e é descartado
após 5 códigos errados (`MFA_MAX_ATTEMPTS`) — volta para a senha; throttle de
10/min no DRF e `limit_req` 10 r/min no Nginx para `/auth/mfa/verify/`;
throttling por dispositivo do próprio django-otp (espera crescente após erro);
falhas geram log `mfa_failed` e 401 contabilizado pelo Fail2ban (`lustre-auth`).

Defesa em profundidade: a permissão padrão da API é
`IsAuthenticatedWithMfa` (`apps/accounts/permissions.py`) — uma sessão criada
só com senha por outro caminho (ex.: `/account/login/` do two_factor) recebe
403 em toda a API.

**Conta de avaliação sem MFA.** `MFA_EXEMPT_USERS` (nomes de usuário,
separados por vírgula; padrão `teste@pucparana.com`) entra só com senha. A
isenção compara o **nome de usuário**, não o e-mail (campo livre no cadastro).
`python manage.py seed_test_user` recria a conta e remove qualquer
dispositivo OTP dela. Para uma demonstração pública, desligar com
`MFA_EXEMPT_USERS=""` no stack (ou trocar a senha da conta).

Limite conhecido: o primeiro cadastro do TOTP é "trust on first use" — quem
souber a senha de uma conta que **ainda não** ativou o MFA consegue ativá-lo
no lugar do dono. Depois de ativado, a senha sozinha não basta. Sem e-mail
não há canal fora de banda para amarrar a ativação ao dono da conta.

Recuperação sem e-mail: código de backup; se o usuário perdeu app **e**
códigos, um administrador remove os dispositivos dele no Django Admin
(*OTP_TOTP › TOTP devices* e *OTP_Static › Static devices*) e o próximo login
volta para a tela de ativação.

## Sprint 2: OIDC + Keycloak + Zero Trust (Futuro)

- Backend: Keycloak como Policy Decision Point (PDP)
- OIDC Middleware: mozilla-django-oidc autentica e mapeia roles → Groups
- Forward-Auth: Nginx usa auth_request com Authelia (PEP)
- Fluxo: Usuário → Keycloak (OIDC) → Token JWT → Nginx → Serviços
- Variáveis: ENABLE_OIDC=true, OIDC_RP_CLIENT_ID, OIDC_RP_CLIENT_SECRET, endpoints

### Ativar (sem mudança de código):
1. Deploy do Keycloak
2. Configurar cliente OIDC
3. ENABLE_OIDC=true no .env
4. Descomentar auth_request no Nginx
5. Deploy do Authelia
6. docker service update no backend
7. Pronto — Zero Trust ativo
