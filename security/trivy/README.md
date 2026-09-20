# Trivy (SCA + imagens)

Analisa dependências (Python/npm) e as imagens Docker construídas em busca de CVEs conhecidas. Roda via Docker.

## Dependências (SCA)

O analisador de `pip` do Trivy só reconhece arquivos chamados exatamente `requirements.txt` — os deste projeto ficam em `backend/requirements/base.txt` e `development.txt`. Para escanear, copie para um nome reconhecido antes de rodar:

```powershell
Copy-Item backend/requirements/base.txt /tmp/requirements.txt
docker run --rm -v "/tmp:/src" aquasec/trivy fs --severity LOW,MEDIUM,HIGH,CRITICAL /src
```

O frontend é detectado automaticamente pelo nome padrão `package-lock.json`:

```powershell
docker run --rm -v "${PWD}:/src" aquasec/trivy fs --severity HIGH,CRITICAL --scanners vuln /src
```

## Imagens

Requer as imagens já construídas (`docker compose build` / `docker compose -f docker-compose.prod.yml build`).

```powershell
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL lustre_decor-backend-prod
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL lustre_decor-waf
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL postgres:17.6-alpine3.22
```

## Histórico

Rodado em 2026-09-05. Dois achados reais:

1. **`djangorestframework==3.17.1`** com duas CVEs corrigidas na versão seguinte (DoS via corpo de requisição enorme; vazamento de informação via `AdminRenderer`). Corrigido: `djangorestframework==3.17.2`.
2. **Imagem do backend em Debian (`python:3.13.7-slim-bookworm`)**: 87 vulnerabilidades HIGH/CRITICAL de pacotes de SO não usados pela aplicação (perl, util-linux, openssl). Migrado para `python:3.13.7-alpine3.22` — `psycopg[binary]` não tem wheel para musl/Alpine, então o driver passou a ser `psycopg[c]` (compila contra a `libpq` instalada na imagem). Resultado: 0 HIGH/CRITICAL (`apk upgrade` no build também resolveu os poucos remanescentes que já tinham correção publicada, só não estavam na imagem-base).

**2026-09-10** — imagem `lustre_decor-waf` (Nginx + ModSecurity + OWASP CRS, base `owasp/modsecurity-crs:4.28.0-nginx-alpine-202608131208`): 13 HIGH em pacotes de SO (openssl, libexpat, util-linux) com correção já publicada mas ainda não incorporada à imagem-base — mesmo padrão do achado acima. Resolvido do mesmo jeito: `apk upgrade --no-cache` no `nginx/Dockerfile` (como root, devolvendo para o usuário `nginx` sem privilégios logo em seguida). Resultado: 0 HIGH/CRITICAL.

Situação atual: backend, WAF (Nginx + ModSecurity + CRS) e Postgres sem vulnerabilidades HIGH/CRITICAL conhecidas.
