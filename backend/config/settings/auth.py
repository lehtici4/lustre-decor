"""
Configurações de autenticação dinâmicas.
Sprint 1 (atual): Django nativo com django-otp (TOTP) + two_factor.
Sprint 2 (futuro): OIDC + Keycloak como PDP, sem reescrever código.

Ativa OIDC alterando ENABLE_OIDC=true no .env ou docker-stack.interna.yml.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

ENABLE_OIDC = os.getenv("ENABLE_OIDC", "false").lower() == "true"

if ENABLE_OIDC:
    AUTHENTICATION_BACKENDS = [
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]

    OIDC_RP_CLIENT_ID = os.getenv("OIDC_RP_CLIENT_ID", "")
    OIDC_RP_CLIENT_SECRET = os.getenv("OIDC_RP_CLIENT_SECRET", "")
    OIDC_OP_AUTHORIZATION_ENDPOINT = os.getenv(
        "OIDC_OP_AUTHORIZATION_ENDPOINT", "http://keycloak:8080/auth/realms/lustredecor/protocol/openid-connect/auth"
    )
    OIDC_OP_TOKEN_ENDPOINT = os.getenv(
        "OIDC_OP_TOKEN_ENDPOINT", "http://keycloak:8080/auth/realms/lustredecor/protocol/openid-connect/token"
    )
    OIDC_OP_USER_ENDPOINT = os.getenv(
        "OIDC_OP_USER_ENDPOINT", "http://keycloak:8080/auth/realms/lustredecor/protocol/openid-connect/userinfo"
    )
    OIDC_OP_JWKS_ENDPOINT = os.getenv(
        "OIDC_OP_JWKS_ENDPOINT", "http://keycloak:8080/auth/realms/lustredecor/protocol/openid-connect/certs"
    )

    OIDC_RP_SIGN_ALGO = "RS256"
    OIDC_RP_IDP_SIGN_KEY = None
    OIDC_OP_USER_ID_FIELD = "sub"

    LOGIN_URL = "oidc_authentication_request"
    LOGIN_REDIRECT_URL = "/"
    LOGOUT_REDIRECT_URL = "/"

else:
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
    ]

    LOGIN_URL = "two_factor:login"
    LOGIN_REDIRECT_URL = "/admin/"
