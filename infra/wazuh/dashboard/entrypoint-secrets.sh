#!/bin/bash
# Entrypoint do Wazuh dashboard no Swarm: mesma ideia do manager — senhas
# vindas de Docker Secrets, exportadas só para o /entrypoint.sh da imagem
# (que as grava no keystore do dashboard e no wazuh.yml do volume de config).
set -eu
DASHBOARD_PASSWORD="$(cat /run/secrets/wazuh_kibanaserver_password)"
API_PASSWORD="$(cat /run/secrets/wazuh_api_password)"
export DASHBOARD_PASSWORD API_PASSWORD
exec /entrypoint.sh "$@"
