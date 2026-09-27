"""Papéis (cliente, parceiro, administrador, tester) e marketplace de lojas
parceiras. Ver apps/accounts/roles.py e docs/authorization.md."""

import logging

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.urls import reverse

from apps.accounts import roles
from apps.accounts.admin import LustreUserChangeForm
from apps.catalog.models import Product
from apps.orders.models import OrderItem
from apps.stores.admin import StoreAdminForm
from apps.stores.models import Store
from tests.helpers import login_with_mfa

PASSWORD = "uma-senha-forte-123"


def make_user(username, *groups, **extra):
    user = User.objects.create_user(username=username, email=f"{username}@example.com", password=PASSWORD, **extra)
    user.groups.set([Group.objects.get(name=g) for g in groups])
    return user


@pytest.fixture
def store_a(db):
    return Store.objects.create(name="Loja A")


@pytest.fixture
def store_b(db):
    return Store.objects.create(name="Loja B")


@pytest.fixture
def partner_a(store_a):
    user = make_user("parceiro_a", roles.PARCEIRO)
    store_a.members.add(user)
    return user


@pytest.fixture
def partner_b(store_b):
    user = make_user("parceiro_b", roles.PARCEIRO)
    store_b.members.add(user)
    return user


@pytest.fixture
def product_a(store_a):
    return Product.objects.create(name="Vaso A", price="50.00", store=store_a)


@pytest.fixture
def product_b(store_b):
    return Product.objects.create(name="Vaso B", price="70.00", store=store_b)


@pytest.fixture
def customer(db):
    return make_user("cliente1", roles.CLIENTE)


# ---- grupos e atribuição automática ------------------------------------------


def test_four_role_groups_exist_after_migrate(db):
    assert set(Group.objects.values_list("name", flat=True)) >= set(roles.ALL_ROLES)


def test_administrator_group_has_admin_permissions(db):
    perms = set(Group.objects.get(name=roles.ADMINISTRADOR).permissions.values_list("codename", flat=True))
    assert {"change_product", "add_store", "view_order", "change_user"} <= perms
    assert "delete_user" not in perms


def test_public_register_always_creates_customer(client, db):
    client.post(
        reverse("auth-register"),
        {"username": "novo", "email": "novo@example.com", "password": PASSWORD},
        content_type="application/json",
    )
    user = User.objects.get(username="novo")

    assert roles.user_roles(user) == [roles.CLIENTE]
    assert not user.is_staff
    assert not roles.is_partner(user)


def test_register_ignores_attempt_to_send_privileges(client, db):
    client.post(
        reverse("auth-register"),
        {"username": "espertinho", "email": "e@example.com", "password": PASSWORD, "is_staff": True, "roles": ["administrador"]},
        content_type="application/json",
    )
    user = User.objects.get(username="espertinho")

    assert not user.is_staff
    assert roles.user_roles(user) == [roles.CLIENTE]


def test_me_exposes_roles(client, partner_a):
    login_with_mfa(client, partner_a)

    body = client.get(reverse("auth-me")).json()

    assert body["roles"] == [roles.PARCEIRO]
    assert body["is_partner"] is True


# ---- tester: igual a cliente, nunca privilegiado ------------------------------


def test_tester_account_is_customer_plus_tester_only(db):
    call_command("seed_test_user")
    tester = User.objects.get(username="teste@pucparana.com")

    assert roles.user_roles(tester) == [roles.CLIENTE, roles.TESTER]
    assert not tester.is_staff and not tester.is_superuser


def test_exempt_account_never_gets_privilege_even_if_forced(store_a):
    call_command("seed_test_user")
    tester = User.objects.get(username="teste@pucparana.com")
    # Simula alguém forçando direto no banco (fora do Admin):
    tester.is_staff = True
    tester.save()
    tester.groups.add(Group.objects.get(name=roles.PARCEIRO), Group.objects.get(name=roles.ADMINISTRADOR))
    store_a.members.add(tester)

    assert not roles.is_partner(tester)
    assert not roles.is_administrator(tester)
    assert roles.PARCEIRO not in roles.user_roles(tester)


def test_admin_form_refuses_privileges_for_exempt_account(db):
    call_command("seed_test_user")
    tester = User.objects.get(username="teste@pucparana.com")
    data = {
        "username": tester.username,
        "password": tester.password,
        "is_active": True,
        "is_staff": True,
        "date_joined_0": "2026-09-27",
        "date_joined_1": "10:00:00",
        "groups": [],
    }

    form = LustreUserChangeForm(data=data, instance=tester)

    assert not form.is_valid()
    assert "isenta de MFA" in str(form.errors)


def test_store_form_refuses_exempt_member(db):
    call_command("seed_test_user")
    tester = User.objects.get(username="teste@pucparana.com")

    form = StoreAdminForm(data={"name": "Loja X", "active": True, "members": [tester.pk]})

    assert not form.is_valid()
    assert "members" in form.errors


def test_admin_linking_user_to_store_grants_partner_role(client, db):
    admin = User.objects.create_superuser("admin_mfa", "admin@example.com", PASSWORD)
    future_partner = make_user("vendedor", roles.CLIENTE)
    login_with_mfa(client, admin)

    response = client.post(
        "/admin/stores/store/add/",
        {"name": "Loja Nova", "active": "on", "members": [future_partner.pk]},
    )

    assert response.status_code == 302
    assert roles.is_partner(future_partner)


# ---- acesso à API do parceiro --------------------------------------------------


def test_customer_cannot_use_partner_api(client, customer):
    login_with_mfa(client, customer)

    assert client.get(reverse("partner-products")).status_code == 403
    assert client.get(reverse("partner-order-items")).status_code == 403


def test_partner_group_without_store_is_not_partner(client, db):
    user = make_user("sem_loja", roles.PARCEIRO)
    login_with_mfa(client, user)

    assert client.get(reverse("partner-products")).status_code == 403


def test_partner_of_inactive_store_loses_access(client, partner_a, store_a):
    store_a.active = False
    store_a.save()
    login_with_mfa(client, partner_a)

    assert client.get(reverse("partner-products")).status_code == 403


def test_partner_api_requires_mfa_verified_session(client, partner_a):
    client.force_login(partner_a)  # só senha, sem segundo fator

    assert client.get(reverse("partner-products")).status_code == 403


# ---- produtos do parceiro ------------------------------------------------------


def test_partner_lists_only_own_products(client, partner_a, product_a, product_b):
    login_with_mfa(client, partner_a)

    names = [p["name"] for p in client.get(reverse("partner-products")).json()]

    assert names == ["Vaso A"]


def test_partner_creates_product_in_own_store(client, partner_a, store_a):
    login_with_mfa(client, partner_a)

    response = client.post(
        reverse("partner-products"),
        {"store": store_a.pk, "name": "Luminária", "price": "120.00", "description": "x"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert Product.objects.get(name="Luminária").store == store_a


def test_partner_cannot_create_product_in_other_store(client, partner_a, store_b):
    login_with_mfa(client, partner_a)

    response = client.post(
        reverse("partner-products"),
        {"store": store_b.pk, "name": "Intruso", "price": "10.00"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not Product.objects.filter(name="Intruso").exists()


def test_partner_cannot_touch_other_store_product(client, partner_a, product_b, caplog):
    login_with_mfa(client, partner_a)

    with caplog.at_level(logging.WARNING, logger="apps.stores"):
        response = client.patch(
            reverse("partner-product-detail", args=[product_b.pk]),
            {"price": "1.00"},
            content_type="application/json",
        )

    assert response.status_code == 404
    product_b.refresh_from_db()
    assert str(product_b.price) == "70.00"
    assert any(r.getMessage() == "forbidden_object_access" for r in caplog.records)


def test_partner_cannot_touch_house_products(client, partner_a, db):
    house = Product.objects.create(name="Produto da casa", price="10.00")
    login_with_mfa(client, partner_a)

    response = client.patch(
        reverse("partner-product-detail", args=[house.pk]), {"active": False}, content_type="application/json"
    )

    assert response.status_code == 404


def test_partner_cannot_move_product_to_other_store(client, partner_a, product_a, store_b):
    login_with_mfa(client, partner_a)

    response = client.patch(
        reverse("partner-product-detail", args=[product_a.pk]), {"store": store_b.pk}, content_type="application/json"
    )

    assert response.status_code == 400


def test_partner_deactivates_product_and_it_leaves_catalog(client, partner_a, product_a):
    login_with_mfa(client, partner_a)
    client.patch(reverse("partner-product-detail", args=[product_a.pk]), {"active": False}, content_type="application/json")

    names = [p["name"] for p in client.get(reverse("product-list")).json()]

    assert "Vaso A" not in names


def test_image_url_rejects_dangerous_schemes(client, partner_a, store_a):
    login_with_mfa(client, partner_a)

    response = client.post(
        reverse("partner-products"),
        {"store": store_a.pk, "name": "X", "price": "1.00", "image_url": "javascript:alert(1)"},
        content_type="application/json",
    )

    assert response.status_code == 400


def test_catalog_shows_store_name_and_hides_inactive_store(client, product_a, product_b, store_b):
    store_b.active = False
    store_b.save()

    products = client.get(reverse("product-list")).json()

    assert [(p["name"], p["store_name"]) for p in products] == [("Vaso A", "Loja A")]


# ---- pedidos: snapshot da loja e despacho pelo parceiro ------------------------


def _buy(client, customer, *products):
    login_with_mfa(client, customer)
    for product in products:
        client.post(reverse("cart-item-list"), {"product_id": product.pk, "quantity": 1}, content_type="application/json")
    return client.post(reverse("order-list-create")).json()


def test_order_items_snapshot_store(client, customer, product_a, product_b):
    _buy(client, customer, product_a, product_b)

    stores = set(OrderItem.objects.values_list("store__name", flat=True))

    assert stores == {"Loja A", "Loja B"}


def test_partner_sees_only_own_items_without_customer_data(client, customer, partner_a, product_a, product_b):
    _buy(client, customer, product_a, product_b)
    client.logout()
    login_with_mfa(client, partner_a)

    items = client.get(reverse("partner-order-items")).json()

    assert [i["product_name"] for i in items] == ["Vaso A"]
    assert "cliente1" not in str(items)
    assert "cliente1@example.com" not in str(items)


def test_partner_marks_item_shipped(client, customer, partner_a, product_a):
    _buy(client, customer, product_a)
    item = OrderItem.objects.get()
    client.logout()
    login_with_mfa(client, partner_a)

    response = client.patch(
        reverse("partner-order-item-detail", args=[item.pk]),
        {"fulfillment_status": "shipped", "quantity": 99},
        content_type="application/json",
    )

    item.refresh_from_db()
    assert response.status_code == 200
    assert item.fulfillment_status == "shipped"
    assert item.quantity == 1  # campo somente leitura para o parceiro


def test_partner_cannot_ship_other_store_item(client, customer, partner_a, product_b):
    _buy(client, customer, product_b)
    item = OrderItem.objects.get()
    client.logout()
    login_with_mfa(client, partner_a)

    response = client.patch(
        reverse("partner-order-item-detail", args=[item.pk]),
        {"fulfillment_status": "shipped"},
        content_type="application/json",
    )

    assert response.status_code == 404
