#!/usr/bin/env bash
# Instala o Falco no HOST (pacote apt, driver modern_ebpf) e aplica a
# configuração + regras do Lustre Decor. Rodar nos DOIS hosts (DMZ .34 e
# interna .50). Etapa 3.4/3.5 do plano. Ver docs/deteccao.md.
#
# Uso (na raiz do repositório, como root):
#   sudo ./infra/scripts/install-falco.sh                         # 0.45.1 (padrão)
#   sudo FALCO_VERSION=0.46.0 ./infra/scripts/install-falco.sh   # outra versão
#
# A versão é fixa por padrão (a mesma nas duas VMs) e o pacote fica em
# "apt-mark hold": uma atualização automática do Ubuntu não troca o sensor
# (nem o driver) no meio dos testes — mesmo raciocínio do hold do docker-ce.
# Arquivos de configuração já existentes em /etc/falco são mantidos
# (--force-confold): o postinst não para numa pergunta interativa nem
# sobrescreve a configuração do Lustre Decor.
#
# Por que no host e não em container: o sensor não pode depender do daemon
# Docker que ele vigia, e rodar Falco em container privilegiado contradiria o
# modelo de adversário (T1611 — Escape to Host).
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Rode como root (sudo)." >&2
    exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$REPO_DIR/infra/falco"
FALCO_VERSION="${FALCO_VERSION:-0.45.1}"
KEYRING=/usr/share/keyrings/falco-archive-keyring.gpg

echo "==> Pré-requisitos do modern_ebpf (kernel >= 5.8 com BTF)"
KERNEL="$(uname -r)"
KMAJ="${KERNEL%%.*}"
KMIN="${KERNEL#*.}"; KMIN="${KMIN%%.*}"
if (( KMAJ < 5 || (KMAJ == 5 && KMIN < 8) )); then
    echo "Kernel $KERNEL < 5.8: modern_ebpf não suportado." >&2
    exit 1
fi
if [[ ! -r /sys/kernel/btf/vmlinux ]]; then
    echo "Sem /sys/kernel/btf/vmlinux (BTF): modern_ebpf não suportado neste kernel." >&2
    exit 1
fi
echo "    kernel $KERNEL, BTF ok"

echo "==> Repositório apt do Falco"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q curl gnupg ca-certificates
if [[ ! -s "$KEYRING" ]]; then
    curl -fsSL https://falco.org/repo/falcosecurity-packages.asc | gpg --dearmor -o "$KEYRING"
fi
echo "deb [signed-by=$KEYRING] https://download.falco.org/packages/deb stable main" \
    > /etc/apt/sources.list.d/falcosecurity.list
apt-get update -q

echo "==> Instalando o pacote (driver modern_ebpf, sem falcoctl de atualização automática)"
# FALCO_FRONTEND/FALCO_DRIVER_CHOICE/FALCOCTL_ENABLED: respostas do postinst
# do pacote, sem a tela interativa do dialog. FALCOCTL_ENABLED=no: as regras
# ficam na versão instalada (reprodutível entre os testes), sem baixar
# atualização em segundo plano.
if ! apt-cache madison falco | awk '{print $3}' | grep -qx "$FALCO_VERSION"; then
    echo "Versão $FALCO_VERSION do Falco não está no repositório. Disponíveis:" >&2
    apt-cache madison falco | awk '{print "  " $3}' | head -5 >&2
    exit 1
fi
apt-mark unhold falco >/dev/null 2>&1 || true
FALCO_FRONTEND=noninteractive FALCO_DRIVER_CHOICE=modern_ebpf FALCOCTL_ENABLED=no \
    apt-get install -y -q --allow-downgrades \
        -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
        "falco=$FALCO_VERSION"
apt-mark hold falco
falco --version | head -1

echo "==> Configuração e regras do Lustre Decor"
install -d -m 0755 /etc/falco/config.d /etc/falco/rules.d
install -m 0644 "$SRC/config.d/lustre-decor.yaml" /etc/falco/config.d/lustre-decor.yaml
install -m 0644 "$SRC/rules.d/lustre_decor_rules.yaml" /etc/falco/rules.d/lustre_decor_rules.yaml
install -d -m 0750 /var/log/falco
install -m 0644 "$SRC/logrotate/falco" /etc/logrotate.d/falco

echo "==> Validando configuração e regras (falco --dry-run)"
if ! falco --dry-run -o engine.kind=modern_ebpf; then
    echo "!! Validação falhou (erro acima). As regras do Lustre Decor foram removidas" >&2
    echo "!! e o serviço NÃO foi iniciado. Corrija e rode o script de novo — ou, para" >&2
    echo "!! subir só com as regras oficiais: systemctl enable --now falco-modern-bpf" >&2
    rm -f /etc/falco/rules.d/lustre_decor_rules.yaml
    exit 1
fi

echo "==> Serviço"
systemctl daemon-reload
systemctl enable falco-modern-bpf.service
systemctl restart falco-modern-bpf.service
sleep 5
systemctl --no-pager --lines=0 status falco-modern-bpf.service || true

cat <<'EOF'

Falco ativo. Teste rápido (deve gerar alerta em /var/log/falco/falco.json):
  docker exec "$(docker ps -qf name=lustre_decor | head -1)" sh -c 'id'
  tail -n 3 /var/log/falco/falco.json | python3 -m json.tool

Alertas também vão para o journal:  journalctl -u falco-modern-bpf -f
EOF
