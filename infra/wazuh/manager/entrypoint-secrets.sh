#!/bin/sh
# Entrypoint do Wazuh manager no Swarm: a imagem oficial só aceita senhas por
# variável de ambiente (INDEXER_PASSWORD, API_PASSWORD). Para não deixá-las em
# texto puro no stack (visíveis em `docker service inspect`), elas chegam como
# Docker Secrets e são exportadas aqui, só no ambiente do processo, antes de
# entregar o controle ao /init (s6-overlay) da imagem — que repassa o ambiente
# aos scripts de inicialização (with-contenv).
set -eu
INDEXER_PASSWORD="$(cat /run/secrets/wazuh_indexer_admin_password)"
API_PASSWORD="$(cat /run/secrets/wazuh_api_password)"
export INDEXER_PASSWORD API_PASSWORD
exec /init "$@"
