#!/usr/bin/env bash
# Cria, a partir do cofre, os Docker Secrets da aplicação com a VERSÃO no
# nome (ex.: postgres_password_v2) e imprime os `export` que o
# docker-stack.interna.yml usa para escolher qual versão montar.
#
#   source infra/openbao/cofre.sh && cofre_login leticia
#   eval "$(./infra/scripts/cofre-para-swarm.sh)"
#   docker stack deploy -c docker-stack.interna.yml lustre_decor
#
# Secrets do Swarm são imutáveis: trocar um segredo = nova versão no cofre
# (bao kv patch ...) + rodar isto + redeploy. Versões que já existem como
# Docker Secret não são recriadas. Os valores passam do cofre para o
# `docker secret create` por pipe — nunca em arquivo nem na tela.
# Atenção: senha do Postgres nova exige também ALTER ROLE no banco
# (docs/cofre.md, "Rotação").
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$script_dir/../.." && pwd)"
# shellcheck source=../openbao/cofre.sh
. "$repo/infra/openbao/cofre.sh"
[ -n "${BAO_TOKEN:-}" ] || { echo "Faça login antes: source infra/openbao/cofre.sh && cofre_login <usuário>" >&2; exit 1; }
export BAO_TOKEN

# <variável no stack> <nome base do secret> <caminho KV> <campo>
while read -r var base path field; do
  [ -n "$var" ] || continue
  json=$(bao kv get -format=json "$path")
  ver=$(printf '%s' "$json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["metadata"]["version"])')
  name="${base}_v${ver}"
  if docker secret inspect "$name" >/dev/null 2>&1; then
    echo "existe: $name" >&2
  else
    printf '%s' "$json" | python3 -c 'import json,sys; sys.stdout.write(json.load(sys.stdin)["data"]["data"][sys.argv[1]])' "$field" \
      | docker secret create --label origem=cofre --label caminho="$path" "$name" - >/dev/null
    echo "criado: $name" >&2
  fi
  echo "export $var=$name"
done <<'MAPA'
DJANGO_SECRET_KEY_SECRET         django_secret_key         lustre/app      django_secret_key
POSTGRES_PASSWORD_SECRET         postgres_password         lustre/postgres superuser_password
POSTGRES_RUNTIME_PASSWORD_SECRET postgres_runtime_password lustre/postgres runtime_password
MAPA
