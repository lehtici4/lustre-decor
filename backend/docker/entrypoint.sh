#!/bin/sh
set -eu

# Migrações exigem DDL: usam o papel dono do banco, não o papel de execução
# normal (restrito a DML) usado pelo servidor abaixo.
POSTGRES_USER="$POSTGRES_MIGRATION_USER" \
POSTGRES_PASSWORD_FILE="$POSTGRES_MIGRATION_PASSWORD_FILE" \
    python manage.py migrate --noinput

exec python manage.py runserver 0.0.0.0:8000
