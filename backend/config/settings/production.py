import os

from .base import *  # noqa: F403

# O Nginx termina TLS e encaminha via HTTP interno com X-Forwarded-Proto —
# sem isso, Django acha que toda requisição é insegura e o redirect abaixo
# entraria em loop.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
# O healthcheck do container fala direto com o Gunicorn (sem passar pelo
# Nginx), então nunca carrega X-Forwarded-Proto — sem essa isenção o redirect
# acima quebraria o próprio healthcheck. Não expõe nada sensível.
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

