import logging

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.catalog.models import Product


@pytest.fixture
def existing_user(db):
    return User.objects.create_user(username="cliente", password="uma-senha-forte-123")


def test_throttled_login_logs_request_throttled(client, existing_user, caplog):
    caplog.set_level(logging.WARNING, logger="apps.core")

    for _ in range(6):
        client.post(
            reverse("auth-login"),
            {"username": "cliente", "password": "senha-errada"},
            content_type="application/json",
        )

    assert any(record.getMessage() == "request_throttled" for record in caplog.records)


def test_anonymous_request_to_protected_endpoint_logs_permission_denied(client, db, caplog):
    caplog.set_level(logging.WARNING, logger="apps.core")

    client.get(reverse("cart-detail"))

    assert any(record.getMessage() == "permission_denied" for record in caplog.records)


def test_admin_change_logs_admin_action(client, db, caplog):
    admin_user = User.objects.create_superuser(username="admin_log", password="uma-senha-forte-123")
    product = Product.objects.create(name="Vaso Log", price="10.00")

    from django.contrib.admin.models import ADDITION, LogEntry
    from django.contrib.contenttypes.models import ContentType

    caplog.set_level(logging.INFO, logger="apps.core")

    LogEntry.objects.log_action(
        user_id=admin_user.id,
        content_type_id=ContentType.objects.get_for_model(Product).id,
        object_id=product.id,
        object_repr=str(product),
        action_flag=ADDITION,
        change_message="Criado via teste",
    )

    assert any(record.getMessage() == "admin_action" for record in caplog.records)
