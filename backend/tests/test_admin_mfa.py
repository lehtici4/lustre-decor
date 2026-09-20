import pytest
from django.contrib.auth.models import User
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin_teste", password="uma-senha-forte-123", is_staff=True, is_superuser=True
    )


def test_admin_redirects_anonymous_to_two_factor_login(client, db):
    response = client.get("/admin/", follow=True)

    assert response.status_code == 200
    assert "two_factor/login" in response.redirect_chain[-1][0] or "account/login" in response.redirect_chain[-1][0]


def test_admin_denies_staff_without_verified_otp_device(client, admin_user):
    client.force_login(admin_user)

    response = client.get("/admin/")

    assert response.status_code in (302, 403)


def test_admin_allows_staff_with_verified_otp_device(client, admin_user):
    device = TOTPDevice.objects.create(user=admin_user, name="default", confirmed=True)
    client.force_login(admin_user)

    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()

    response = client.get("/admin/")

    assert response.status_code == 200
