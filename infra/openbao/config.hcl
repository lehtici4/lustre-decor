# Cofre de segredos do Lustre Decor (OpenBao) — configuração do servidor.
# Montado em /openbao/config/cofre.hcl pelo docker-stack.cofre.yml.
# Ver docs/cofre.md.

ui        = true
log_level = "info"

# Integrated storage (raft): a recomendação é desligar o mlock — ele não
# combina com os arquivos mapeados em memória do raft. Consequência: com swap
# ativo na VM, páginas do processo podem ir para o disco (registrado em
# docs/cofre.md, "Limites").
disable_mlock = true

api_addr     = "https://192.168.9.50:8200"
cluster_addr = "https://127.0.0.1:8201"

storage "raft" {
  path    = "/openbao/file"
  node_id = "cofre-1"
}

listener "tcp" {
  address         = "0.0.0.0:8200"
  cluster_address = "127.0.0.1:8201"
  tls_cert_file   = "/run/secrets/cofre_tls_cert"
  tls_key_file    = "/run/secrets/cofre_tls_key"
  tls_min_version = "tls12"
}

# Auditoria declarada aqui (não pela API): existe desde a primeira subida e
# não pode ser desligada por quem só tem acesso à API. Cada requisição e
# resposta vira uma linha JSON; valores de segredo saem como HMAC, nunca em
# claro. O diretório é /var/log/openbao no host, lido pelo agente Wazuh.
audit "file" "arquivo" {
  description = "Auditoria em arquivo, coletada pelo agente Wazuh do host"
  options {
    file_path = "/openbao/logs/audit.log"
  }
}
