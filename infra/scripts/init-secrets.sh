#!/usr/bin/env bash
# Equivalente Linux/macOS de init-secrets.ps1 — mesma lógica (cria só o que
# faltar, nunca sobrescreve um segredo já existente), pensado pras VMs
# Ubuntu do laboratório, onde não há PowerShell.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_root="$(cd "$script_dir/../.." && pwd)"
secrets_dir="$workspace_root/secrets"

mkdir -p "$secrets_dir"

create_secret() {
  local name="$1" bytes="$2" target="$secrets_dir/$1"
  if [ -f "$target" ]; then
    echo "Preservado: $target"
    return
  fi
  # -A: sem quebras de linha na base64 (mesmo formato do init-secrets.ps1)
  openssl rand -base64 "$bytes" | tr -d '\n' > "$target"
  chmod 600 "$target"
  echo "Criado: $target"
}

create_secret "django_secret_key.txt" 48
create_secret "postgres_password.txt" 32
create_secret "postgres_runtime_password.txt" 32
