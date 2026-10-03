#!/usr/bin/env bash
# Prepara a VM interna (.50) para o stack do Wazuh (docker-stack.wazuh.yml).
# Idempotente: só cria o que falta. Rodar da raiz do repositório, como o
# usuário que opera o Docker (usa sudo só para o sysctl e para ajustar dono
# dos certificados gerados pelo container oficial).
#
#   ./infra/scripts/init-wazuh.sh
#
# O que faz:
#   1. vm.max_map_count=262144 persistente (o OpenSearch não sobe sem isso);
#   2. certificados do Wazuh (indexer, manager/Filebeat, dashboard, admin)
#      com o wazuh-certs-generator oficial -> secrets/wazuh/certs/;
#   3. senhas aleatórias (admin do indexer, kibanaserver, API wazuh-wui,
#      registro de agentes) -> secrets/wazuh/*.txt;
#   4. internal_users.yml com os hashes bcrypt dessas senhas;
#   5. Docker Secrets do Swarm (wazuh_*), a partir dos arquivos acima.
set -euo pipefail

WAZUH_VERSION="4.14.7"
CERTS_GENERATOR_IMAGE="wazuh/wazuh-certs-generator:0.0.4"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$script_dir/../.." && pwd)"
out="$repo/secrets/wazuh"
certs="$out/certs"
mkdir -p "$out"
chmod 700 "$out"

# --- 0. trava: secrets já existem mas os arquivos de origem sumiram ---------
# O Swarm não devolve o conteúdo de um secret. Se as senhas já foram criadas
# no Swarm e os .txt foram apagados (o recomendado depois da implantação),
# gerar senhas novas aqui criaria arquivos que NÃO correspondem ao que os
# serviços usam. Para recuperar uma senha: docker exec no container que a
# recebe (ver docs/wazuh.md). Para recomeçar do zero: remover o stack e os
# secrets wazuh_* antes.
if docker secret inspect wazuh_indexer_admin_password >/dev/null 2>&1; then
  for name in indexer_admin_password kibanaserver_password api_password authd_pass; do
    if [ ! -s "$out/$name.txt" ]; then
      echo "ERRO: o secret wazuh_* já existe no Swarm mas secrets/wazuh/$name.txt não." >&2
      echo "Nada foi alterado. Veja 'Recuperar senhas' em docs/wazuh.md." >&2
      exit 1
    fi
  done
fi

# --- 1. kernel -------------------------------------------------------------
if [ "$(sysctl -n vm.max_map_count)" -lt 262144 ]; then
  echo "vm.max_map_count=262144" | sudo tee /etc/sysctl.d/99-wazuh-indexer.conf >/dev/null
  sudo sysctl -q -p /etc/sysctl.d/99-wazuh-indexer.conf
fi
echo "vm.max_map_count = $(sysctl -n vm.max_map_count)"

# --- 2. certificados -------------------------------------------------------
if [ ! -f "$certs/root-ca.pem" ]; then
  echo "Gerando certificados do Wazuh ($CERTS_GENERATOR_IMAGE)..."
  mkdir -p "$certs"
  docker run --rm \
    -e CERT_TOOL_VERSION="${WAZUH_VERSION%.*}" \
    -v "$certs:/certificates/" \
    -v "$repo/infra/wazuh/certs.yml:/config/certs.yml:ro" \
    "$CERTS_GENERATOR_IMAGE"
  # O gerador deixa os arquivos com dono 1000/999 e o diretório 500: devolve
  # ao usuário atual para o `docker secret create` ler (o dono dentro dos
  # containers é definido no stack, por secret).
  sudo chown -R "$(id -u):$(id -g)" "$certs"
  chmod 700 "$certs"
  chmod 600 "$certs"/*
fi
for f in root-ca.pem admin.pem admin-key.pem wazuh.indexer.pem wazuh.indexer-key.pem \
         wazuh.manager.pem wazuh.manager-key.pem wazuh.dashboard.pem wazuh.dashboard-key.pem; do
  [ -f "$certs/$f" ] || { echo "ERRO: $certs/$f não foi gerado." >&2; exit 1; }
done

# --- 3. senhas -------------------------------------------------------------
# Política da API do Wazuh: 8-64 caracteres com maiúscula, minúscula, número
# e símbolo. Só "." e "-" como símbolos: os scripts da imagem usam a senha
# dentro de sed/YAML/JSON sem escape.
# (Sem `tr </dev/urandom | head`: com pipefail, o SIGPIPE do tr abortaria o script.)
rand_alnum() {
  local s
  s="$(openssl rand -base64 96 | LC_ALL=C tr -dc 'A-Za-z0-9')"
  printf '%s' "${s:0:$1}"
}
gen_password() {
  local pw
  while :; do
    pw="$(rand_alnum 10).$(rand_alnum 10)-$(rand_alnum 6)"
    [[ "$pw" =~ [A-Z] && "$pw" =~ [a-z] && "$pw" =~ [0-9] ]] && break
  done
  printf '%s' "$pw"
}
for name in indexer_admin_password kibanaserver_password api_password authd_pass; do
  if [ ! -s "$out/$name.txt" ]; then
    gen_password > "$out/$name.txt"
    chmod 600 "$out/$name.txt"
    echo "Senha gerada: secrets/wazuh/$name.txt"
  fi
done

# --- 4. internal_users.yml -------------------------------------------------
# Hash bcrypt com a ferramenta do próprio indexer. A senha entra por stdin e
# chega ao Hasher por variável de ambiente (-env), não por argumento — evita
# que apareça no `ps` do host. Se esta versão não tiver -env, cai para -p.
bcrypt_hash() {
  docker run --rm -i --entrypoint bash -e JAVA_HOME=/usr/share/wazuh-indexer/jdk \
    "wazuh/wazuh-indexer:$WAZUH_VERSION" -c \
    'export LUSTRE_PW="$(cat)"; T=/usr/share/wazuh-indexer/plugins/opensearch-security/tools/hash.sh
     out="$(bash $T -env LUSTRE_PW 2>/dev/null | grep -E "^[\$]2[aby][\$]" | tail -1)"
     [ -n "$out" ] || out="$(bash $T -p "$LUSTRE_PW" 2>/dev/null | grep -E "^[\$]2[aby][\$]" | tail -1)"
     printf "%s\n" "$out"' \
    < "$1"
}
if [ ! -s "$out/internal_users.yml" ]; then
  echo "Gerando hashes do internal_users.yml..."
  admin_hash="$(bcrypt_hash "$out/indexer_admin_password.txt")"
  kibana_hash="$(bcrypt_hash "$out/kibanaserver_password.txt")"
  [ -n "$admin_hash" ] && [ -n "$kibana_hash" ] || { echo "ERRO: falha ao gerar hash bcrypt." >&2; exit 1; }
  sed -e "s|__ADMIN_HASH__|$admin_hash|" -e "s|__KIBANASERVER_HASH__|$kibana_hash|" \
    "$repo/infra/wazuh/internal_users.yml.template" > "$out/internal_users.yml"
  chmod 600 "$out/internal_users.yml"
fi

# --- 5. Docker Secrets -----------------------------------------------------
create_secret() {
  if docker secret inspect "$1" >/dev/null 2>&1; then
    echo "Secret já existe: $1"
  else
    docker secret create "$1" "$2" >/dev/null
    echo "Secret criado:   $1"
  fi
}
create_secret wazuh_root_ca                "$certs/root-ca.pem"
create_secret wazuh_indexer_cert           "$certs/wazuh.indexer.pem"
create_secret wazuh_indexer_key            "$certs/wazuh.indexer-key.pem"
create_secret wazuh_admin_cert             "$certs/admin.pem"
create_secret wazuh_admin_key              "$certs/admin-key.pem"
create_secret wazuh_manager_cert           "$certs/wazuh.manager.pem"
create_secret wazuh_manager_key            "$certs/wazuh.manager-key.pem"
create_secret wazuh_dashboard_cert         "$certs/wazuh.dashboard.pem"
create_secret wazuh_dashboard_key          "$certs/wazuh.dashboard-key.pem"
create_secret wazuh_internal_users         "$out/internal_users.yml"
create_secret wazuh_indexer_admin_password "$out/indexer_admin_password.txt"
create_secret wazuh_kibanaserver_password  "$out/kibanaserver_password.txt"
create_secret wazuh_api_password           "$out/api_password.txt"
create_secret wazuh_authd_pass             "$out/authd_pass.txt"

cat <<EOF

Pronto. Próximo passo:
  docker stack deploy -c docker-stack.wazuh.yml wazuh
Login no dashboard (https://192.168.9.50): usuário "admin", senha em
secrets/wazuh/indexer_admin_password.txt.
Senha de registro dos agentes (install-wazuh-agent.sh): secrets/wazuh/authd_pass.txt.
secrets/wazuh/certs/root-ca.key só serve para emitir certificados: guarde
fora do servidor e apague daqui.
EOF
