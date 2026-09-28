#!/usr/bin/env bash
# Instala o agente Wazuh no HOST (fora de container — "quem vigia o host ou o
# Docker fica no host") e aplica a coleta do Lustre Decor.
#
#   sudo ./infra/scripts/install-wazuh-agent.sh interna   # na .50
#   sudo ./infra/scripts/install-wazuh-agent.sh dmz       # na .34
#
# Senha de registro: secrets/wazuh/authd_pass.txt (gerada na .50 por
# init-wazuh.sh; na DMZ, copiar esse arquivo para o mesmo caminho). Caminho
# alternativo via WAZUH_AUTHD_PASS_FILE.
#
# Idempotente: reexecutar só reaplica o bloco de configuração e reinicia.
set -euo pipefail

WAZUH_VERSION="4.14.7"
WAZUH_MANAGER="${WAZUH_MANAGER:-192.168.9.50}"
BEGIN_MARK="<!-- LUSTRE-DECOR-BEGIN (install-wazuh-agent.sh) -->"
END_MARK="<!-- LUSTRE-DECOR-END -->"

role="${1:-}"
case "$role" in
  interna|dmz) ;;
  *) echo "Uso: sudo $0 <interna|dmz>" >&2; exit 1 ;;
esac
[ "$(id -u)" -eq 0 ] || { echo "Rode com sudo." >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$script_dir/../.." && pwd)"
pass_file="${WAZUH_AUTHD_PASS_FILE:-$repo/secrets/wazuh/authd_pass.txt}"
[ -s "$pass_file" ] || { echo "ERRO: senha de registro não encontrada em $pass_file" >&2; exit 1; }

conf=/var/ossec/etc/ossec.conf

# --- pacote ----------------------------------------------------------------
if ! dpkg -s wazuh-agent >/dev/null 2>&1; then
  echo "Instalando wazuh-agent $WAZUH_VERSION (manager $WAZUH_MANAGER)..."
  apt-get install -y -q gnupg apt-transport-https curl >/dev/null
  if [ ! -s /usr/share/keyrings/wazuh.gpg ]; then
    curl -fsS https://packages.wazuh.com/key/GPG-KEY-WAZUH \
      | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import
    chmod 644 /usr/share/keyrings/wazuh.gpg
  fi
  echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" \
    > /etc/apt/sources.list.d/wazuh.list
  apt-get update -q >/dev/null
  # A senha vai por variável de ambiente para o postinst do pacote (que a grava
  # em /var/ossec/etc/authd.pass), não por argumento de linha de comando.
  WAZUH_MANAGER="$WAZUH_MANAGER" \
  WAZUH_AGENT_NAME="$(hostname -s)-$role" \
  WAZUH_REGISTRATION_PASSWORD="$(cat "$pass_file")" \
    apt-get install -y -q "wazuh-agent=${WAZUH_VERSION}-1"
  # Agente nunca pode ficar mais novo que o manager: sem upgrade automático.
  apt-mark hold wazuh-agent >/dev/null
fi

# Senha de registro sempre presente (reinstalação/re-registro).
install -m 640 -o root -g wazuh "$pass_file" /var/ossec/etc/authd.pass

# --- bloco do Lustre Decor no ossec.conf -----------------------------------
# Remove o bloco anterior (se houver) e anexa o atual.
tmp="$(mktemp)"
awk -v b="$BEGIN_MARK" -v e="$END_MARK" '
  $0 == b { skip = 1; next }
  $0 == e { skip = 0; next }
  !skip' "$conf" > "$tmp"
{
  echo "$BEGIN_MARK"
  sed "s|__REPO__|$repo|g" "$repo/infra/wazuh/agent/lustre-common.conf"
  [ "$role" = dmz ] && cat "$repo/infra/wazuh/agent/lustre-dmz.conf"
  echo "$END_MARK"
} >> "$tmp"
install -m 640 -o root -g wazuh "$tmp" "$conf"
rm -f "$tmp"

systemctl daemon-reload
systemctl enable wazuh-agent >/dev/null 2>&1
systemctl restart wazuh-agent

sleep 5
/var/ossec/bin/wazuh-control status | grep -E "agentd|logcollector|syscheckd" || true
echo
echo "Últimas linhas do log do agente:"
grep -E "Connected to the server|Requesting a key|Valid key received|ERROR|Invalid password" \
  /var/ossec/logs/ossec.log | tail -5 || true
