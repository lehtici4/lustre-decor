#!/usr/bin/env bash
# Implanta o cofre (OpenBao) na VM interna (.50). Idempotente.
#
#   sudo ./infra/scripts/init-cofre.sh
#
# 1) /var/log/openbao (dono = usuário do OpenBao) + logrotate;
# 2) certificado TLS autoassinado do cofre -> Docker Secrets cofre_tls_cert e
#    cofre_tls_key (só se ainda não existirem). A chave é gerada em memória
#    (/dev/shm) e apagada logo depois: só o Swarm guarda;
# 3) docker stack deploy -c docker-stack.cofre.yml cofre;
# 4) espera o cofre responder e mostra o estado.
#
# NÃO inicializa o cofre: o `bao operator init` mostra as chaves de unseal e
# o root token uma única vez e tem que ser feito por quem vai guardá-las
# (docs/cofre.md, "Cerimônia de inicialização").
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Rode com sudo." >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$script_dir/../.." && pwd)"
COFRE_IP="${COFRE_IP:-192.168.9.50}"
BAO_UID=100
BAO_GID=1000

# --- 1) log de auditoria --------------------------------------------------
install -d -o "$BAO_UID" -g "$BAO_GID" -m 0750 /var/log/openbao
install -m 0644 "$repo/infra/openbao/logrotate" /etc/logrotate.d/openbao
echo "Log de auditoria: /var/log/openbao (logrotate diário, 14 dias)"

# --- 2) certificado TLS ---------------------------------------------------
# Autoassinado e marcado como CA, para servir de âncora de confiança para
# quem fala com o cofre (BAO_CACERT / --cacert). A CA interna da aplicação
# não é usada porque a chave dela já foi apagada dos servidores.
if docker secret inspect cofre_tls_key >/dev/null 2>&1; then
  echo "Certificado do cofre já existe (secret cofre_tls_key)."
else
  tmp="$(mktemp -d /dev/shm/cofre.XXXXXX)"
  chmod 700 "$tmp"
  trap 'shred -u "$tmp"/* 2>/dev/null || true; rmdir "$tmp" 2>/dev/null || true' EXIT
  openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$tmp/key.pem" 2>/dev/null
  openssl req -x509 -new -key "$tmp/key.pem" -sha256 -days 825 \
    -subj "/O=LustreDecor Lab/CN=cofre.lustre.internal" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,digitalSignature,keyCertSign" \
    -addext "extendedKeyUsage=serverAuth" \
    -addext "subjectAltName=DNS:cofre.lustre.internal,DNS:localhost,IP:127.0.0.1,IP:$COFRE_IP" \
    -out "$tmp/cert.pem"
  docker secret create cofre_tls_key "$tmp/key.pem" >/dev/null
  docker secret create cofre_tls_cert "$tmp/cert.pem" >/dev/null
  # O certificado é público: fica em secrets/pki/ para os clientes confiarem.
  install -D -m 0644 "$tmp/cert.pem" "$repo/secrets/pki/cofre.crt"
  [ -n "${SUDO_USER:-}" ] && chown "$SUDO_USER": "$repo/secrets/pki/cofre.crt"
  echo "Certificado do cofre criado; público em secrets/pki/cofre.crt"
  openssl x509 -in "$repo/secrets/pki/cofre.crt" -noout -fingerprint -sha256
fi

# --- 3) deploy --------------------------------------------------------------
cd "$repo"
docker stack deploy -c docker-stack.cofre.yml cofre

# --- 4) esperar responder ---------------------------------------------------
echo -n "Aguardando o cofre"
for _ in $(seq 1 60); do
  c="$(docker ps -qf name=cofre_openbao | head -1)"
  if [ -n "$c" ]; then
    rc=0
    docker exec "$c" bao status >/dev/null 2>&1 || rc=$?
    # 0 = destrancado, 2 = selado (normal antes do init/unseal)
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ]; then
      echo
      docker exec "$c" bao status || true
      cat <<'NEXT'

Próximo passo (quem vai guardar as chaves, SEM ninguém olhando a tela):
  docker exec -it $(docker ps -qf name=cofre_openbao) bao operator init -key-shares=3 -key-threshold=2
Depois: 2x `bao operator unseal` e ./infra/scripts/configurar-cofre.sh
Detalhes em docs/cofre.md.
NEXT
      exit 0
    fi
  fi
  echo -n "."
  sleep 5
done
echo
echo "O cofre não respondeu em 5 min. Veja: docker service logs cofre_openbao" >&2
exit 1
