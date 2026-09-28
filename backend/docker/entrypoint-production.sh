#!/bin/sh
set -eu

# TLS obrigatório (mTLS com o waf) — sem os três arquivos o backend NÃO sobe,
# em vez de cair silenciosamente para HTTP em texto claro. Checado antes de
# tudo para falhar rápido. Ver docker/gunicorn.conf.py e
# infra/scripts/generate-internal-pki.sh.
for var in BACKEND_TLS_CERT_FILE BACKEND_TLS_KEY_FILE BACKEND_TLS_CA_FILE; do
    eval "file=\${$var:-}"
    if [ -z "$file" ] || [ ! -r "$file" ]; then
        echo "ERRO: $var ausente ou ilegível ('$file') — o backend só sobe com TLS." >&2
        exit 1
    fi
done

# Migrações exigem DDL: usam o papel dono do banco, não o papel de execução
# normal (restrito a DML) usado pelo Gunicorn abaixo. A conexão com o
# Postgres também é TLS (verify-full) — ver DATABASES em config/settings/base.py.
POSTGRES_USER="$POSTGRES_MIGRATION_USER" \
POSTGRES_PASSWORD_FILE="$POSTGRES_MIGRATION_PASSWORD_FILE" \
    python manage.py migrate --noinput

python manage.py collectstatic --noinput

exec gunicorn --config=docker/gunicorn.conf.py config.wsgi:application
