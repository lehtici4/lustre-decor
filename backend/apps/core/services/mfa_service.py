"""MFA (TOTP) obrigatório no login da loja.

Sem serviço de e-mail no laboratório, o segundo fator é um app autenticador
(TOTP, RFC 6238 — Google Authenticator, Microsoft Authenticator, Aegis...) e
a recuperação é feita por códigos de backup de uso único, entregues uma única
vez no momento em que o TOTP é confirmado.

Fluxo (a sessão só é criada DEPOIS do segundo fator):

1. POST /auth/login/ com usuário e senha corretos:
   - conta isenta (MFA_EXEMPT_USERS, por padrão só a conta de avaliação
     teste@pucparana.com): login imediato, como antes;
   - conta com TOTP confirmado: responde ``stage=verify`` e guarda na sessão
     anônima um "desafio pendente" (id do usuário, validade, tentativas);
   - conta sem TOTP confirmado (usuário novo): gera um dispositivo TOTP ainda
     não confirmado e responde ``stage=setup`` com o QR code/segredo.
2. POST /auth/mfa/verify/ com o código de 6 dígitos (ou um código de backup):
   só então chama ``django.contrib.auth.login`` + ``django_otp.login`` — a
   sessão nasce marcada como verificada (``request.user.is_verified()``).

O desafio pendente expira em MFA_PENDING_TTL segundos e é descartado após
MFA_MAX_ATTEMPTS códigos errados (obriga a digitar a senha de novo).
"""

import base64
import io
import logging
import time
from dataclasses import dataclass, field

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django_otp import login as otp_login
from django_otp import match_token
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

logger = logging.getLogger("apps.accounts")

PENDING_SESSION_KEY = "mfa_pending"
TOTP_DEVICE_NAME = "app-autenticador"
BACKUP_DEVICE_NAME = "codigos-backup"
BACKUP_CODES_COUNT = 8

STAGE_SETUP = "setup"
STAGE_VERIFY = "verify"


class MfaChallengeError(Exception):
    """Desafio inexistente, expirado ou esgotado — o cliente precisa refazer o login."""


class MfaInvalidToken(Exception):
    """Código incorreto, mas o desafio continua válido (ainda há tentativas)."""

    def __init__(self, attempts_left: int):
        super().__init__("invalid token")
        self.attempts_left = attempts_left


@dataclass
class MfaVerification:
    user: User
    backup_codes: list[str] = field(default_factory=list)


def _exempt_usernames() -> set[str]:
    return {name.lower() for name in getattr(settings, "MFA_EXEMPT_USERS", [])}


def is_exempt(user: User) -> bool:
    """Isenção por NOME DE USUÁRIO (o identificador de login), não por e-mail:
    o e-mail é um campo livre no cadastro, não deve abrir exceção de MFA."""
    return user.username.lower() in _exempt_usernames()


def has_confirmed_totp(user: User) -> bool:
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def _qr_code_data_uri(uri: str) -> str:
    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def start_challenge(request, user: User) -> dict:
    """Chamado após usuário+senha corretos, para contas NÃO isentas. Não cria
    sessão autenticada — só registra o desafio pendente na sessão anônima."""
    pending = {
        "user_id": user.pk,
        "backend": getattr(user, "backend", settings.AUTHENTICATION_BACKENDS[0]),
        "expires_at": time.time() + settings.MFA_PENDING_TTL,
        "attempts": 0,
    }

    if has_confirmed_totp(user):
        pending["stage"] = STAGE_VERIFY
        request.session[PENDING_SESSION_KEY] = pending
        logger.info("mfa_challenge_issued", extra={"user_id": user.pk, "stage": STAGE_VERIFY})
        return {"mfa_required": True, "stage": STAGE_VERIFY}

    # Primeiro acesso (ou cadastro que nunca concluiu o setup): um segredo novo
    # a cada tentativa — um QR code antigo exposto não serve para nada.
    TOTPDevice.objects.filter(user=user, confirmed=False).delete()
    device = TOTPDevice.objects.create(user=user, name=TOTP_DEVICE_NAME, confirmed=False)
    pending["stage"] = STAGE_SETUP
    pending["device_id"] = device.pk
    request.session[PENDING_SESSION_KEY] = pending

    secret = base64.b32encode(device.bin_key).decode("ascii").rstrip("=")
    logger.info("mfa_challenge_issued", extra={"user_id": user.pk, "stage": STAGE_SETUP})
    return {
        "mfa_required": True,
        "stage": STAGE_SETUP,
        "otpauth_uri": device.config_url,
        "secret": secret,
        "qr_code": _qr_code_data_uri(device.config_url),
    }


def _load_pending(request) -> dict:
    pending = request.session.get(PENDING_SESSION_KEY)
    if not pending:
        raise MfaChallengeError("no pending challenge")
    if time.time() > pending["expires_at"]:
        request.session.pop(PENDING_SESSION_KEY, None)
        raise MfaChallengeError("expired")
    return pending


def _issue_backup_codes(user: User) -> list[str]:
    StaticDevice.objects.filter(user=user, name=BACKUP_DEVICE_NAME).delete()
    backup = StaticDevice.objects.create(user=user, name=BACKUP_DEVICE_NAME, confirmed=True)
    codes = [StaticToken.random_token() for _ in range(BACKUP_CODES_COUNT)]
    for code in codes:
        backup.token_set.create(token=code)
    return codes


def verify_challenge(request, token: str) -> MfaVerification:
    pending = _load_pending(request)

    try:
        user = User.objects.get(pk=pending["user_id"], is_active=True)
    except User.DoesNotExist as exc:
        request.session.pop(PENDING_SESSION_KEY, None)
        raise MfaChallengeError("user gone") from exc

    token = token.strip().replace(" ", "")
    device = None

    if pending["stage"] == STAGE_SETUP:
        candidate = TOTPDevice.objects.filter(pk=pending.get("device_id"), user=user, confirmed=False).first()
        if candidate is None:
            request.session.pop(PENDING_SESSION_KEY, None)
            raise MfaChallengeError("setup device gone")
        if candidate.verify_token(token):
            device = candidate
    else:
        # Aceita o TOTP ou um código de backup (StaticDevice) — ambos
        # confirmados; o código de backup é consumido ao ser usado.
        device = match_token(user, token)

    if device is None:
        pending["attempts"] += 1
        attempts_left = settings.MFA_MAX_ATTEMPTS - pending["attempts"]
        logger.warning(
            "mfa_failed",
            extra={"user_id": user.pk, "origin": request.META.get("REMOTE_ADDR"), "stage": pending["stage"]},
        )
        if attempts_left <= 0:
            request.session.pop(PENDING_SESSION_KEY, None)
            raise MfaChallengeError("too many attempts")
        request.session[PENDING_SESSION_KEY] = pending
        raise MfaInvalidToken(attempts_left)

    backup_codes: list[str] = []
    if pending["stage"] == STAGE_SETUP:
        device.confirmed = True
        device.save(update_fields=["confirmed"])
        backup_codes = _issue_backup_codes(user)
        logger.info("mfa_enrolled", extra={"user_id": user.pk})

    request.session.pop(PENDING_SESSION_KEY, None)
    login(request, user, backend=pending["backend"])
    otp_login(request, device)
    logger.info("login_succeeded", extra={"user_id": user.pk, "mfa": True})
    return MfaVerification(user=user, backup_codes=backup_codes)


def is_request_verified(user) -> bool:
    """Sessão autenticada E (conta isenta OU segundo fator verificado nesta sessão)."""
    if not (user and user.is_authenticated):
        return False
    if is_exempt(user):
        return True
    # is_verified() é injetado no usuário pelo OTPMiddleware do django-otp.
    verified_check = getattr(user, "is_verified", None)
    return bool(callable(verified_check) and verified_check())
