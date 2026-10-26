#!/usr/bin/env bash
# Diagnóstico de desempenho do Wazuh na VM interna (.50). NÃO precisa de sudo:
# basta estar no grupo docker. Só lê — não altera nada.
#
#   ./infra/scripts/wazuh-diagnostico.sh              # imprime na tela
#   ./infra/scripts/wazuh-diagnostico.sh > ~/wazuh-diag.txt 2>&1
#
# O que procurar na saída está em docs/wazuh.md, seção "Desempenho".
# A senha do admin do indexer é lida do secret dentro do container do manager
# e passada ao curl por stdin (-K -): não aparece na tela nem em `ps`.
set -uo pipefail

sec() { printf '\n===== %s =====\n' "$*"; }

M=$(docker ps -qf name=wazuh_manager | head -1)
I=$(docker ps -qf name=wazuh_indexer | head -1)

idx() {  # idx METHOD PATH [JSON]
  local method=$1 path=$2 body=${3:-}
  [ -n "$M" ] && [ -n "$I" ] || { echo "(indexer/manager não estão rodando)"; return 1; }
  local pass
  pass=$(docker exec "$M" cat /run/secrets/wazuh_indexer_admin_password 2>/dev/null) || { echo "(sem acesso ao secret do admin)"; return 1; }
  if [ -n "$body" ]; then
    printf 'user = "admin:%s"\n' "$pass" | docker exec -i "$I" curl -s --max-time 60 -K - \
      --cacert /usr/share/wazuh-indexer/config/certs/root-ca.pem \
      -H 'Content-Type: application/json' -X "$method" "https://wazuh.indexer:9200$path" --data-raw "$body"
  else
    printf 'user = "admin:%s"\n' "$pass" | docker exec -i "$I" curl -s --max-time 60 -K - \
      --cacert /usr/share/wazuh-indexer/config/certs/root-ca.pem \
      -X "$method" "https://wazuh.indexer:9200$path"
  fi
}

# Resume a resposta de uma agregação: chave, contagem e sub-agregações.
buckets() {
  python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception as e:
    print("(resposta inválida:", e, ")"); sys.exit()
if "error" in d:
    print("ERRO:", json.dumps(d["error"])[:400]); sys.exit()
print("total no período:", d.get("hits", {}).get("total", {}).get("value"))
for name, agg in d.get("aggregations", {}).items():
    print("--", name)
    for b in agg.get("buckets", []):
        key = b.get("key_as_string", b.get("key"))
        subs = []
        for k, v in b.items():
            if isinstance(v, dict) and "buckets" in v:
                subs.append(k + "=" + ", ".join("%s(%d)" % (x.get("key"), x["doc_count"]) for x in v["buckets"]))
        print("  %8d  %s  %s" % (b["doc_count"], key, "  ".join(subs)))
'
}

sec "Host"
date; uptime; echo "CPUs: $(nproc)"
free -m
echo; echo "swap:"; swapon --show 2>/dev/null || cat /proc/swaps
echo; echo "pressão (PSI) — avg10/avg60 altos = a VM está esperando CPU/RAM/disco:"
for r in cpu memory io; do printf '%-7s ' "$r"; head -1 /proc/pressure/$r 2>/dev/null || echo "-"; done
echo; echo "vmstat 1 5 (si/so > 0 = usando swap; wa alto = disco):"
vmstat 1 5
echo; df -h / /var/lib/docker 2>/dev/null | uniq

sec "Containers (uso agora)"
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'

sec "Tarefas do Swarm (reinícios e erros)"
for s in wazuh_indexer wazuh_manager wazuh_dashboard lustre_decor_backend lustre_decor_postgres; do
  docker service ps "$s" --no-trunc --format '{{.Name}}  {{.CurrentState}}  {{.Error}}' 2>/dev/null | head -6
done

sec "Containers encerrados por OOM (limite de memória do serviço)"
docker ps -aq --filter name=wazuh_ --filter name=lustre_decor_ | while read -r c; do
  docker inspect -f '{{.Name}}  status={{.State.Status}}  OOMKilled={{.State.OOMKilled}}  exit={{.State.ExitCode}}  fim={{.State.FinishedAt}}' "$c"
done

sec "Indexer: saúde, heap, rejeições"
idx GET '/_cluster/health?pretty'
idx GET '/_nodes/stats/jvm,thread_pool,breaker?filter_path=nodes.*.jvm.mem.heap_used_percent,nodes.*.jvm.mem.heap_max_in_bytes,nodes.*.jvm.gc.collectors,nodes.*.thread_pool.write.rejected,nodes.*.thread_pool.search.rejected,nodes.*.breakers.parent.tripped&pretty'
echo; echo "shards abertos: $(idx GET '/_cat/shards?h=index' | wc -l)"
echo; echo "índices (maiores primeiro):"
idx GET '/_cat/indices?v&h=index,health,pri,rep,docs.count,store.size&s=store.size:desc' | head -25

sec "Alertas por hora (últimas 24 h)"
idx POST '/wazuh-alerts-*/_search' '{"size":0,"track_total_hits":true,"query":{"range":{"timestamp":{"gte":"now-24h"}}},"aggs":{"por_hora":{"date_histogram":{"field":"timestamp","fixed_interval":"1h"}}}}' | buckets

sec "Regras que mais geram alerta (24 h)"
idx POST '/wazuh-alerts-*/_search' '{"size":0,"track_total_hits":true,"query":{"range":{"timestamp":{"gte":"now-24h"}}},"aggs":{"regras":{"terms":{"field":"rule.id","size":20},"aggs":{"nivel":{"terms":{"field":"rule.level","size":1}},"desc":{"terms":{"field":"rule.description","size":1}},"agente":{"terms":{"field":"agent.name","size":3}}}}}}' | buckets

sec "Falco: regras e processos mais frequentes (24 h)"
idx POST '/wazuh-alerts-*/_search' '{"size":0,"track_total_hits":true,"query":{"bool":{"filter":[{"range":{"timestamp":{"gte":"now-24h"}}},{"exists":{"field":"data.priority"}}]}},"aggs":{"falco":{"terms":{"field":"data.rule","size":15},"aggs":{"proc":{"terms":{"field":"data.output_fields.proc.name","size":4}},"container":{"terms":{"field":"data.output_fields.container.name","size":3}},"agente":{"terms":{"field":"agent.name","size":2}}}}}}' | buckets

sec "Manager: processos, filas e descartes"
if [ -n "$M" ]; then
  docker exec "$M" /var/ossec/bin/wazuh-control status 2>/dev/null | grep -v 'not running' | head -20
  echo; echo "analysisd (events_dropped > 0 = perdeu eventos; queue_usage perto de 1 = sobrecarga):"
  docker exec "$M" sh -c 'grep -E "^(total_events_decoded|events_dropped|.*queue_usage|events_received)" /var/ossec/var/run/wazuh-analysisd.state 2>/dev/null' | head -20
  echo; echo "remoted:"
  docker exec "$M" sh -c 'cat /var/ossec/var/run/wazuh-remoted.state 2>/dev/null' | grep -vE '^#|^$' | head -10
  echo; echo "uso de disco dentro do manager:"
  docker exec "$M" sh -c 'du -sh /var/ossec/queue/vd /var/ossec/queue/vd_updater /var/ossec/queue/indexer /var/ossec/logs/alerts /var/ossec/logs/archives 2>/dev/null'
  echo; echo "ERROR/WARNING no ossec.log do manager (contagem e últimas):"
  docker exec "$M" sh -c 'grep -cE "ERROR|WARNING" /var/ossec/logs/ossec.log; grep -E "ERROR|WARNING" /var/ossec/logs/ossec.log | tail -15'
fi

sec "Fim"
echo "Configuração em vigor no manager (vuln-detection / syscheck / AR):"
[ -n "$M" ] && docker exec "$M" sh -c 'grep -A1 -E "<vulnerability-detection>|<syscheck>|<rootcheck>|<sca>" /var/ossec/etc/ossec.conf | grep -E "enabled|disabled"; grep -c "<active-response>" /var/ossec/etc/ossec.conf'
