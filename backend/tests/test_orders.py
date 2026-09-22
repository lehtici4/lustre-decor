import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.catalog.models import Product
from apps.orders.models import Cart, CartItem, Order
from tests.helpers import login_with_mfa


@pytest.fixture
def user_a(db):
    return User.objects.create_user(username="cliente_a", password="uma-senha-forte-123")


@pytest.fixture
def user_b(db):
    return User.objects.create_user(username="cliente_b", password="uma-senha-forte-123")


@pytest.fixture
def product(db):
    return Product.objects.create(name="Vaso Teste", price="25.00")


def test_create_order_requires_authentication(client):
    response = client.post(reverse("order-list-create"))

    assert response.status_code in (401, 403)


def test_create_order_fails_with_empty_cart(client, user_a):
    login_with_mfa(client, user_a)

    response = client.post(reverse("order-list-create"))

    assert response.status_code == 400


def test_create_order_from_cart_snapshots_items_and_clears_cart(client, user_a, product):
    login_with_mfa(client, user_a)
    cart = Cart.objects.create(user=user_a)
    CartItem.objects.create(cart=cart, product=product, quantity=3)

    response = client.post(reverse("order-list-create"))

    assert response.status_code == 201
    data = response.json()
    assert data["total"] == "75.00"
    assert data["items"][0]["product_name"] == product.name
    assert data["items"][0]["quantity"] == 3
    assert not cart.items.exists()


def test_order_survives_product_changes(client, user_a, product):
    login_with_mfa(client, user_a)
    cart = Cart.objects.create(user=user_a)
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    client.post(reverse("order-list-create"))

    product.price = "999.00"
    product.name = "Nome Alterado"
    product.save()

    order = Order.objects.get(user=user_a)
    response = client.get(reverse("order-detail", args=[order.id]))

    assert response.json()["items"][0]["unit_price"] == "25.00"
    assert response.json()["items"][0]["product_name"] == "Vaso Teste"


def test_list_orders_returns_only_own_orders(client, user_a, user_b, product):
    Order.objects.create(user=user_b, total="10.00")
    login_with_mfa(client, user_a)
    cart = Cart.objects.create(user=user_a)
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    client.post(reverse("order-list-create"))

    response = client.get(reverse("order-list-create"))

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_user_cannot_view_another_users_order(client, user_a, user_b):
    order_b = Order.objects.create(user=user_b, total="10.00")
    login_with_mfa(client, user_a)

    response = client.get(reverse("order-detail", args=[order_b.id]))

    assert response.status_code == 404
