"""Vitrines temáticas (Campaign) e o seed do marketplace."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts import roles
from apps.catalog.models import Product
from apps.stores.admin import CampaignAdminForm
from apps.stores.models import Campaign, Store
from tests.helpers import login_with_mfa


@pytest.fixture
def store(db):
    return Store.objects.create(name="Loja A")


@pytest.fixture
def other_store(db):
    return Store.objects.create(name="Loja B")


@pytest.fixture
def products(store):
    return [Product.objects.create(name=f"P{i}", price="10.00", store=store) for i in range(3)]


@pytest.fixture
def campaign(store, products):
    c = Campaign.objects.create(store=store, name="Vitrine A", slug="vitrine-a")
    c.products.set(products[:2])
    return c


@pytest.fixture
def partner(store):
    user = User.objects.create_user("parc", password="uma-senha-forte-123")
    user.groups.add(Group.objects.get(name=roles.PARCEIRO))
    store.members.add(user)
    return user


def test_public_list_shows_live_campaign(client, campaign):
    body = client.get(reverse("campaign-list")).json()

    assert body == [
        {
            "slug": "vitrine-a",
            "name": "Vitrine A",
            "description": "",
            "accent_color": "#795b3d",
            "store_name": "Loja A",
            "product_count": 2,
        }
    ]


def test_campaign_detail_lists_only_visible_products(client, campaign, products):
    products[0].active = False
    products[0].save()

    body = client.get(reverse("campaign-detail", args=["vitrine-a"])).json()

    assert [p["name"] for p in body["products"]] == ["P1"]


@pytest.mark.parametrize(
    "change",
    [
        {"active": False},
        {"starts_at": timezone.now() + timedelta(days=1)},
        {"ends_at": timezone.now() - timedelta(days=1)},
    ],
)
def test_inactive_or_out_of_period_campaign_is_hidden(client, campaign, change):
    Campaign.objects.filter(pk=campaign.pk).update(**change)

    assert client.get(reverse("campaign-list")).json() == []
    assert client.get(reverse("campaign-detail", args=["vitrine-a"])).status_code == 404


def test_campaign_of_inactive_store_is_hidden(client, campaign, store):
    store.active = False
    store.save()

    assert client.get(reverse("campaign-list")).json() == []


def test_campaign_without_visible_products_is_not_listed(client, campaign, products):
    Product.objects.update(active=False)

    assert client.get(reverse("campaign-list")).json() == []


def test_admin_form_rejects_product_from_other_store(store, other_store):
    foreign = Product.objects.create(name="Alheio", price="5.00", store=other_store)
    form = CampaignAdminForm(
        data={"store": store.pk, "name": "V", "slug": "v", "accent_color": "#123456", "products": [foreign.pk]}
    )

    assert not form.is_valid()


def test_partner_creates_campaign_with_own_products(client, partner, store, products):
    login_with_mfa(client, partner)

    response = client.post(
        reverse("partner-campaigns"),
        {"store": store.pk, "name": "Minha Vitrine", "products": [products[0].pk], "accent_color": "#aa3300"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["slug"] == "minha-vitrine"


def test_partner_cannot_put_other_store_product_in_campaign(client, partner, store, other_store):
    foreign = Product.objects.create(name="Alheio", price="5.00", store=other_store)
    login_with_mfa(client, partner)

    response = client.post(
        reverse("partner-campaigns"),
        {"store": store.pk, "name": "X", "products": [foreign.pk]},
        content_type="application/json",
    )

    assert response.status_code == 400


def test_partner_cannot_edit_other_store_campaign(client, partner, other_store):
    foreign = Campaign.objects.create(store=other_store, name="Deles", slug="deles")
    login_with_mfa(client, partner)

    response = client.patch(
        reverse("partner-campaign-detail", args=[foreign.pk]), {"active": False}, content_type="application/json"
    )

    assert response.status_code == 404
    foreign.refresh_from_db()
    assert foreign.active is True


def test_accent_color_is_validated(client, partner, store):
    login_with_mfa(client, partner)

    response = client.post(
        reverse("partner-campaigns"),
        {"store": store.pk, "name": "X", "accent_color": "red;background:url(x)"},
        content_type="application/json",
    )

    assert response.status_code == 400


# ---- seed_marketplace -----------------------------------------------------------


def test_seed_marketplace_creates_three_stores_with_campaigns(client, db, capsys):
    call_command("seed_marketplace")
    out = capsys.readouterr().out

    assert Store.objects.count() == 3
    assert Product.objects.filter(store__isnull=False).count() == 15
    assert len(client.get(reverse("campaign-list")).json()) == 3
    for username in ("parceiro.terra", "parceiro.boho", "parceiro.luz"):
        assert roles.is_partner(User.objects.get(username=username))
        assert username in out  # senha mostrada uma vez


def test_seed_marketplace_is_idempotent_and_keeps_passwords(db, capsys):
    call_command("seed_marketplace")
    hashes = dict(User.objects.filter(username__startswith="parceiro.").values_list("username", "password"))
    capsys.readouterr()

    call_command("seed_marketplace")
    out = capsys.readouterr().out

    assert Store.objects.count() == 3
    assert Campaign.objects.count() == 3
    assert dict(User.objects.filter(username__startswith="parceiro.").values_list("username", "password")) == hashes
    assert "parceiro.terra" not in out
