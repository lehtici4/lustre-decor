#!/bin/sh
# Executado automaticamente pelo Postgres (docker-entrypoint-initdb.d) somente
# na primeira inicialização de um volume novo. Cria um papel de aplicação
# restrito a DML (sem DDL), usado pelo backend em execução normal. Migrações
# continuam usando o papel dono do banco ($POSTGRES_USER), que tem privilégio
# total — ver backend/docker/entrypoint*.sh.
set -eu

RUNTIME_PASSWORD="$(cat /run/secrets/postgres_runtime_password)"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'lustre_app_runtime') THEN
            CREATE ROLE lustre_app_runtime WITH LOGIN PASSWORD '${RUNTIME_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO lustre_app_runtime;
    GRANT USAGE ON SCHEMA public TO lustre_app_runtime;

    ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_USER} IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lustre_app_runtime;
    ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_USER} IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO lustre_app_runtime;
EOSQL
