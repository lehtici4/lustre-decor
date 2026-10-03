# Wazuh (SIEM)

Manager, indexer e dashboard em container na VM interna (`192.168.9.50`), num stack Swarm próprio (`docker-stack.wazuh.yml`, stack `wazuh`), separado da aplicação. Agentes no **host** das duas VMs (fora de container — quem vigia o host ou o Docker fica no host, mesma regra do Falco).

```text
 DMZ .34 (host)                                  Interna .50
 ┌────────────────────────┐                      ┌──────────────────────────────────────────┐
 │ wazuh-agent            │  TCP 1514 (eventos)  │ host: wazuh-agent ───┐                    │
 │  - journald (sshd, AD) │  TCP 1515 (registro, │  - journald          │ 1514/1515          │
 │  - falco.json          │   com senha)         │    (lustre-backend,  ▼                    │
 │  - fail2ban.log        │ ───── pfSense ─────▶ │     lustre-postgres) [manager]──TLS──▶[indexer]
 │  - lustre-waf/access   │                      │  - falco.json            ▲                 │
 └────────────────────────┘                      │  - fail2ban.log          │ API 55000       │
                                                 │                      [dashboard] :443      │
                                                 └──────────────────────────────────────────┘
```

Versão: **4.14.7** (última estável do `wazuh-docker`). Agente e manager na mesma versão; o agente fica com `apt-mark hold` (agente mais novo que o manager não é suportado).

## O que chega ao Wazuh

| Fonte | Como é coletada | Regras (`infra/wazuh/manager/local_rules.xml`) |
|---|---|---|
| Backend Django (log JSON) | driver `journald` do Docker, tag `lustre-backend`; o agente do host já coleta o journald inteiro | 1001xx: falha de login, força bruta por origem, MFA inválido repetido, throttling, acesso a objeto de outro usuário (IDOR) e enumeração, admin_action, **conexão recusada pelo mTLS** |
| Postgres | driver `journald`, tag `lustre-postgres` | 10013x: `pg_hba.conf rejects` (conexão sem TLS), falha de senha, força bruta |
| Falco | `/var/log/falco/falco.json` (`log_format json`) | 1002xx: severidade do Falco + regras próprias com ATT&CK (shell em container, docker.sock, secret lido, evasão, exfiltração) |
| waf (DMZ) | `/var/log/lustre-waf/access.log` | 1003xx: bloqueio do ModSecurity, rajada de bloqueios, `limit_req`, 502 (backend/mTLS) |
| Fail2ban | `/var/log/fail2ban.log` | 1004xx: ban, unban, reincidente (`recidive`) |
| SSH, sudo, login AD (sssd) | journald (padrão do pacote) | regras nativas do Wazuh |
| FIM | `<syscheck>` do agente | `/etc/fail2ban`, `/etc/falco`, `/etc/docker`, `secrets/` do repo em tempo real (sem enviar conteúdo); logs dos sensores e dumps agendados |

O `origin` dos eventos do backend é o IP real do cliente (último item do `X-Forwarded-For`, que o waf anexa) — ver `backend/apps/core/net.py`.

## Segurança do próprio Wazuh

- **TLS em todos os saltos internos**: Filebeat do manager → indexer com verificação completa (`FILEBEAT_SSL_VERIFICATION_MODE=full`); dashboard → indexer com `verificationMode: full`; dashboard em HTTPS. Os certificados vêm do `wazuh-certs-generator` oficial — uma CA **separada** da CA interna da aplicação (comprometer uma não afeta a outra).
- **Segredos como Docker Secrets**: chaves privadas, `internal_users.yml` e senhas. As imagens oficiais só aceitam senha por variável de ambiente; um entrypoint mínimo (`infra/wazuh/*/entrypoint-secrets.sh`) lê o secret e exporta só para o processo — nada em texto puro no stack ou em `docker service inspect`.
- **Sem usuários demo**: o `internal_users.yml` oficial traz `kibanaro`, `logstash`, `readall`, `snapshotrestore` com senhas públicas; o nosso só tem `admin` e `kibanaserver`, com senhas aleatórias.
- **Registro de agente com senha** (`authd.pass`): sem ela, qualquer host que alcançasse a 1515 viraria agente.
- **Exposição mínima**: publicados só 1514/1515 (agentes) e 443 (dashboard). API do manager (55000) e indexer (9200) ficam só na rede overlay. Nenhum `docker.sock` montado.

## Implantação (VM interna, .50)

```bash
free -h                                     # conferir memória (~5 GB livres)
./infra/scripts/init-wazuh.sh               # sysctl, certificados, senhas, secrets
docker stack deploy -c docker-stack.wazuh.yml wazuh
watch docker service ls                     # indexer, manager, dashboard em 1/1 (primeira subida: 3-5 min)
```

Dashboard: `https://192.168.9.50` (pelo desktop da .50 via Guacamole), usuário `admin`, senha em `secrets/wazuh/indexer_admin_password.txt`.

Agentes:

```bash
sudo ./infra/scripts/install-wazuh-agent.sh interna      # na .50
sudo ./infra/scripts/install-wazuh-agent.sh dmz          # na .34, com secrets/wazuh/authd_pass.txt copiado da .50
```

pfSense: liberar **só** `192.168.9.34 → 192.168.9.50` TCP 1514 e 1515. A 443 da .50 não deve ser alcançável pela DMZ.

## Recuperar senhas

Depois da implantação, os arquivos `secrets/wazuh/*.txt` podem (e devem) ser apagados: os serviços leem os Docker Secrets. O Swarm não devolve o conteúdo de um secret, mas o container que o recebe consegue ler — quem está no grupo `docker` da .50 recupera assim:

```bash
M=$(docker ps -qf name=wazuh_manager)
docker exec $M cat /run/secrets/wazuh_indexer_admin_password; echo   # login "admin" do dashboard
docker exec $M cat /wazuh-config-mount/etc/authd.pass; echo          # senha de registro de agentes
```

(Isso também é um achado: o grupo `docker` equivale a root no host e lê qualquer secret. A proteção do Swarm é em repouso e em trânsito, não contra o administrador do host.)

Não rodar `init-wazuh.sh` de novo depois de apagar os arquivos — ele recusa (trava no passo 0) para não gerar senhas que não batem com os secrets.

## Testar regras sem disparar ataque (`wazuh-logtest`)

```bash
docker exec -it $(docker ps -qf name=wazuh_manager) /var/ossec/bin/wazuh-logtest
```

Colar uma linha por vez:

```text
Sep 28 17:00:00 ep138-pucpr lustre-backend[1]: {"asctime": "2026-09-28 17:00:00", "levelname": "WARNING", "name": "apps.core", "message": "login_failed", "origin": "203.0.113.7"}
Sep 28 17:00:00 ep138-pucpr lustre-backend[1]: {"asctime": "2026-09-28 17:00:00", "levelname": "WARNING", "name": "apps.core", "message": "forbidden_object_access", "user_id": 7, "model": "Order", "object_id": "3"}
Sep 28 17:00:00 ep138-pucpr lustre-backend[1]: [2026-09-28 17:00:00 -0300] [42] [WARNING] Invalid request from ip=192.168.9.34: [SSL: PEER_DID_NOT_RETURN_A_CERTIFICATE] peer did not return a certificate (_ssl.c:2590)
Sep 28 17:00:00 ep138-pucpr lustre-postgres[1]: 2026-09-28 20:00:00.000 UTC [99] FATAL:  pg_hba.conf rejects connection for host "127.0.0.1", user "lustre_app", database "lustre_decor", no encryption
203.0.113.7 [2026-09-28T17:18:47-03:00] 403 upstream=- "GET /?q=<script>" rt=0.000 ua="curl/8.5.0"
2026-09-28 17:18:47,123 fail2ban.actions        [812]: NOTICE  [lustre-auth] Ban 203.0.113.7
{"hostname":"ep138-pucpr","output":"Shell iniciado","priority":"Warning","rule":"LustreDecor - Shell iniciado em container da aplicacao","source":"syscall","time":"2026-09-28T20:00:00.000Z"}
```

Esperado: regras 100101, 100106, 100120, 100131, 100301, 100401 e 100210, nessa ordem (validado em 03/10/2026; o decoder do Fail2ban precisou de ajuste porque o pré-decoder consome a data do início da linha).

## Limites conhecidos

- **`security_opt` é ignorado pelo Swarm** (vale para todos os stacks da .50): `no-new-privileges` não chega aos containers. A correção é no daemon — `"no-new-privileges": true` em `/etc/docker/daemon.json` da .50, seguido de `sudo systemctl restart docker` (os serviços voltam sozinhos com `restart_policy: any`).
- O manager baixa o feed de vulnerabilidades da Wazuh (CTI) pela Internet; sem saída liberada no pfSense, a detecção de vulnerabilidades fica sem dados (o resto funciona).
- O dashboard grava a senha da API no `wazuh.yml` do volume `wazuh-dashboard-config` (comportamento da imagem). Trocar a senha da API exige recriar esse volume.
- Os agentes não validam o certificado do `authd` (registro); a proteção do registro é a senha.
- Rotação de secrets no Swarm: secrets são imutáveis — criar com nome novo e trocar a referência no stack.
