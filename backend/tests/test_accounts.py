import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


@pytest.fixture
def existing_user(db):
    return User.objects.create_user(username="cliente", password="uma-senha-forte-123")


def test_register_creates_user_with_hashed_password(client, db):
    response = client.post(
        reverse("auth-register"),
        {"username": "novo_cliente", "email": "novo@example.com", "password": "uma-senha-forte-123"},
        content_type="application/json",
    )

    assert response.status_code == 201
    user = User.objects.get(username="novo_cliente")
    assert user.password != "uma-senha-forte-123"
    assert user.check_password("uma-senha-forte-123")


def test_register_rejects_duplicate_username(client, existing_user):
    response = client.post(
        reverse("auth-register"),
        {"username": "cliente", "email": "outro@example.com", "password": "outra-senha-123"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "username" in response.json()


def test_register_rejects_duplicate_email(client, db):
    User.objects.create_user(username="alguem", email="ocupado@example.com", password="uma-senha-forte-123")

    response = client.post(
        reverse("auth-register"),
        {"username": "outro_nome", "email": "ocupado@example.com", "password": "outra-senha-123"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "email" in response.json()


def test_register_requires_email(client, db):
    response = client.post(
        reverse("auth-register"),
        {"username": "sem_email", "password": "uma-senha-forte-123"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "email" in response.json()


def test_register_rejects_weak_password(client, db):
    response = client.post(
        reverse("auth-register"),
        {"username": "outro_cliente", "email": "outro_cliente@example.com", "password": "123"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "password" in response.json()


def test_login_succeeds_with_valid_credentials(client, existing_user):
    response = client.post(
        reverse("auth-login"),
        {"username": "cliente", "password": "uma-senha-forte-123"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["username"] == "cliente"
    assert "_auth_user_id" in client.session


def test_login_fails_with_invalid_credentials(client, existing_user):
    response = client.post(
        reverse("auth-login"),
        {"username": "cliente", "password": "senha-errada"},
        content_type="application/json",
    )

    assert response.status_code == 401
    assert "_auth_user_id" not in client.session


def test_login_is_throttled_after_repeated_attempts(client, existing_user):
    for _ in range(5):
        client.post(
            reverse("auth-login"),
            {"username": "cliente", "password": "senha-errada"},
            content_type="application/json",
        )

    response = client.post(
        reverse("auth-login"),
        {"username": "cliente", "password": "senha-errada"},
        content_type="application/json",
    )

    assert response.status_code == 429


def test_logout_requires_authentication(client, db):
    response = client.post(reverse("auth-logout"))

    assert response.status_code in (401, 403)


def test_logout_ends_session(client, existing_user):
    client.force_login(existing_user)

    response = client.post(reverse("auth-logout"))

    assert response.status_code == 204
    assert "_auth_user_id" not in client.session


def test_authenticated_post_without_csrf_token_is_rejected(existing_user):
    strict_client = Client(enforce_csrf_checks=True)
    strict_client.force_login(existing_user)

    response = strict_client.post(reverse("auth-logout"))

    assert response.status_code == 403


def test_me_requires_authentication(client, db):
    response = client.get(reverse("auth-me"))

    assert response.status_code in (401, 403)


def test_me_returns_current_user(client, existing_user):
    client.force_login(existing_user)

    response = client.get(reverse("auth-me"))

    assert response.status_code == 200
    assert response.json()["username"] == "cliente"


def test_csrf_endpoint_sets_cookie(client, db):
    response = client.get(reverse("auth-csrf"))

    assert response.status_code == 204
    assert "csrftoken" in response.cookies
