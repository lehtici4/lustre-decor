#!/usr/bin/env bash
# Gera (ou renova) o certificado TLS autoassinado usado pelo perfil de
# produção local — ver README, "TLS local". Recebe o IP ou hostname real
# usado pra acessar a aplicação e o coloca só no SAN (Subject Alternative
# Name) — nunca no CN: certificado que depende do CN pro endereço é rejeitado
# por navegadores e clientes HTTP modernos (RFC 6125), e SAN é o campo que
# eles realmente validam. Por isso o CN aqui é um rótulo genérico, não um dos
# endereços.
#
# Uso:
#   ./infra/scripts/generate-tls-cert.sh 192.168.9.34
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Uso: $0 <IP-ou-hostname> [IP-ou-hostname adicional ...]" >&2
  echo "Exemplo: $0 192.168.9.34" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_root="$(cd "$script_dir/../.." && pwd)"
tls_dir="$workspace_root/secrets/tls"
mkdir -p "$tls_dir"

# CN genérico de propósito — nunca um dos endereços (ver comentário acima).
cn="LustreDecor"

# Monta o SAN a partir de cada argumento: números-e-pontos viram entrada
# "IP:", o resto vira entrada "DNS:". 127.0.0.1 e localhost sempre inclusos,
# pra continuar valendo pro uso local mesmo gerando pro IP/domínio do lab.
san_entries=("IP:127.0.0.1" "DNS:localhost")
for arg in "$@"; do
  if [[ "$arg" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    entry="IP:$arg"
  else
    entry="DNS:$arg"
  fi
  [[ " ${san_entries[*]} " == *" $entry "* ]] || san_entries+=("$entry")
done
san=$(printf "%s," "${san_entries[@]}")
san="${san%,}"

openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout "$tls_dir/localhost.key" \
  -out "$tls_dir/localhost.crt" \
  -subj "//CN=$cn" \
  -addext "subjectAltName=$san"

chmod 600 "$tls_dir/localhost.key"
chmod 644 "$tls_dir/localhost.crt"

echo "Gerado: $tls_dir/localhost.{crt,key}"
echo "SAN: $san"
