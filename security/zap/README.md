# OWASP ZAP (DAST)

Testa a aplicação **rodando de verdade** (não o código-fonte). Precisa do perfil de produção local no ar:

```powershell
docker compose -f docker-compose.prod.yml up -d --build
```

## Varredura baseline (passiva + ativa leve, sem login)

O container `waf` (Nginx + ModSecurity + OWASP CRS) só aceita os hosts `127.0.0.1:8443`/`localhost:8443` na porta TLS (allowlist contra Host header injection — ver `docs/security.md`). Como o container do ZAP acessa o `waf` pela rede interna do Docker (nome do serviço, não esse host), é preciso reescrever o cabeçalho `Host` de cada requisição para um valor aceito:

```powershell
docker run --rm --network lustre_decor_application_net -v "${PWD}/security/zap:/zap/wrk:rw" `
  zaproxy/zap-stable zap-baseline.py `
  -t https://waf:8443/ `
  -r zap-report.html `
  -z "-config replacer.full_list(0).description=hostheader -config replacer.full_list(0).enabled=true -config replacer.full_list(0).matchtype=REQ_HEADER -config replacer.full_list(0).matchstr=Host -config replacer.full_list(0).regex=false -config replacer.full_list(0).replacement=127.0.0.1:8443"
```

Aponte direto para a porta 8443 (TLS), não para a 8080: a 8080 só redireciona para `https://$host:8443/...`, e dentro da rede do Docker o `$host` vira só `127.0.0.1` — o container do ZAP tentaria então se conectar em `127.0.0.1:8443` (ele mesmo), não no `waf`, e o redirect falharia com "Connection refused". Isso não afeta o navegador de verdade (que resolve `127.0.0.1` como o próprio host), só o teste rodando de dentro da rede Docker.

O relatório sai em `security/zap/zap-report.html`.

## Varredura autenticada (carrinho e pedidos)

Cobre `/api/v1/cart/` e `/api/v1/orders/`, que exigem sessão. Em vez de ensinar o ZAP a fazer login sozinho (a API espera JSON + CSRF, não um form comum — o método de autenticação nativo do ZAP não encaixa direto), a sessão é pré-autenticada via `curl` e injetada em toda requisição com o mesmo truque de `replacer` já usado pro cabeçalho `Host`: um `replacer.full_list` reescrevendo `Cookie` (sessionid + csrftoken) e outro adicionando `X-CSRFToken`.

Plano próprio em `security/zap/zap-authenticated.yaml` (não é o `zap-baseline.py`/`zap.yaml` de cima): usa um job `requestor` pra visitar as URLs autenticadas direto (o spider não as acha sozinho — são endpoints de API, não tem link nenhum apontando pra eles no HTML da SPA) e roda `activeScan` de verdade (não só passivo como o baseline), então manda payloads de ataque de propósito contra carrinho/pedidos — útil também pra validar o WAF sob varredura automatizada, não só os meus testes manuais de curl.

```powershell
# autentica um usuário de teste e captura sessionid/csrftoken via curl antes (ver histórico)
docker run --rm --network lustre_decor_application_net -v "${PWD}/security/zap:/zap/wrk:rw" `
  zaproxy/zap-stable zap.sh -cmd -autorun /zap/wrk/zap-authenticated.yaml `
  -config "replacer.full_list(0).description=hostheader" -config "replacer.full_list(0).enabled=true" `
  -config "replacer.full_list(0).matchtype=REQ_HEADER" -config "replacer.full_list(0).matchstr=Host" `
  -config "replacer.full_list(0).regex=false" -config "replacer.full_list(0).replacement=127.0.0.1:8443" `
  -config "replacer.full_list(1).description=sessioncookie" -config "replacer.full_list(1).enabled=true" `
  -config "replacer.full_list(1).matchtype=REQ_HEADER" -config "replacer.full_list(1).matchstr=Cookie" `
  -config "replacer.full_list(1).regex=false" -config "replacer.full_list(1).replacement=sessionid=<SESSIONID>; csrftoken=<CSRFTOKEN>" `
  -config "replacer.full_list(2).description=csrfheader" -config "replacer.full_list(2).enabled=true" `
  -config "replacer.full_list(2).matchtype=REQ_HEADER" -config "replacer.full_list(2).matchstr=X-CSRFToken" `
  -config "replacer.full_list(2).regex=false" -config "replacer.full_list(2).replacement=<CSRFTOKEN>"
```

Relatório em `security/zap/zap-report-authenticated.html`.

Admin (`/admin/`) fica de fora: exige MFA (TOTP), e automatizar um app autenticador só pra isso não compensa pro que esse teste entrega — a superfície de autenticação em si (throttling, MFA) já foi validada manualmente.

## Histórico

**2026-09-05** — varredura baseline, sem autenticação, antes do WAF e do TLS existirem.

Dois achados reais corrigidos em `nginx/templates/conf.d/default.conf.template`: `Content-Security-Policy` e `Permissions-Policy` ausentes. A CSP libera `https://cdnjs.cloudflare.com` em `script-src`/`style-src`/`font-src` porque a tela de login do django-two-factor-auth carrega Bootstrap/jQuery de lá; o resto da aplicação (SPA React) usa só `'self'`.

Resultado final: 0 falhas, 64 aprovações, 3 avisos de baixa prioridade sem ação necessária — conteúdo estático cacheável (esperado para JS/CSS/robots.txt), detecção informativa de "aplicação moderna" (SPA), e ausência de `Cross-Origin-Embedder-Policy` (não se aplica: a aplicação não usa recursos que exigem isolamento cross-origin, e habilitá-lo quebraria o carregamento do Bootstrap/jQuery externos na tela de MFA sem ganho de segurança real para este caso).

**2026-09-10** — repetido após adicionar o WAF (ModSecurity + OWASP CRS) e o TLS. Ver `zap-report.html` nesta pasta para o resultado atual.

Resultado: 0 falhas, 62 aprovações, 5 avisos — os mesmos três de antes (agora reclassificados: `Strict-Transport-Security` ausente por causa do certificado autoassinado, já documentado; `Cross-Origin-Embedder-Policy`, mesmo motivo de antes) mais dois novos (`Non-Storable Content`, `Re-examine Cache-control Directives`), causados por um efeito colateral do próprio WAF: o spider do ZAP manda requisições sem `User-Agent`, e o CRS bloqueia isso por padrão (regra de detecção de scanner, `Empty User Agent Header`, pontuação de anomalia 5 — exatamente o limite configurado) com 403 em vez de 404/200. Nenhuma ação necessária: é o WAF fazendo o que devia contra tráfego automatizado sem `User-Agent`; navegador de verdade sempre manda esse cabeçalho.

**2026-09-13** — varredura autenticada (usuária de teste `zapauth`, com item no carrinho e um pedido criado antes de rodar), cobrindo `/api/v1/cart/` e `/api/v1/orders/`. Diferente das anteriores, inclui `activeScan` de verdade (não só passivo) — ZAP manda payloads de ataque contra os endpoints autenticados. Ver `zap-report-authenticated.html`.

Resultado: 0 falhas, 58 aprovações, 3 avisos — os mesmos já conhecidos e documentados (`Strict-Transport-Security`, cache-control em respostas de API, detecção informativa de "aplicação moderna"). Nenhum achado novo específico de carrinho/pedidos: a autorização por objeto e a validação de entrada já cobertas pelos testes de unidade e pelos testes manuais seguram também contra o active scan do ZAP.
