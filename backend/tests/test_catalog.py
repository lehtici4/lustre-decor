import pytest
from django.urls import reverse

from apps.catalog.models import Product


@pytest.fixture
def active_product(db):
    return Product.objects.create(name="Vaso Teste", description="Descrição", price="10.00")


@pytest.fixture
def inactive_product(db):
    return Product.objects.create(
        name="Vaso Inativo", description="Descrição", price="10.00", active=False
    )


def test_product_list_is_public(client, active_product):
    response = client.get(reverse("product-list"))

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == [active_product.name]


def test_product_list_hides_inactive_products(client, active_product, inactive_product):
    response = client.get(reverse("product-list"))

    names = [item["name"] for item in response.json()]
    assert inactive_product.name not in names


def test_product_detail_is_public(client, active_product):
    response = client.get(reverse("product-detail", args=[active_product.pk]))

    assert response.status_code == 200
    assert response.json()["name"] == active_product.name


def test_product_detail_hides_inactive_products(client, inactive_product):
    response = client.get(reverse("product-detail", args=[inactive_product.pk]))

    assert response.status_code == 404
