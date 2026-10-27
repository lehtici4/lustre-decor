"""Eventos de segurança que alimentam o Wazuh e o Fail2ban (VULN-06 e VULN-07
do pentest). Regras correspondentes em infra/wazuh/manager/local_rules.xml."""

import logging

import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts import roles
from apps.catalog.models import Product
from apps.orders.models import Cart, CartItem, Order
from apps.stores.models import Store
from tests.helpers import login_with_mfa

PASSWORD = "uma-senha-forte-123"
REAL_IP = "203.0.113.7"


def events(caplog, name):
    return [r for r in caplog.records if r.getMessage() == name]


def make_user(username, *groups, **extra):
    user = User.objects.create_user(username=username, email=f"{username}@example.com", password=PASSWORD, **extra)
    user.groups.set([Group.objects.get(name=g) for g in groups])
    return user


@pytest.fixture
def customer(db):
    return make_user("cliente1", roles.CLIENTE)


@pytest.fixture
def other_customer(db):
    return make_user("cliente2", roles.CLIENTE)


@pytest.fixture(autouse=True)
def _capture(caplog):
    caplog.set_level(logging.INFO)


# ---- VULN-06: toda falha de login vira login_failed --------------------------


def test_wrong_password_logs_login_failed_once_with_real_ip(client, customer, caplog):
    client.post(
        reverse("auth-login"),
        {"username": "cliente1", "password": "errada"},
        content_type="application/json",
        HTTP_X_FORWARDED_FOR=f"10.9.9.9, {REAL_IP}",
    )

    records = events(caplog, "login_failed")
    assert len(records) == 1, "sinal e serviço não podem duplicar o evento"
    assert records[0].origin == REAL_IP
    assert records[0].reason == "bad_credentials"


def test_password_is_never_logged(client, customer, caplog):
    client.post(
        reverse("auth-login"),
        {"username": "cliente1", "password": "SenhaSecreta#999"},
        content_type="application/json",
    )

    assert "SenhaSecreta#999" not in caplog.text
    record = events(caplog, "login_failed")[0]
    assert "SenhaSecreta#999" not in str(record.__dict__)


@pytest.mark.parametrize(
    "body,content_type",
    [
        ({"username": "cliente1"}, "application/json"),  # campo faltando
        ({"user": "x", "pass": "y"}, "application/json"),  # nomes errados (hydra mal configurado)
        ("{nao-e-json", "application/json"),  # JSON quebrado
        ("username=a&password=b", "text/plain"),  # content-type não suportado
    ],
)
def test_malformed_login_request_logs_login_failed(client, db, caplog, body, content_type):
    response = client.post(
        reverse("auth-login"), body, content_type=content_type, HTTP_X_FORWARDED_FOR=REAL_IP
    )

    assert response.status_code in (400, 415)
    records = events(caplog, "login_failed")
    assert len(records) == 1
    assert records[0].reason == "invalid_request"
    assert records[0].origin == REAL_IP


def test_malformed_mfa_request_logs_login_failed(client, db, caplog):
    response = client.post(reverse("auth-mfa-verify"), {"token": "<script>"}, content_type="application/json")

    assert response.status_code == 400
    assert events(caplog, "login_failed")[0].reason == "invalid_request"


def test_failed_password_outside_the_api_is_logged(customer, caplog):
    # Admin / django-two-factor autenticam pelo mesmo authenticate(): o sinal cobre.
    request = RequestFactory().post("/account/login/", REMOTE_ADDR=REAL_IP)

    assert authenticate(request, username="cliente1", password="errada") is None

    record = events(caplog, "login_failed")[0]
    assert record.path == "/account/login/"
    assert record.origin == REAL_IP


def test_invalid_register_request_is_not_a_login_failure(client, db, caplog):
    client.post(reverse("auth-register"), {"username": "x"}, content_type="application/json")

    assert events(caplog, "login_failed") == []


# ---- VULN-07: enumeração e escalonamento ficam visíveis -----------------------


def test_nonexistent_order_logs_object_not_found(client, customer, caplog):
    login_with_mfa(client, customer)

    response = client.get(reverse("order-detail", args=[999999]))

    assert response.status_code == 404
    record = events(caplog, "object_not_found")[0]
    assert (record.user_id, record.model, record.object_id) == (customer.id, "Order", 999999)


def test_nonexistent_cart_item_logs_object_not_found(client, customer, caplog):
    login_with_mfa(client, customer)

    client.delete(reverse("cart-item-detail", args=[424242]))

    assert events(caplog, "object_not_found")[0].model == "CartItem"


def test_other_users_order_still_logs_forbidden_object_access(client, customer, other_customer, caplog):
    order = Order.objects.create(user=other_customer, total="10.00")
    login_with_mfa(client, customer)

    response = client.get(reverse("order-detail", args=[order.id]))

    assert response.status_code == 404
    assert events(caplog, "forbidden_object_access")
    assert events(caplog, "object_not_found") == []


def test_own_cart_item_logs_nothing_suspicious(client, customer, caplog):
    product = Product.objects.create(name="Vaso", price="10.00")
    item = CartItem.objects.create(cart=Cart.objects.create(user=customer), product=product, quantity=1)
    login_with_mfa(client, customer)

    client.delete(reverse("cart-item-detail", args=[item.id]))

    assert events(caplog, "object_not_found") == []
    assert events(caplog, "forbidden_object_access") == []


def test_partner_nonexistent_product_logs_object_not_found(client, db, caplog):
    store = Store.objects.create(name="Loja A")
    partner = make_user("parceiro_a", roles.PARCEIRO)
    store.members.add(partner)
    login_with_mfa(client, partner)

    response = client.get(reverse("partner-product-detail", args=[777777]))

    assert response.status_code == 404
    record = events(caplog, "object_not_found")[0]
    assert (record.model, record.scope) == ("Product", "partner")


def test_customer_on_partner_api_logs_privileged_route_denied(client, customer, caplog):
    login_with_mfa(client, customer)

    response = client.get(reverse("partner-products"))

    assert response.status_code == 403
    record = events(caplog, "privileged_route_denied")[0]
    assert record.user_id == customer.id
    assert record.path == reverse("partner-products")
    assert events(caplog, "permission_denied") == []


def test_anonymous_on_partner_api_is_plain_permission_denied(client, db, caplog):
    client.get(reverse("partner-products"))

    assert events(caplog, "privileged_route_denied") == []
    assert events(caplog, "permission_denied")


def test_customer_on_django_admin_logs_privileged_route_denied(client, customer, caplog):
    login_with_mfa(client, customer)

    client.get("/admin/auth/user/")

    record = events(caplog, "privileged_route_denied")[0]
    assert (record.user_id, record.reason) == (customer.id, "not_staff")


def test_staff_without_second_factor_on_admin_is_flagged(client, db, caplog):
    staff = make_user("staff1", roles.ADMINISTRADOR, is_staff=True)
    client.force_login(staff)  # sessão só com senha, sem OTP

    client.get("/admin/")

    assert events(caplog, "privileged_route_denied")[0].reason == "otp_not_verified"


def test_verified_staff_on_admin_logs_nothing(client, db, caplog):
    staff = make_user("staff2", roles.ADMINISTRADOR, is_staff=True)
    login_with_mfa(client, staff)

    client.get("/admin/")

    assert events(caplog, "privileged_route_denied") == []


def test_anonymous_on_admin_login_page_logs_nothing(client, db, caplog):
    client.get("/admin/login/")

    assert events(caplog, "privileged_route_denied") == []
