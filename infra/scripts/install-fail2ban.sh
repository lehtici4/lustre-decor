#!/usr/bin/env bash
# Instala e configura o Fail2ban no HOST (não em container — ver
# docs/deteccao.md e Plano de Deploy, §3 "quem vigia o host fica no host").
#
# Uso (na raiz do repositório, como root):
#   sudo FAIL2BAN_IGNOREIP="192.168.9.10" ./infra/scripts/install-fail2ban.sh dmz
#   sudo FAIL2BAN_IGNOREIP="192.168.9.10" ./infra/scripts/install-fail2ban.sh interna
#
# FAIL2BAN_IGNOREIP: IPs/redes de administração que NUNCA devem ser banidos
# (ex.: o servidor do Guacamole de onde vocês acessam as VMs). Separados por
# espaço. Sem isso, errar a senha do SSH algumas vezes pelo Guacamole bane o
# próprio acesso de administração.
#
#   dmz     -> sshd + lustre-auth + lustre-ratelimit + lustre-waf + recidive
#              (lê /var/log/lustre-waf/access.log gerado pelo waf)
#   interna -> sshd + recidive
set -euo pipefail

ROLE="${1:-}"
if [[ "$ROLE" != "dmz" && "$ROLE" != "interna" ]]; then
    echo "Uso: $0 dmz|interna" >&2
    exit 64
fi
if [[ $EUID -ne 0 ]]; then
    echo "Rode como root (sudo)." >&2
    exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$REPO_DIR/infra/fail2ban"
IGNOREIP="${FAIL2BAN_IGNOREIP:-}"
LOG_DIR=/var/log/lustre-waf

echo "==> Instalando pacotes"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
# python3-systemd: backend "systemd" da jail sshd (Ubuntu 24.04 não grava
# /var/log/auth.log por padrão). nftables: ação de ban.
apt-get install -y -q fail2ban python3-systemd nftables

if [[ "$ROLE" == "dmz" ]]; then
    echo "==> Diretório do access log do waf ($LOG_DIR)"
    # Dono = UID do usuário nginx da imagem do waf. Tenta descobrir pela
    # própria imagem; cai para 101 (padrão da imagem owasp/modsecurity-crs).
    WAF_UID="${WAF_UID:-}"
    if [[ -z "$WAF_UID" ]]; then
        WAF_IMAGE="${WAF_IMAGE:-lustre_decor-waf}"
        if docker image inspect "$WAF_IMAGE" >/dev/null 2>&1; then
            WAF_UID="$(docker run --rm --entrypoint id "$WAF_IMAGE" -u 2>/dev/null | tr -dc '0-9' || true)"
        fi
    fi
    WAF_UID="${WAF_UID:-101}"
    install -d -m 0750 -o "$WAF_UID" -g "$WAF_UID" "$LOG_DIR"
    touch "$LOG_DIR/access.log"
    chown "$WAF_UID:$WAF_UID" "$LOG_DIR/access.log"
    chmod 0640 "$LOG_DIR/access.log"
    echo "    dono: UID $WAF_UID"

    echo "==> Filtros e logrotate"
    install -m 0644 "$SRC"/filter.d/lustre-*.conf /etc/fail2ban/filter.d/
    install -m 0644 "$SRC/logrotate/lustre-waf" /etc/logrotate.d/lustre-waf
fi

echo "==> Jails ($ROLE)"
sed "s|__IGNOREIP__|$IGNOREIP|" "$SRC/jail.d/lustre-decor-$ROLE.local" > /etc/fail2ban/jail.d/lustre-decor.local
chmod 0644 /etc/fail2ban/jail.d/lustre-decor.local

echo "==> systemd: fail2ban depois do Docker"
install -d /etc/systemd/system/fail2ban.service.d
install -m 0644 "$SRC/systemd/override.conf" /etc/systemd/system/fail2ban.service.d/lustre-decor.conf
systemctl daemon-reload

echo "==> Testando configuração"
fail2ban-client -t

systemctl enable --now fail2ban
systemctl restart fail2ban
sleep 2

if [[ "$ROLE" == "dmz" ]]; then
    cat <<EOF

Fail2ban ativo. Próximo passo (uma vez): recriar o waf para montar o log:
  cd $REPO_DIR && docker compose -f docker-compose.dmz.yml up -d --build
  tail -f $LOG_DIR/access.log     # deve aparecer uma linha por requisição

EOF
fi
fail2ban-client status
