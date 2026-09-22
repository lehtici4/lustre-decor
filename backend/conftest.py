import os

import pytest


@pytest.fixture(scope="session")
def django_db_modify_db_settings():
    """Criar/destruir o banco de teste exige DDL (CREATEDB), privilégio que o
    papel de execução normal do backend não tem (ver infra/postgres/init-app-role.sh).
    Usa o papel dono do banco só para esta finalidade de teste."""
    from django.conf import settings

    settings.DATABASES["default"]["USER"] = os.environ["POSTGRES_MIGRATION_USER"]

    password_file = os.environ["POSTGRES_MIGRATION_PASSWORD_FILE"]
    with open(password_file, encoding="utf-8") as fh:
        settings.DATABASES["default"]["PASSWORD"] = fh.read().strip()


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """O throttling do DRF guarda contadores no cache (LocMem, compartilhado
    no processo). Sem limpar, os logins de um teste consomem a cota do
    seguinte — relevante desde que o fluxo com MFA faz vários logins por teste."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
