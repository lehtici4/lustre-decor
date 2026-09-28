"""IP do cliente atrás do waf: throttling e logs usam o endereço que o Nginx
anexou ao X-Forwarded-For (o ÚLTIMO item), nunca um valor escolhido pelo
cliente. Sem isso, variar o X-Forwarded-For a cada tentativa burlava o
throttling de login do DRF (achado desta etapa)."""

import logging

import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def existing_user(db):
    return User.objects.create_user(username="cliente", password="uma-senha-forte-123")


def _login(client, xff):
    return client.post(
        reverse("auth-login"),
        {"username": "cliente", "password": "senha-errada"},
        content_type="application/json",
        HTTP_X_FORWARDED_FOR=xff,
    )


def test_spoofed_x_forwarded_for_does_not_bypass_login_throttle(client, existing_user):
    # O cliente forja um XFF diferente a cada tentativa; o waf anexa o IP real
    # (203.0.113.7) no fim, como faz $proxy_add_x_forwarded_for.
    for i in range(5):
        _login(client, f"10.0.0.{i}, 203.0.113.7")

    response = _login(client, "10.0.0.99, 203.0.113.7")

    assert response.status_code == 429


def test_login_failed_log_carries_real_client_ip(client, existing_user, caplog):
    caplog.set_level(logging.WARNING, logger="apps.core")

    _login(client, "6.6.6.6, 203.0.113.7")

    record = next(r for r in caplog.records if r.getMessage() == "login_failed")
    assert record.origin == "203.0.113.7"


def test_without_proxy_header_uses_remote_addr(client, existing_user, caplog):
    caplog.set_level(logging.WARNING, logger="apps.core")

    client.post(
        reverse("auth-login"),
        {"username": "cliente", "password": "senha-errada"},
        content_type="application/json",
        REMOTE_ADDR="198.51.100.4",
    )

    record = next(r for r in caplog.records if r.getMessage() == "login_failed")
    assert record.origin == "198.51.100.4"
