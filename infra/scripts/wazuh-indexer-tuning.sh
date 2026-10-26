#!/usr/bin/env bash
# Ajustes do Wazuh indexer para nó único (VM interna .50). Sem sudo: grupo
# docker. Idempotente — pode rodar de novo. Ver docs/wazuh.md "Desempenho".
#
#   ./infra/scripts/wazuh-indexer-tuning.sh
#
# 1) Template de prioridade maior que o oficial ("wazuh", order 0) para os
#    índices diários de alertas/arquivos: 1 shard (o oficial cria 3 por dia —
#    num nó único isso só multiplica shards e consome heap), 0 réplicas e
#    refresh a cada 10 s em vez de 1 s (menos CPU/disco; alerta aparece no
#    dashboard em até 10 s). Vale para os índices criados a partir de amanhã.
# 2) Réplicas = 0 nos índices wazuh-* existentes: com um nó só a réplica nunca
#    é alocada e o cluster fica amarelo.
#
# Desfazer o 1):  DELETE /_template/lustre-single-node (mesma função idx).
set -euo pipefail

M=$(docker ps -qf name=wazuh_manager | head -1)
I=$(docker ps -qf name=wazuh_indexer | head -1)
[ -n "$M" ] && [ -n "$I" ] || { echo "manager/indexer não estão rodando" >&2; exit 1; }
PASS=$(docker exec "$M" cat /run/secrets/wazuh_indexer_admin_password)

idx() {  # idx METHOD PATH [JSON]
  local args=(-s --max-time 60 -K - --cacert /usr/share/wazuh-indexer/config/certs/root-ca.pem -X "$1" "https://wazuh.indexer:9200$2")
  [ $# -ge 3 ] && args+=(-H 'Content-Type: application/json' --data-raw "$3")
  printf 'user = "admin:%s"\n' "$PASS" | docker exec -i "$I" curl "${args[@]}"
  echo
}

echo "== template lustre-single-node"
idx PUT /_template/lustre-single-node '{
  "order": 10,
  "index_patterns": ["wazuh-alerts-4.x-*", "wazuh-archives-4.x-*"],
  "settings": {
    "index.number_of_shards": "1",
    "index.number_of_replicas": "0",
    "index.refresh_interval": "10s"
  }
}'

echo "== réplicas = 0 nos índices wazuh-* existentes"
idx PUT '/wazuh-*/_settings?expand_wildcards=open' '{"index": {"number_of_replicas": 0}}'

echo "== conferência"
idx GET '/_template/lustre-single-node?filter_path=*.order,*.settings'
idx GET '/_cluster/health?filter_path=status,active_shards,unassigned_shards'
