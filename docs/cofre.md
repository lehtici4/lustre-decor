# Cofre de segredos (OpenBao)

O OpenBao (fork aberto do HashiCorp Vault, Linux Foundation) roda na VM interna (`192.168.9.50`) num stack Swarm próprio (`docker-stack.cofre.yml`, stack `cofre`). Ele substitui os arquivos `secrets/*.txt` como **fonte da verdade** dos segredos.

| Papel | Como |
|---|---|
| Guardar os segredos | KV v2 em `lustre/` (`lustre/app`, `lustre/postgres`, `lustre/pki`, `lustre/wazuh`, `lustre/wazuh-pki`) |
| Entregar aos serviços | **continua sendo Docker Secrets**: `infra/scripts/cofre-para-swarm.sh` cria cada secret com a versão no nome (`postgres_password_v2`) a partir do cofre |
| Acesso de pessoas | usuário e senha próprios (userpass) + política `admin`; token de 8 h; root token revogado depois da configuração |
| Auditoria | cada requisição vira uma linha JSON em `/var/log/openbao/audit.log` → agente Wazuh → regras 1006xx |
| SSH (etapa 2) | autoridade certificadora: certificados de 8 h para os admins |

**A loja não depende do cofre em funcionamento.** Os containers leem Docker Secrets; o cofre só é consultado para criar ou trocar segredos. Depois de um reboot o cofre volta **selado** (trancado) e a loja e o Wazuh seguem normais até alguém destrancar.

Diferença para o Twingate: o Twingate decide *quem chega a qual recurso pela rede*; o cofre decide *quem recebe qual segredo* e registra cada entrega. Um não substitui o outro.

## Implantação (uma vez, na .50)

```bash
cd ~/lustre-decor && git pull --ff-only
sudo ./infra/scripts/init-cofre.sh
```

Cria `/var/log/openbao` (dono uid 100, o usuário da imagem) e o logrotate, gera o certificado TLS do cofre (autoassinado, chave só no Docker Secret `cofre_tls_key`, público em `secrets/pki/cofre.crt`), faz o deploy e espera o cofre responder (`Sealed: true`, `Initialized: false`).

## Cerimônia de inicialização

O `operator init` mostra **uma única vez** as chaves de unseal e o root token. Quem vai guardá-las roda os comandos, **sem compartilhar a tela** (nem Guacamole gravado, nem o Claude olhando).

```bash
C=$(docker ps -qf name=cofre_openbao)
docker exec -it $C bao operator init -key-shares=3 -key-threshold=2
```

- 3 chaves, 2 destrancam. Sugestão: chave 1 com a Letícia, chave 2 com o Nathan (entregue pessoalmente ou por canal cifrado), chave 3 guardada offline (impressa, envelope) para emergência. Nenhuma chave em arquivo no servidor, no repo ou no OneDrive.
- Root token: só para o próximo passo; é revogado no fim dele.

```bash
docker exec -it $C bao operator unseal      # chave 1 (pedida sem eco)
docker exec -it $C bao operator unseal      # chave 2 -> "Sealed: false"
sudo ./infra/scripts/configurar-cofre.sh    # pede o root token sem eco
clear; history -c                           # e feche o terminal
```

O `configurar-cofre.sh` habilita o KV, grava a política `admin`, cria os usuários `leticia` e `nathan` (senha inicial sem eco, mínimo 14 caracteres), **importa os Docker Secrets atuais** para o cofre (lendo no host — `/var/lib/docker/containers/<id>/mounts/secrets/` — para não disparar a regra 100212 do Falco nem a resposta ativa), testa o login e oferece revogar o root token. Com 2 chaves de unseal sempre é possível gerar um root novo (`bao operator generate-root`).

## Depois de cada reboot da .50

```bash
docker exec -it $(docker ps -qf name=cofre_openbao) bao operator unseal   # 2 vezes, 2 chaves
```

## Uso no dia a dia

```bash
source infra/openbao/cofre.sh
cofre_login leticia                  # senha sem eco; exporta BAO_TOKEN (8 h)
bao kv list lustre/
bao kv metadata get lustre/postgres  # versões, sem mostrar valores
cofre_logout
```

O CLI `bao` roda dentro do container do cofre; o token vai por `-e BAO_TOKEN` sem valor (não aparece em `ps`). Evite `bao kv get` sem `-field` num terminal compartilhado: mostra os valores.

Interface web: `https://192.168.9.50:8200/ui` (certificado autoassinado; confira a impressão digital que o `init-cofre.sh` mostrou).

## Da fonte da verdade para os serviços

```bash
source infra/openbao/cofre.sh && cofre_login leticia
eval "$(./infra/scripts/cofre-para-swarm.sh)"          # cria *_vN e exporta os nomes
docker stack deploy -c docker-stack.interna.yml lustre_decor
```

Sem as variáveis, o `docker-stack.interna.yml` usa os nomes antigos (`django_secret_key`...), então nada quebra antes da migração. Depois do primeiro deploy com `_v1`, os secrets antigos podem ser removidos (`docker secret rm`).

### Rotação

```bash
# django_secret_key (invalida as sessões abertas)
openssl rand -base64 48 | tr -d '\n' | bao kv patch lustre/app django_secret_key=-
eval "$(./infra/scripts/cofre-para-swarm.sh)" && docker stack deploy -c docker-stack.interna.yml lustre_decor
```

Senha do Postgres: trocar **primeiro no banco** (`ALTER ROLE ... PASSWORD`) e depois no cofre + deploy — o secret sozinho não muda a senha de um banco já inicializado. Segredos do Wazuh ficam no cofre como cópia de recuperação; a rotação deles (hashes do `internal_users.yml`, volume do dashboard) não está automatizada.

## Auditoria no Wazuh

Agente da .50: `localfile` JSON em `/var/log/openbao/audit.log` (`infra/wazuh/agent/lustre-interna.conf`, aplicado por `install-wazuh-agent.sh interna`).

| Regra | Nível | Evento |
|---|---|---|
| 100601 | 3 | segredo lido |
| 100602 | 5 | segredo criado/alterado/apagado |
| 100603 / 100604 | 8 / 12 | acesso negado / repetido da mesma origem (enumeração) |
| 100605 / 100606 | 8 / 12 | falha de login / 5 em 2 min (força bruta) |
| 100607 | 12 | qualquer operação com o root token |
| 100608 | 6 | certificado SSH emitido |
| 100609 | 10 | mudança de configuração (selar, políticas, auth, motores, auditoria) |

Linha para o `wazuh-logtest` (regra 100601):

```text
{"time":"2026-10-26T23:00:00Z","type":"response","auth":{"display_name":"userpass-leticia","policies":["admin","default"]},"request":{"id":"1","operation":"read","path":"lustre/data/app","remote_address":"127.0.0.1"},"response":{}}
```

Antes de aplicar regras novas: `./infra/scripts/wazuh-validar-regras.sh` (valida no manager em execução e desfaz se houver erro).

## Limites conhecidos

- **Nó único**, sem alta disponibilidade. Backup: `bao operator raft snapshot save` (exige token com acesso a `sys/storage/raft/snapshot`).
- **mlock desligado** (recomendação para o storage raft) e a .50 tem swap: memória do processo pode ir para o disco.
- **Certificado autoassinado**: clientes confiam em `secrets/pki/cofre.crt`. Evolução: o motor PKI do próprio cofre virar a CA interna (a chave da CA atual já foi apagada).
- O CLI roda no container, então a auditoria mostra `remote_address` 127.0.0.1 para o uso local; acessos pelo Twingate aparecem com o IP do Connector.
- Root no host da .50 continua lendo qualquer Docker Secret (achado já registrado); o cofre protege a origem e audita, não o host.
- Falco: incluir `/var/log/openbao/` nos caminhos protegidos (apagar/truncar auditoria) — pendente.
