# Autenticação e Zero Trust

## Sprint 1: Django Nativo (Atual)

- Backend: Django com django-otp (TOTP) + django-two-factor-auth
- Login: Formulário padrão → Two-Factor
- Fluxo: Usuário autentica direto na aplicação, sessão em DB
- Variáveis: ENABLE_OIDC=false (padrão)

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
