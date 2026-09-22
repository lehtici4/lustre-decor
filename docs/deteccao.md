# Detecção e resposta no host — Fail2ban e Falco

Etapas 2.6 e 3.4/3.5 do plano de deploy. Os dois rodam **no host** (serviço
systemd), não em container: quem vigia o host ou o Docker fica no host, e o
sensor não pode depender do daemon que ele observa.

| Componente | DMZ (192.168.9.34) | Interna (192.168.9.50) | Testes |
| --- | --- | --- | --- |
| Fail2ban | sshd, lustre-auth, lustre-ratelimit, lustre-waf, recidive | sshd, recidive | T08 (+ doc v4 nº 4 e 5) |
| Falco (`modern_ebpf`) | regras oficiais + `lustre_decor_rules.yaml` | idem | T03, T04, T05, T06 |

Arquivos: `infra/fail2ban/`, `infra/falco/`, `infra/scripts/install-fail2ban.sh`,
`infra/scripts/install-falco.sh`.

---

## 1. Implantação

Tirar snapshot das VMs antes (Etapa 5.2). Na raiz do repositório atualizado
(`git pull`), em cada VM:

### DMZ (.34)

```bash
# 1) Fail2ban. FAIL2BAN_IGNOREIP = IP(s) de onde vocês administram a VM
#    (ex.: servidor do Guacamole) — nunca banir o próprio acesso.
sudo FAIL2BAN_IGNOREIP="<ip-do-guacamole>" ./infra/scripts/install-fail2ban.sh dmz

# 2) Recriar o waf: nova imagem (log dedicado + limit_req do MFA) e o bind
#    mount /var/log/lustre-waf
docker compose -f docker-compose.dmz.yml up -d --build
tail -f /var/log/lustre-waf/access.log        # uma linha por requisição

# 3) Falco
sudo ./infra/scripts/install-falco.sh
```

### Interna (.50)

```bash
sudo FAIL2BAN_IGNOREIP="<ip-do-guacamole>" ./infra/scripts/install-fail2ban.sh interna
sudo ./infra/scripts/install-falco.sh

# Backend com MFA: nova imagem (GHCR) + variável MFA_EXEMPT_USERS no stack
docker stack deploy -c docker-stack.interna.yml lustre_decor
docker exec "$(docker ps -qf name=lustre_decor_backend)" python manage.py seed_test_user
```

`seed_test_user` garante a conta `teste@pucparana.com` / `Teste@2026` e apaga
qualquer dispositivo OTP que tenha sobrado nela (a conta fica **sem MFA**).

### Conferência

```bash
sudo fail2ban-client status                       # lista as jails
sudo nft list table inet f2b-table                # sets de IPs banidos
systemctl status falco-modern-bpf --no-pager
sudo tail -n 5 /var/log/falco/falco.json
```

---

## 2. Fail2ban

### Como o log chega até ele

O `waf` grava um access log dedicado em `/var/log/lustre-waf/access.log`
(bind mount do host, formato `lustre_f2b` em
`nginx/templates/conf.d/default.conf.template`):

```
203.0.113.7 [2026-09-22T21:10:01+00:00] 401 upstream=401 "POST /api/v1/auth/login/" rt=0.120 ua="hydra"
```

- O IP é o **primeiro campo** (`$remote_addr`, vem da conexão TCP) e os
  filtros são ancorados no início da linha — nada que o atacante mande na URI
  ou no User-Agent consegue forjar o IP banido. Por isso a jail do WAF **não**
  lê a mensagem do ModSecurity no error log (ela traz o payload antes do
  `client:`).
- `upstream=-` quer dizer que a resposta nasceu no próprio waf: é o que
  diferencia um bloqueio do ModSecurity (403, `upstream=-`) de um 403 do Django
  (`/auth/me/` sem sessão, `upstream=403`).
- Na DMZ o IP real do cliente chega ao Nginx porque o Compose publica a porta
  sem routing mesh (decisão registrada no plano: Swarm só na interna).

### Jails

| Jail | Dispara com | Limite | Ban |
| --- | --- | --- | --- |
| `sshd` | falha de login SSH (journal) | 5 em 10 min | 1 h |
| `lustre-auth` | 401 do Django em `/auth/login/` ou `/auth/mfa/verify/` | 6 em 10 min | 30 min |
| `lustre-ratelimit` | 429 (Nginx `limit_req` ou throttle do DRF) em `/api/v1/auth/` | 5 em 10 min | 1 h |
| `lustre-waf` | 403 gerado pelo ModSecurity/CRS | 10 em 5 min | 1 h |
| `recidive` | IP banido 3× em 1 dia | 3 em 1 dia | 1 semana |

Camadas contra força bruta no login, de dentro para fora: MFA (5 códigos por
desafio) → throttle do DRF (5/min login, 10/min MFA) → `limit_req` do Nginx
(5 r/min login, 10 r/min MFA) → Fail2ban (ban de rede) → recidive.

### Por que a ação usa o hook `forward`

As portas 80/443 da DMZ são publicadas pelo Docker: o tráfego sofre DNAT e
passa pelo hook **FORWARD** do kernel, não pelo INPUT. Um ban comum do
Fail2ban (hook input) **não bloquearia** o acesso ao container. As jails da
aplicação aplicam o ban em dois lugares (tabela nftables `inet f2b-table`):

- `f2b-chain` (hook input) — bloqueia o IP no próprio host (SSH etc.);
- `f2b-forward` (hook forward, prioridade −1) — bloqueia antes das regras do
  Docker, para qualquer container publicado.

Validado em laboratório local: 6 falhas → IP nos dois sets
(`addr-set-lustre-auth` e `addr-set-lustre-auth-fwd`).

### Operação

```bash
sudo fail2ban-client status lustre-auth           # falhas e IPs banidos
sudo fail2ban-client set lustre-auth unbanip <ip> # desbanir
sudo fail2ban-regex /var/log/lustre-waf/access.log /etc/fail2ban/filter.d/lustre-auth.conf
```

**Durante a varredura do ZAP (T07)** o IP do Kali seria banido pela
`lustre-waf` no meio do scan. Para esse teste: `sudo fail2ban-client stop lustre-waf`
antes e `sudo fail2ban-client reload --restart lustre-waf` depois (o Falco
registra a parada — é esperado e vira evidência de T05).

---

## 3. Falco

- Pacote apt oficial, driver `modern_ebpf` (CO-RE: sem kernel headers, DKMS ou
  módulo). O instalador confere kernel ≥ 5.8 e BTF, instala com
  `FALCOCTL_ENABLED=no` (regras não se atualizam sozinhas durante os testes) e
  valida tudo com `falco --dry-run` antes de subir o serviço.
- Saída em JSON, uma linha por alerta, em `/var/log/falco/falco.json` (o
  agente Wazuh lê esse arquivo — etapa 3.5) e também no syslog/journal
  (`journalctl -u falco-modern-bpf`), que sobrevive se o arquivo for apagado.
- Prioridade mínima `notice`.

### Regras do Lustre Decor (`infra/falco/rules.d/lustre_decor_rules.yaml`)

| Regra | Prioridade | Teste | TTP |
| --- | --- | --- | --- |
| Shell iniciado em container da aplicacao | WARNING | doc v4 nº 10 / T03 | T1059, T1609 |
| Acesso ao Docker socket a partir de container | CRITICAL | T03 | T1611 |
| Container privilegiado ou montagem sensivel solicitado no host | CRITICAL | T03 | T1611, T1610 |
| Container privilegiado iniciado | CRITICAL | T03 | T1611 |
| Docker secret lido por processo inesperado | WARNING | T04 | T1552.001 |
| Tentativa de parar sensor de seguranca | CRITICAL | T05 | T1562.001 |
| Log ou evidencia apagado ou renomeado | CRITICAL | T05 | T1070.004 |
| Log de seguranca truncado | CRITICAL | T05 | T1070.004 |
| Conexao de saida para fora das redes privadas a partir de container | WARNING | T06 | T1048, T1567 |
| Ferramenta de rede ou transferencia executada em container | WARNING | T06 | T1105, T1048 |
| Dump do banco lido fora da rotina de backup | NOTICE | T06 | T1074.001 |

As regras oficiais estáveis continuam ativas (ex.: *Terminal shell in
container*, *Clear Log Activities*, *Read sensitive file untrusted*).

Exceções embutidas (para não gerar ruído): entrypoints dos containers (PID 1,
filho do `docker-init`, scripts `*entrypoint*`), healthcheck `pg_isready` do
Postgres e o `curl` do healthcheck da imagem do waf.

---

## 4. Roteiro de disparo controlado (evidências)

Registrar para cada um: pré-condição, comando, horário, resultado e o alerta.
Ver o alerta com `sudo tail -f /var/log/falco/falco.json` em outro terminal.

```bash
B=$(docker ps -qf name=lustre_decor_backend)     # na .50
W=$(docker ps -qf name=lustre_decor-waf)         # na .34

# Shell em container (doc v4 nº 10)
docker exec -it "$B" sh -c 'id; exit'

# T03 — Docker socket (não está montado: o acesso falha E é detectado)
docker exec "$B" python -c "open('/var/run/docker.sock')"
# T03 — pedido de container privilegiado no host (Falco alerta antes do Docker responder)
docker run --rm --privileged alpine true

# T04 — secret lido fora do processo dono
docker exec "$B" cat /run/secrets/django_secret_key > /dev/null

# T05 — evasão (em cenário controlado; reverter logo depois)
sudo systemctl stop fail2ban && sudo systemctl start fail2ban
sudo sh -c ': > /var/log/lustre-waf/access.log'           # só na DMZ

# T06 — tentativa de saída a partir do container (pfSense deve bloquear;
# o Falco registra a TENTATIVA com o resultado em res=)
docker exec "$B" python -c "import socket; socket.create_connection(('1.1.1.1', 443), timeout=3)"
docker exec "$W" curl -m 3 -s https://example.com -o /dev/null
```

### T08 — força bruta no login (a partir do Kali, contra a DMZ)

```bash
for i in $(seq 1 15); do
  curl -sk -o /dev/null -w '%{http_code}\n' https://192.168.9.34/api/v1/auth/login/ \
    -H 'Content-Type: application/json' \
    -d '{"username":"teste@pucparana.com","password":"errada"}'
done
```

Esperado: 401 → 429 (Nginx/DRF) → timeout/recusa (ban). Na DMZ:
`sudo fail2ban-client status lustre-auth` / `lustre-ratelimit` mostra o IP do
Kali banido. Desbanir no fim: `sudo fail2ban-client unban <ip-do-kali>`.

### doc v4 nº 5 — SSH

```bash
# do Kali: senhas erradas repetidas
for i in $(seq 1 6); do ssh -o PreferredAuthentications=password -o ConnectTimeout=3 fake@192.168.9.34; done
sudo fail2ban-client status sshd                  # na DMZ
```

---

## 5. Integração com o Wazuh (etapa 3.2/3.5 — quando o manager subir)

No `ossec.conf` do agente, nos dois hosts:

```xml
<localfile>
  <log_format>json</log_format>
  <location>/var/log/falco/falco.json</location>
</localfile>
<localfile>
  <log_format>syslog</log_format>
  <location>/var/log/fail2ban.log</location>
</localfile>
<!-- só na DMZ -->
<localfile>
  <log_format>syslog</log_format>
  <location>/var/log/lustre-waf/access.log</location>
</localfile>
```

E FIM (`<syscheck>`) em `/var/log/falco`, `/var/log/lustre-waf`,
`/etc/fail2ban`, `/etc/falco` e `/var/backups/lustre-decor` (T11).
