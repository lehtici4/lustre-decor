#!/usr/bin/env bash
# Valida ossec.conf, regras e decoders do repo NO manager em execução, antes
# do `docker service update --force wazuh_manager`. Sem sudo (grupo docker).
#
#   ./infra/scripts/wazuh-validar-regras.sh && docker service update --force wazuh_manager
#
# Copia os três arquivos para dentro do container (por cima das cópias que o
# init fez na última subida), roda `wazuh-analysisd -t` e, se der erro,
# restaura os anteriores — o manager em execução não é afetado: o analysisd
# só relê os arquivos ao reiniciar. Pega erros como o da regra 100225
# (regex inválida), que derrubou o manager em 26/10/2026.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$script_dir/../.." && pwd)"
M=$(docker ps -qf name=wazuh_manager | head -1)
[ -n "$M" ] || { echo "manager não está rodando" >&2; exit 1; }

files=(
  "infra/wazuh/manager/ossec.conf:/var/ossec/etc/ossec.conf"
  "infra/wazuh/manager/local_rules.xml:/var/ossec/etc/rules/local_rules.xml"
  "infra/wazuh/manager/local_decoder.xml:/var/ossec/etc/decoders/local_decoder.xml"
)
for f in "${files[@]}"; do
  dst="${f#*:}"
  docker exec "$M" cp -p "$dst" "$dst.validar-bak"
  docker cp "$repo/${f%%:*}" "$M:$dst"
  docker exec "$M" chown root:wazuh "$dst"
  docker exec "$M" chmod 660 "$dst"
done

if out=$(docker exec "$M" /var/ossec/bin/wazuh-analysisd -t 2>&1); then
  echo "OK: configuração, regras e decoders válidos."
  for f in "${files[@]}"; do docker exec "$M" rm -f "${f#*:}.validar-bak"; done
else
  echo "ERRO — nada foi aplicado; arquivos anteriores restaurados:" >&2
  printf '%s\n' "$out" | grep -E "ERROR|CRITICAL" >&2 || printf '%s\n' "$out" >&2
  for f in "${files[@]}"; do
    dst="${f#*:}"
    docker exec "$M" mv -f "$dst.validar-bak" "$dst"
  done
  exit 1
fi
