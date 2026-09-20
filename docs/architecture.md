# Arquitetura

Dois perfis de execução convivem no mesmo repositório: **desenvolvimento** (`docker-compose.yml`, hot-reload via Vite) e **produção local** (`docker-compose.prod.yml`, Nginx + ModSecurity/OWASP CRS + Gunicorn). Ambos compartilham a mesma segmentação de rede e o mesmo volume de dados do PostgreSQL.

## Fluxo — desenvolvimento

```text
Navegador -> 127.0.0.1:5173 -> frontend:5173 (Vite dev server)
                                  |
                                  | /api, /admin, /account, /static (proxy interno)
                                  v
                               backend:8000 (runserver) -> postgres:5432
```

Só o frontend é publicado no host. O backend participa de duas redes e atua como a única ponte lógica entre a interface e os dados.

## Fluxo — produção local

```text
Navegador -> 127.0.0.1:8080 -> waf:8080 (redireciona para HTTPS)
Navegador -> 127.0.0.1:8443 -> waf:8443 TLS + ModSecurity/OWASP CRS (estáticos do React + proxy reverso)
                                  |
                                  | /api, /admin, /account -> proxy_pass (HTTP interno + X-Forwarded-Proto)
                                  | /static -> arquivos coletados (volume compartilhado)
                                  v
                               backend:8000 (Gunicorn) -> postgres:5432
```

O container `waf` (imagem `owasp/modsecurity-crs:nginx`, Nginx com o módulo ModSecurity 3 e o OWASP Core Rule Set já compilados) termina TLS (certificado autoassinado — ver README, "TLS local"), serve os artefatos estáticos do build do React (`npm run build`) e faz proxy dos estáticos do Django (`/static/` — admin, two-factor) pro backend, que os serve via WhiteNoise — e inspeciona toda requisição contra o CRS antes dela chegar em qualquer location. A porta 8080 só existe para redirecionar para 8443; nenhum dado sensível trafega nela. Só o `waf` é publicado no host; backend e PostgreSQL permanecem inacessíveis de fora da rede Docker em ambos os perfis. Entre `waf` e backend o tráfego continua HTTP simples — está dentro da rede Docker isolada (`application_net`), não exposta ao host.

## Componentes

- **Frontend:** apresentação e consumo da API. Não contém credenciais do banco.
- **waf — Nginx + ModSecurity + OWASP CRS (perfil produção):** um único container, imagem própria (`nginx/Dockerfile`) construída sobre `owasp/modsecurity-crs:nginx`, que já embute o frontend compilado (sem bind mount). Termina TLS, serve os estáticos do frontend, encaminha `/api`, `/admin`, `/account` e `/static` ao backend, aplica rate limiting adicional no login (defesa em profundidade, complementar ao throttling do DRF) e passa toda requisição pelo OWASP Core Rule Set (SQLi, XSS, path traversal etc. — nível de paranoia 1, bloqueio ativo). Roda como o usuário sem privilégios já definido pela imagem base.
- **Backend:** fronteira de confiança para autenticação, autorização, validação e regras de negócio. Regras de negócio isoladas em `apps/core/services/`, separadas das views. Sabe que está atrás de um proxy que termina TLS via `SECURE_PROXY_SSL_HEADER`, o que também mantém `SECURE_SSL_REDIRECT` coerente sem loop de redirecionamento.
- **PostgreSQL:** persistência privada, acessível somente pelo backend.
- **Mailpit:** captura os e-mails de alerta de segurança que o backend envia (bloqueio por força bruta, acesso a objeto de outro usuário — ver `docs/security.md`). Não é um serviço de e-mail de verdade, só um sumidouro local com interface web para inspecionar o que foi enviado; existe nos dois perfis.

## Redes e portas

| Serviço | Rede | Porta interna | Porta no host |
|---|---|---:|---:|
| frontend (dev) | `application_net` | 5173 | `127.0.0.1:5173` |
| waf — redirecionamento (produção local) | `application_net` | 8080 | `127.0.0.1:8080` |
| waf — TLS + ModSecurity/CRS (produção local) | `application_net` | 8443 | `127.0.0.1:8443` |
| backend | `application_net`, `database_net` | 8000 | nenhuma |
| postgres | `database_net` | 5432 | nenhuma |
| mailpit (SMTP) | `application_net` | 1025 | nenhuma |
| mailpit (interface web) | `application_net` | 8025 | `127.0.0.1:8025` |

## Persistência

`postgres_data` é o único volume persistente de dados de negócio, compartilhado entre os dois perfis (mesmo `COMPOSE_PROJECT_NAME`). `frontend_node_modules` impede que o bind mount do perfil de desenvolvimento substitua as dependências instaladas na imagem. Os arquivos coletados pelo `collectstatic` (perfil de produção) ficam num `tmpfs` local ao container do backend — regenerados a cada início, servidos via WhiteNoise, sem volume compartilhado com o `waf`.

## Evolução prevista

TLS já é terminado no `waf` do perfil de produção local, mas com certificado autoassinado — adequado só para `127.0.0.1`. Um certificado de CA confiável (ex.: Let's Encrypt) para um domínio real e os serviços de observabilidade (Wazuh, Falco, Prometheus/Grafana) descritos na especificação do laboratório continuam fora do escopo do desenvolvimento e exigem decisão arquitetural própria antes da implementação.
