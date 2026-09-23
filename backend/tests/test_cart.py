import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.catalog.models import Product
from apps.orders.models import Cart, CartItem
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


def test_cart_requires_authentication(client, product):
    response = client.get(reverse("cart-detail"))

    assert response.status_code in (401, 403)


def test_add_item_creates_cart_and_item(client, user_a, product):
    login_with_mfa(client, user_a)

    response = client.post(
        reverse("cart-item-list"),
        {"product_id": product.id, "quantity": 2},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["items"][0]["quantity"] == 2
    assert data["total"] == "50.00"


def test_add_item_twice_increments_quantity(client, user_a, product):
    login_with_mfa(client, user_a)
    client.post(
        reverse("cart-item-list"),
        {"product_id": product.id, "quantity": 1},
        content_type="application/json",
    )

    response = client.post(
        reverse("cart-item-list"),
        {"product_id": product.id, "quantity": 2},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["items"][0]["quantity"] == 3


def test_add_inactive_product_is_rejected(client, user_a, product):
    product.active = False
    product.save()
    login_with_mfa(client, user_a)

    response = client.post(
        reverse("cart-item-list"),
        {"product_id": product.id, "quantity": 1},
        content_type="application/json",
    )

    assert response.status_code == 400


def test_update_item_quantity(client, user_a, product):
    login_with_mfa(client, user_a)
    cart = Cart.objects.create(user=user_a)
    item = CartItem.objects.create(cart=cart, product=product, quantity=1)

    response = client.patch(
        reverse("cart-item-detail", args=[item.id]),
        {"quantity": 5},
        content_type="application/json",
    )

    assert response.status_code == 200
    item.refresh_from_db()
    assert item.quantity == 5


def test_remove_item(client, user_a, product):
    login_with_mfa(client, user_a)
    cart = Cart.objects.create(user=user_a)
    item = CartItem.objects.create(cart=cart, product=product, quantity=1)

    response = client.delete(reverse("cart-item-detail", args=[item.id]))

    assert response.status_code == 200
    assert not CartItem.objects.filter(id=item.id).exists()


def test_user_cannot_modify_another_users_cart_item(client, user_a, user_b, product):
    cart_b = Cart.objects.create(user=user_b)
    item_b = CartItem.objects.create(cart=cart_b, product=product, quantity=1)

    login_with_mfa(client, user_a)
    response = client.patch(
        reverse("cart-item-detail", args=[item_b.id]),
        {"quantity": 9},
        content_type="application/json",
    )

    assert response.status_code == 404
    item_b.refresh_from_db()
    assert item_b.quantity == 1


def test_user_cannot_delete_another_users_cart_item(client, user_a, user_b, product):
    cart_b = Cart.objects.create(user=user_b)
    item_b = CartItem.objects.create(cart=cart_b, product=product, quantity=1)

    login_with_mfa(client, user_a)
    response = client.delete(reverse("cart-item-detail", args=[item_b.id]))

    assert response.status_code == 404
    assert CartItem.objects.filter(id=item_b.id).exists()
