"""MFA (TOTP) obrigatório no login da loja, com a conta de avaliação isenta.
Ver apps/core/services/mfa_service.py."""

import time

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

PASSWORD = "uma-senha-forte-123"


def current_code(device: TOTPDevice) -> str:
    return f"{totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits):06d}"


def post_login(client, username, password=PASSWORD):
    return client.post(
        reverse("auth-login"), {"username": username, "password": password}, content_type="application/json"
    )


def post_verify(client, token):
    return client.post(reverse("auth-mfa-verify"), {"token": token}, content_type="application/json")


@pytest.fixture
def new_user(db):
    return User.objects.create_user(username="novo", email="novo@example.com", password=PASSWORD)


@pytest.fixture
def enrolled_user(db):
    user = User.objects.create_user(username="com_mfa", email="mfa@example.com", password=PASSWORD)
    TOTPDevice.objects.create(user=user, name="app-autenticador", confirmed=True)
    return user


@pytest.fixture
def exempt_user(db):
    call_command("seed_test_user")
    return User.objects.get(username="teste@pucparana.com")


# ---- conta de avaliação isenta -------------------------------------------------


def test_exempt_test_account_logs_in_without_mfa(client, exempt_user):
    response = post_login(client, "teste@pucparana.com", "Teste@2026")

    assert response.status_code == 200
    assert response.json()["username"] == "teste@pucparana.com"
    assert "mfa_required" not in response.json()
    assert "_auth_user_id" in client.session
    assert client.get(reverse("cart-detail")).status_code == 200


def test_seed_test_user_removes_leftover_otp_devices(db):
    call_command("seed_test_user")
    user = User.objects.get(username="teste@pucparana.com")
    TOTPDevice.objects.create(user=user, name="sobra", confirmed=True)

    call_command("seed_test_user")

    assert not TOTPDevice.objects.filter(user=user).exists()


def test_exemption_can_be_disabled_by_setting(client, exempt_user, settings):
    settings.MFA_EXEMPT_USERS = []

    response = post_login(client, "teste@pucparana.com", "Teste@2026")

    assert response.json()["mfa_required"] is True
    assert "_auth_user_id" not in client.session


def test_exemption_is_by_username_not_email(client, db):
    User.objects.create_user(username="espertinho", email="teste@pucparana.com", password=PASSWORD)

    response = post_login(client, "espertinho")

    assert response.json()["mfa_required"] is True


# ---- novo usuário: cadastro de TOTP no primeiro login --------------------------


def test_new_user_gets_setup_challenge_with_qr_code(client, new_user):
    response = post_login(client, "novo")

    body = response.json()
    assert response.status_code == 200
    assert body["stage"] == "setup"
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert body["qr_code"].startswith("data:image/svg+xml;base64,")
    assert len(body["secret"]) >= 16
    assert "_auth_user_id" not in client.session
    assert TOTPDevice.objects.filter(user=new_user, confirmed=False).count() == 1


def test_new_user_completes_setup_and_receives_backup_codes(client, new_user):
    post_login(client, "novo")
    device = TOTPDevice.objects.get(user=new_user, confirmed=False)

    response = post_verify(client, current_code(device))

    body = response.json()
    assert response.status_code == 200
    assert body["username"] == "novo"
    assert body["mfa_enabled"] is True
    assert len(body["backup_codes"]) == 8
    device.refresh_from_db()
    assert device.confirmed is True
    assert "_auth_user_id" in client.session
    assert client.get(reverse("auth-me")).status_code == 200


def test_each_setup_attempt_rotates_the_secret(client, new_user):
    first = post_login(client, "novo").json()["secret"]
    second = post_login(client, "novo").json()["secret"]

    assert first != second
    assert TOTPDevice.objects.filter(user=new_user, confirmed=False).count() == 1


def test_register_then_login_goes_to_setup(client, db):
    client.post(
        reverse("auth-register"),
        {"username": "recem", "email": "recem@example.com", "password": PASSWORD},
        content_type="application/json",
    )

    assert post_login(client, "recem").json()["stage"] == "setup"


# ---- usuário já cadastrado no MFA ----------------------------------------------


def test_enrolled_user_gets_verify_challenge_without_secret(client, enrolled_user):
    body = post_login(client, "com_mfa").json()

    assert body == {"mfa_required": True, "stage": "verify"}


def test_enrolled_user_logs_in_with_valid_totp(client, enrolled_user):
    device = TOTPDevice.objects.get(user=enrolled_user)
    post_login(client, "com_mfa")

    response = post_verify(client, current_code(device))

    assert response.status_code == 200
    assert "backup_codes" not in response.json()
    assert client.get(reverse("cart-detail")).status_code == 200


def test_wrong_totp_is_rejected_and_no_session_is_created(client, enrolled_user):
    post_login(client, "com_mfa")

    response = post_verify(client, "000000")

    assert response.status_code == 401
    assert response.json()["attempts_left"] == 4
    assert "_auth_user_id" not in client.session


def test_challenge_is_discarded_after_max_attempts(client, enrolled_user, settings):
    settings.MFA_MAX_ATTEMPTS = 2
    device = TOTPDevice.objects.get(user=enrolled_user)
    post_login(client, "com_mfa")
    post_verify(client, "000000")
    response = post_verify(client, "000000")
    assert response.json()["restart"] is True

    # Mesmo o código certo não serve mais: precisa digitar a senha de novo.
    response = post_verify(client, current_code(device))
    assert response.status_code == 401
    assert "_auth_user_id" not in client.session


def test_challenge_expires(client, enrolled_user, settings, monkeypatch):
    device = TOTPDevice.objects.get(user=enrolled_user)
    post_login(client, "com_mfa")
    future = time.time() + settings.MFA_PENDING_TTL + 1
    monkeypatch.setattr("apps.core.services.mfa_service.time.time", lambda: future)

    response = post_verify(client, current_code(device))

    assert response.status_code == 401
    assert response.json()["restart"] is True


def test_verify_without_password_step_is_rejected(client, enrolled_user):
    device = TOTPDevice.objects.get(user=enrolled_user)

    response = post_verify(client, current_code(device))

    assert response.status_code == 401
    assert "_auth_user_id" not in client.session


def test_backup_code_works_once(client, new_user):
    post_login(client, "novo")
    device = TOTPDevice.objects.get(user=new_user, confirmed=False)
    codes = post_verify(client, current_code(device)).json()["backup_codes"]
    client.post(reverse("auth-logout"))

    post_login(client, "novo")
    assert post_verify(client, codes[0]).status_code == 200
    client.post(reverse("auth-logout"))

    post_login(client, "novo")
    assert post_verify(client, codes[0]).status_code == 401
    assert StaticDevice.objects.get(user=new_user).token_set.count() == 7


def test_mfa_verify_is_throttled(client, enrolled_user):
    post_login(client, "com_mfa")
    for _ in range(10):
        post_verify(client, "000000")

    assert post_verify(client, "000000").status_code == 429


# ---- sessão sem segundo fator não acessa a API --------------------------------


def test_password_only_session_is_denied_by_api(client, new_user):
    # Ex.: sessão criada por outro caminho (login do two_factor em /account/login/).
    client.force_login(new_user)

    assert client.get(reverse("auth-me")).status_code == 403
    assert client.get(reverse("cart-detail")).status_code == 403
