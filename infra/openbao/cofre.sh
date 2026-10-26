# Funções para usar o cofre a partir do HOST da .50, sem instalar o binário:
# o CLI `bao` roda dentro do próprio container do cofre.
#
#   source infra/openbao/cofre.sh
#   cofre_login leticia        # pede a senha sem eco e exporta BAO_TOKEN
#   bao kv get lustre/app      # qualquer comando do CLI
#   cofre_logout               # revoga o token e limpa a variável
#
# O token passa para o container por `-e BAO_TOKEN` SEM valor: o docker lê
# do ambiente de quem chama, então ele não aparece na linha de comando (ps).

cofre_container() {
  local c
  c=$(docker ps -qf name=cofre_openbao | head -1)
  [ -n "$c" ] || { echo "cofre: container cofre_openbao não está rodando" >&2; return 1; }
  printf '%s' "$c"
}

bao() {
  local c
  c=$(cofre_container) || return 1
  docker exec -i -e BAO_TOKEN "$c" bao "$@"
}

cofre_login() {
  local u="${1:-}" p resp
  [ -n "$u" ] || { read -rp "Usuário do cofre: " u; }
  read -rsp "Senha do cofre ($u): " p; echo
  resp=$(printf '%s' "$p" | env -u BAO_TOKEN bash -c "$(declare -f cofre_container bao); bao write -format=json auth/userpass/login/$u password=-") || { unset p; echo "cofre: login falhou" >&2; return 1; }
  unset p
  BAO_TOKEN=$(printf '%s' "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin)["auth"]["client_token"])')
  export BAO_TOKEN
  echo "cofre: logado como $u (token válido por 8 h)" >&2
}

cofre_logout() {
  [ -n "${BAO_TOKEN:-}" ] && bao token revoke -self >/dev/null 2>&1
  unset BAO_TOKEN
}
