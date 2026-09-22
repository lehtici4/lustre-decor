#!/usr/bin/env bash
# Backup diario do Postgres da VM interna (Etapa 5.1 do plano de deploy —
# "mecanismos de recuperacao"). Roda no HOST via cron, nunca dentro de um
# container: e o host que registra o arquivo num diretorio que o FIM do
# Wazuh (quando instalado) vai monitorar, e o proprio arquivo de dump serve
# de alvo realista para o teste de exfiltracao T06 — ver decisoes registradas
# em claude/Plano_Deploy_Containerizacao_LustreDecor.md.
#
# Usa `docker exec` no container do Postgres e le a senha do secret que o
# Swarm ja montou DENTRO do container (/run/secrets/postgres_password) — o
# host nunca precisa guardar credencial nenhuma para isso.
#
# Usuario: POSTGRES_USER (papel dono do banco, ex.: lustre_app), nao o
# lustre_app_runtime. O runtime so tem SELECT via ALTER DEFAULT PRIVILEGES
# (ver infra/postgres/init-app-role.sh) — cobre as tabelas certas hoje, mas
# um backup de recuperacao nao pode depender de nenhuma tabela/sequencia
# futura ficar de fora por um grant que nao foi replicado. O dono sempre
# enxerga tudo.
#
# Uso: chamado pelo cron, sem argumentos. Ajuste STACK_NAME/DEST abaixo se
# o nome do stack ou o destino mudarem.
set -euo pipefail

STACK_NAME="lustre_decor"
DEST="/var/backups/lustre_decor"
RETENTION_DAYS=14
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DUMP_FILE="$DEST/lustre_decor_${TIMESTAMP}.dump"
SUM_FILE="${DUMP_FILE}.sha256"

mkdir -p "$DEST"
chmod 700 "$DEST"

CID="$(docker ps -q -f "name=${STACK_NAME}_postgres")"
if [ -z "$CID" ]; then
  echo "[$(date -Is)] ERRO: container ${STACK_NAME}_postgres nao encontrado" >&2
  exit 1
fi

# --format=custom: comprimido e restauravel com pg_restore (inclusive
# seletivamente, tabela por tabela), diferente de um .sql puro.
docker exec "$CID" sh -c '
  set -eu
  export PGPASSWORD="$(cat /run/secrets/postgres_password)"
  exec pg_dump -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom
' > "$DUMP_FILE"

chmod 600 "$DUMP_FILE"

# Checksum ao lado do dump: evidencia de integridade utilizavel ja hoje,
# antes do Wazuh existir. Depois que o FIM (syscheck) estiver monitorando
# este diretorio, ele passa a ser redundante, mas nao faz mal manter.
sha256sum "$DUMP_FILE" > "$SUM_FILE"

# Prova rapida de que o arquivo e um dump valido (nao testa restauracao
# completa — isso fica pro teste manual de recuperacao, ver docs/security.md
# ou o roteiro de evidencias do Sprint 1).
if ! pg_restore --list "$DUMP_FILE" > /dev/null 2>&1; then
  echo "[$(date -Is)] AVISO: pg_restore --list falhou para $DUMP_FILE (dump pode estar corrompido)" >&2
fi

echo "[$(date -Is)] OK: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# Retencao: apaga dumps com mais de RETENTION_DAYS. Sinaliza cada remocao no
# log do proprio cron — se o Wazuh syscheck estiver monitorando $DEST quando
# isso rodar, a exclusao vai gerar evento; e esperado (rotina agendada, nao
# incidente), mas vale registrar uma excecao/regra para essa janela de
# horario ao configurar o Wazuh, pra nao virar ruido.
find "$DEST" -maxdepth 1 -name '*.dump' -mtime "+${RETENTION_DAYS}" -print -delete
find "$DEST" -maxdepth 1 -name '*.dump.sha256' -mtime "+${RETENTION_DAYS}" -print -delete
