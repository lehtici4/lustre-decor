# Política "admin" do cofre (Letícia e Nathan). Administra conteúdo e
# configuração sem ser root: o root token só existe na cerimônia inicial e é
# revogado em seguida (docs/cofre.md). Não dá acesso a sys/raw nem a
# sys/rotate, que continuam exigindo root.

# Segredos do projeto (KV v2)
path "lustre/*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list"]
}

# Motores de segredos e métodos de autenticação
path "sys/mounts" {
  capabilities = ["read"]
}
path "sys/mounts/*" {
  capabilities = ["create", "read", "update", "delete", "sudo"]
}
path "sys/auth" {
  capabilities = ["read"]
}
path "sys/auth/*" {
  capabilities = ["create", "read", "update", "delete", "sudo"]
}
path "auth/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}

# Políticas
path "sys/policies/acl" {
  capabilities = ["list"]
}
path "sys/policies/acl/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Autoridade certificadora do SSH (etapa 2)
path "ssh-client-signer/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Operação: selar em emergência, ver auditoria e saúde
path "sys/seal" {
  capabilities = ["update", "sudo"]
}
path "sys/audit" {
  capabilities = ["read", "sudo"]
}
path "sys/health" {
  capabilities = ["read"]
}
