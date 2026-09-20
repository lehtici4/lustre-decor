# Semgrep (SAST)

Analisa o código-fonte (Python, TypeScript, Nginx, Dockerfiles) em busca de padrões inseguros. Não precisa instalar nada — roda via Docker.

## Rodar

```powershell
docker run --rm -v "${PWD}:/src" -w /src returntocorp/semgrep semgrep `
  --config=p/security-audit --config=p/secrets --config=p/python `
  --config=p/owasp-top-ten --config=p/typescript --config=p/react --config=p/dockerfile `
  --exclude=node_modules --exclude=migrations --exclude=dist .
```

## Histórico

Rodado em 2026-09-05. Achado real: `nginx/proxy_params.conf` repassava o cabeçalho `Host` recebido do cliente direto ao backend (`proxy_set_header Host $host;`), sem validar — regra `generic.nginx.security.request-host-used`. Um cliente poderia forjar `Host: backend` para tentar contornar o `ALLOWED_HOSTS` do Django. Corrigido com uma allowlist explícita (`map` + `if`) em `nginx/default.conf`, testada manualmente (host legítimo → 200, host forjado → 400). Duas ocorrências residuais da mesma regra (falsos positivos — o valor já é validado antes de ser usado) foram suprimidas com `# nosemgrep` e comentário justificando.

Situação atual: 0 findings.
