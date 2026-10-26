#!/usr/bin/env bash
# Configuração do cofre depois da cerimônia de inicialização e do unseal.
# Idempotente: pode rodar de novo (só faz o que falta).
#
#   sudo ./infra/scripts/configurar-cofre.sh
#
# Pede o ROOT TOKEN sem eco (ou usa BAO_TOKEN do ambiente) e:
#   1) habilita o KV v2 em "lustre/";
#   2) grava a política "admin" (infra/openbao/policies/admin.hcl);
#   3) habilita userpass e cria os usuários (USUARIOS, padrão "leticia nathan"),
#      pedindo a senha inicial de cada um sem eco;
#   4) importa para o cofre os segredos que hoje só existem como Docker
#      Secrets (valores nunca aparecem na tela);
#   5) testa o login do primeiro usuário e oferece revogar o root token.
#
# sudo: os valores são lidos no HOST, em
# /var/lib/docker/containers/<container>/mounts/secrets/<id do secret> — e não
# com `docker exec ... cat`, que dispararia a regra do Falco de secret lido
# (100212) e, com a resposta ativa instalada, recriaria os containers.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Rode com sudo." >&2; exit 1; }
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$script_dir/../.." && pwd)"
# shellcheck source=../openbao/cofre.sh
. "$repo/infra/openbao/cofre.sh"
USUARIOS="${USUARIOS:-leticia nathan}"

if [ -z "${BAO_TOKEN:-}" ]; then
  read -rsp "Root token do cofre: " BAO_TOKEN; echo
fi
export BAO_TOKEN
bao token lookup >/dev/null 2>&1 || { echo "Token inválido ou cofre selado (bao status)." >&2; exit 1; }

tem_chave() {  # tem_chave <json> <chave>
  python3 -c 'import json,sys; sys.exit(0 if sys.argv[1] in json.load(sys.stdin) else 1)' "$1"
}

# --- 1) KV v2 ---------------------------------------------------------------
if bao secrets list -format=json | tem_chave "lustre/"; then
  echo "KV lustre/ já habilitado."
else
  bao secrets enable -path=lustre -description="Segredos do Lustre Decor" kv-v2
fi

# --- 2) política --------------------------------------------------------------
bao policy write admin - < "$repo/infra/openbao/policies/admin.hcl"

# --- 3) usuários ----------------------------------------------------------------
if bao auth list -format=json | tem_chave "userpass/"; then
  echo "userpass já habilitado."
else
  bao auth enable -description="Administradores (Letícia, Nathan)" userpass
fi
primeiro="" senha_primeiro=""
for u in $USUARIOS; do
  [ -z "$primeiro" ] && primeiro="$u"
  if bao read auth/userpass/users/"$u" >/dev/null 2>&1; then
    echo "Usuário $u já existe."
    continue
  fi
  while :; do
    read -rsp "Senha inicial de '$u' (mín. 14 caracteres): " p1; echo
    read -rsp "Repita: " p2; echo
    [ "$p1" = "$p2" ] && [ "${#p1}" -ge 14 ] && break
    echo "Não confere ou é curta demais; de novo."
  done
  printf '%s' "$p1" | bao write auth/userpass/users/"$u" password=- \
    token_policies=admin token_ttl=8h token_max_ttl=12h >/dev/null
  [ "$u" = "$primeiro" ] && senha_primeiro="$p1"
  unset p1 p2
  echo "Usuário $u criado (política admin, token de 8 h)."
done

# --- 4) importar os Docker Secrets atuais ------------------------------------------
# <caminho KV> <campo> <docker secret> <serviço que o monta>
importar() {
  local path="$1" field="$2" secret="$3" svc="$4" sid c cid arq op
  if bao kv get -field="$field" "$path" >/dev/null 2>&1; then
    echo "  já no cofre: $path -> $field"; return
  fi
  sid=$(docker secret inspect -f '{{.ID}}' "$secret" 2>/dev/null) || { echo "  AVISO: secret $secret não existe; pulei"; return; }
  c=$(docker ps -qf name="$svc" | head -1)
  [ -n "$c" ] || { echo "  AVISO: serviço $svc parado; pulei $secret"; return; }
  cid=$(docker inspect -f '{{.Id}}' "$c")
  arq="/var/lib/docker/containers/$cid/mounts/secrets/$sid"
  [ -f "$arq" ] || { echo "  AVISO: $secret não encontrado em $arq; pulei"; return; }
  if bao kv get "$path" >/dev/null 2>&1; then op=patch; else op=put; fi
  bao kv "$op" "$path" "$field=-" < "$arq" >/dev/null
  echo "  importado: $secret -> $path ($field)"
}
echo "Importando segredos para o cofre:"
importar lustre/app      django_secret_key      django_secret_key            lustre_decor_backend
importar lustre/postgres superuser_password     postgres_password            lustre_decor_postgres
importar lustre/postgres runtime_password       postgres_runtime_password    lustre_decor_postgres
importar lustre/pki      backend_tls_key        backend_tls_key              lustre_decor_backend
importar lustre/pki      postgres_tls_key       postgres_tls_key             lustre_decor_postgres
importar lustre/wazuh    indexer_admin_password wazuh_indexer_admin_password wazuh_manager
importar lustre/wazuh    api_password           wazuh_api_password           wazuh_manager
importar lustre/wazuh    authd_password         wazuh_authd_pass             wazuh_manager
importar lustre/wazuh    kibanaserver_password  wazuh_kibanaserver_password  wazuh_dashboard
importar lustre/wazuh-pki indexer_key           wazuh_indexer_key            wazuh_indexer
importar lustre/wazuh-pki admin_key             wazuh_admin_key              wazuh_indexer
importar lustre/wazuh-pki manager_key           wazuh_manager_key            wazuh_manager
importar lustre/wazuh-pki dashboard_key         wazuh_dashboard_key          wazuh_dashboard

# --- 5) testar o login e revogar o root ------------------------------------------
if [ -n "$senha_primeiro" ]; then
  if printf '%s' "$senha_primeiro" | env -u BAO_TOKEN bash -c "$(declare -f cofre_container bao); bao write -format=json auth/userpass/login/$primeiro password=-" >/dev/null; then
    echo "Login de $primeiro testado: OK."
  else
    echo "ERRO: login de $primeiro falhou — NÃO revogue o root token." >&2
    unset senha_primeiro; exit 1
  fi
fi
unset senha_primeiro

if [ "$(bao token lookup -format=json | python3 -c 'import json,sys; print(" ".join(json.load(sys.stdin)["data"]["policies"]))')" = "root" ]; then
  read -rp "Revogar o ROOT TOKEN agora? (recomendado; um novo só com 2 chaves de unseal) [s/N] " r
  if [ "${r,,}" = "s" ]; then
    bao token revoke -self
    unset BAO_TOKEN
    echo "Root token revogado. Daqui em diante: source infra/openbao/cofre.sh; cofre_login <usuário>"
  fi
fi
echo "Pronto. Próximo: ./infra/scripts/cofre-para-swarm.sh (docs/cofre.md)."
