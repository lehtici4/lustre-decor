import os

from .base import *  # noqa: F403

# O waf termina o TLS do navegador e abre OUTRA conexão TLS (mTLS) até o
# Gunicorn; o esquema original do cliente chega em X-Forwarded-Proto. Sem
# isso, requisições que o navegador fez em HTTP não seriam reconhecidas como
# tal pelo redirect abaixo.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Postgres só por TLS, validando certificado E nome do host (verify-full). Sem
# POSTGRES_SSLROOTCERT a conexão falha — de propósito (fail-closed).
DATABASES["default"]["OPTIONS"]["sslmode"] = os.getenv("POSTGRES_SSLMODE", "verify-full")  # noqa: F405

SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
# O healthcheck do container fala direto com o Gunicorn (sem passar pelo
# Nginx) e não envia X-Forwarded-Proto. Isenção mantida por robustez; o
# healthcheck já usa HTTPS (docker/healthcheck.py).
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Hash no nome do arquivo (cache-busting) + gzip/brotli pré-comprimidos —
# só faz sentido aqui, onde o `collectstatic` do entrypoint-production.sh
# realmente roda. Exige STATICFILES_STORAGE além do middleware (ver base.py).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

