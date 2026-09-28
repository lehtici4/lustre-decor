#!/usr/bin/env bash
# CA interna do laboratório + certificados dos saltos INTERNOS da aplicação.
# O certificado público do waf (secrets/tls/dmz.crt, o que o navegador vê)
# continua vindo de generate-tls-cert.sh — este script cobre o que vem
# depois dele:
#
#   waf (DMZ) --mTLS--> backend :8000 (Gunicorn)   backend.crt + waf-client.crt
#   backend   --TLS---> postgres :5432              postgres.crt (verify-full)
#
# Arquivos gerados em secrets/pki/ (fora do Git, como todo secrets/):
#   ca.crt / ca.key                 CA interna (a chave só serve para emitir)
#   backend.crt / backend.key       servidor do Gunicorn; também clientAuth,
#                                   para o healthcheck do próprio container
#   waf-client.crt / waf-client.key identidade do waf perante o backend (mTLS)
#   postgres.crt / postgres.key     servidor do Postgres
#
# Chaves EC P-256: handshake barato e PEM curto (dá para colar pelo
# clipboard do Guacamole ao levar os arquivos do waf para a DMZ).
#
# Uso:
#   ./infra/scripts/generate-internal-pki.sh            # cria só o que falta
#   ./infra/scripts/generate-internal-pki.sh --force    # recria TUDO (nova CA)
#
# Variáveis opcionais:
#   BACKEND_IP=192.168.9.50   IP da VM interna (entra no SAN do backend)
#   LEAF_DAYS=825  CA_DAYS=3650
set -euo pipefail

# Git Bash (Windows) converteria "/CN=..." em caminho de arquivo.
export MSYS_NO_PATHCONV=1

BACKEND_IP="${BACKEND_IP:-192.168.9.50}"
LEAF_DAYS="${LEAF_DAYS:-825}"
CA_DAYS="${CA_DAYS:-3650}"
# Nome que o waf usa para VALIDAR o certificado do backend (proxy_ssl_name
# no template do Nginx). Nome e não IP: a verificação de nome do Nginx
# (X509_check_host) não casa entradas IP do SAN.
BACKEND_TLS_NAME="backend.lustre.internal"

force=false
if [ "${1:-}" = "--force" ]; then
  force=true
elif [ $# -gt 0 ]; then
  echo "Uso: $0 [--force]" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_root="$(cd "$script_dir/../.." && pwd)"
pki_dir="$workspace_root/secrets/pki"
mkdir -p "$pki_dir"
chmod 700 "$pki_dir"
cd "$pki_dir"

if $force; then
  rm -f ca.* backend.* waf-client.* postgres.* ./*.srl ./*.csr ./*.ext
fi

new_key() {
  openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$1" 2>/dev/null
  chmod 600 "$1"
}

if [ ! -f ca.key ] || [ ! -f ca.crt ]; then
  if ls backend.crt waf-client.crt postgres.crt >/dev/null 2>&1; then
    echo "ERRO: ca.key/ca.crt ausentes mas há certificados emitidos. Use --force para recriar tudo." >&2
    exit 1
  fi
  new_key ca.key
  openssl req -x509 -new -key ca.key -sha256 -days "$CA_DAYS" \
    -subj "/O=LustreDecor Lab/CN=LustreDecor Internal CA" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -addext "subjectKeyIdentifier=hash" \
    -out ca.crt
  chmod 644 ca.crt
  echo "CA criada: $pki_dir/ca.crt"
fi

# issue <nome> <CN> <extendedKeyUsage> [subjectAltName]
issue() {
  local name="$1" cn="$2" eku="$3" san="${4:-}"
  if [ -f "$name.crt" ] && [ -f "$name.key" ]; then
    echo "Já existe: $name.crt (use --force para recriar)"
    return
  fi
  new_key "$name.key"
  openssl req -new -key "$name.key" -subj "/O=LustreDecor Lab/CN=$cn" -out "$name.csr"
  {
    echo "basicConstraints=critical,CA:FALSE"
    echo "keyUsage=critical,digitalSignature"
    echo "extendedKeyUsage=$eku"
    echo "subjectKeyIdentifier=hash"
    echo "authorityKeyIdentifier=keyid"
    [ -n "$san" ] && echo "subjectAltName=$san"
  } > "$name.ext"
  openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -sha256 -days "$LEAF_DAYS" -extfile "$name.ext" -out "$name.crt" 2>/dev/null
  chmod 644 "$name.crt"
  rm -f "$name.csr" "$name.ext"
  openssl verify -CAfile ca.crt "$name.crt" >/dev/null
  echo "Emitido: $name.crt  (EKU=$eku${san:+  SAN=$san})"
}

issue backend "$BACKEND_TLS_NAME" "serverAuth,clientAuth" \
  "DNS:$BACKEND_TLS_NAME,DNS:backend,DNS:localhost,IP:127.0.0.1,IP:$BACKEND_IP"
issue waf-client "waf-dmz" "clientAuth"
issue postgres "postgres" "serverAuth" "DNS:postgres,DNS:localhost,IP:127.0.0.1"

cat <<EOF

Pronto. Onde cada arquivo vai:
  VM interna (Swarm):  ca.crt, backend.crt, backend.key, postgres.crt, postgres.key
                       -> docker secret create (ver docker-stack.interna.yml)
  VM DMZ (Compose):    ca.crt, waf-client.crt, waf-client.key -> secrets/pki/
                       (waf-client.key com dono UID 101, o nginx da imagem)
  ca.key:              só serve para emitir certificados. Guarde fora dos
                       servidores e apague daqui depois de emitir.
EOF
