#!/bin/sh
# Entrypoint do Postgres com TLS obrigatório. Roda como root (antes do
# docker-entrypoint.sh oficial rebaixar para o usuário postgres) só para uma
# coisa: copiar certificado e chave dos Docker Secrets para um diretório do
# usuário postgres, com as permissões que o Postgres exige (chave 0600, dono
# postgres). Os secrets em si chegam como root 0444 (Swarm) ou com as
# permissões do arquivo no host (Compose, Windows) — o Postgres recusaria
# subir com a chave assim ("private key file has group or world access").
set -eu

TLS_DIR=/var/run/postgresql/tls
mkdir -p "$TLS_DIR"
cp /run/secrets/postgres_tls_cert "$TLS_DIR/server.crt"
cp /run/secrets/postgres_tls_key "$TLS_DIR/server.key"
chown -R postgres:postgres "$TLS_DIR"
chmod 700 "$TLS_DIR"
chmod 644 "$TLS_DIR/server.crt"
chmod 600 "$TLS_DIR/server.key"

# pg_hba.conf próprio (infra/postgres/pg_hba.conf): conexão pela rede só com
# TLS (hostssl) e senha SCRAM; sem TLS = rejeitada.
exec docker-entrypoint.sh postgres \
    -c ssl=on \
    -c ssl_cert_file="$TLS_DIR/server.crt" \
    -c ssl_key_file="$TLS_DIR/server.key" \
    -c ssl_min_protocol_version=TLSv1.2 \
    -c hba_file=/etc/lustre-postgres/pg_hba.conf \
    "$@"
