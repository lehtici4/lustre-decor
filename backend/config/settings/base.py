import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_admins(name: str) -> list[tuple[str, str]]:
    """Formato: "Nome:email@exemplo.com,Outro Nome:outro@exemplo.com". Sem
    isso configurado, ADMINS fica vazio e os alertas de segurança (ver
    apps/core/logging.py) simplesmente não são enviados — não quebra nada."""
    admins = []
    for entry in env_list(name):
        display_name, _, email = entry.partition(":")
        if not email:
            display_name, email = "Segurança", display_name
        admins.append((display_name.strip(), email.strip()))
    return admins


def read_secret(name: str) -> str:
    file_name = os.getenv(f"{name}_FILE")
    if not file_name:
        raise RuntimeError(f"A variável {name}_FILE é obrigatória.")
    try:
        return Path(file_name).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Não foi possível ler o segredo {name}.") from exc


SECRET_KEY = read_secret("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    "formtools",
    "two_factor",
    "apps.core",
    "apps.catalog",
    "apps.accounts",
    "apps.orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serve os estáticos (admin, two-factor) direto do processo do Gunicorn —
    # tem que vir logo após o SecurityMiddleware (ordem exigida pelo próprio
    # WhiteNoise). Elimina a dependência de volume compartilhado entre o waf
    # e o backend: o /static/ do Nginx agora faz proxy_pass pro backend, em
    # vez de ler de um volume — funciona igual com os dois no mesmo host ou
    # em VMs separadas. Sem efeito em dev (nunca roda collectstatic; o
    # runserver já serve os estáticos do próprio jeito dele).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

LOGIN_URL = "two_factor:login"
LOGIN_REDIRECT_URL = "/admin/"
OTP_TOTP_ISSUER = "LustreDecor"

# MFA (TOTP) obrigatório no login da loja — ver apps/core/services/mfa_service.py.
# Sem serviço de e-mail no laboratório, o segundo fator é app autenticador +
# códigos de backup. MFA_EXEMPT_USERS: nomes de usuário (login) liberados sem
# MFA — por padrão só a conta de avaliação exigida pelo professor. Para
# desligar a isenção em uma demonstração pública: MFA_EXEMPT_USERS="" no stack.
MFA_EXEMPT_USERS = env_list("MFA_EXEMPT_USERS", "teste@pucparana.com")
MFA_PENDING_TTL = int(os.getenv("MFA_PENDING_TTL", "300"))
MFA_MAX_ATTEMPTS = int(os.getenv("MFA_MAX_ATTEMPTS", "5"))

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "lustre_decor"),
        "USER": os.getenv("POSTGRES_USER", "lustre_app"),
        "PASSWORD": read_secret("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST", "postgres"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = False

# Sem isso, POST/PUT/DELETE de um domínio/IP que não seja exatamente o que o
# Django calcula como "próprio" (scheme + ALLOWED_HOSTS) falha o CSRF de forma
# silenciosa — o formulário simplesmente não envia. Preencher com o(s)
# endereço(s) reais usados pra acessar a aplicação (ex.: https://172.168.9.50:8443).
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Alertas de segurança (ver apps/core/logging.py e LOGGING abaixo): e-mail
# para bloqueio por força bruta e acesso a objeto de outro usuário. Aponta
# pro Mailpit local por padrão (captura tudo, sem precisar de credencial
# SMTP de verdade) — ver docker-compose.yml / docker-compose.prod.yml.
ADMINS = env_admins("DJANGO_ADMINS")
MANAGERS = ADMINS
EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "mailpit")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "1025"))
EMAIL_USE_TLS = os.getenv("DJANGO_EMAIL_USE_TLS", "false").lower() == "true"
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
SERVER_EMAIL = os.getenv("DJANGO_SERVER_EMAIL", "alertas@lustredecor.local")
EMAIL_SUBJECT_PREFIX = "[LustreDecor segurança] "

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["apps.accounts.permissions.IsAuthenticatedWithMfa"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"login": "5/min", "mfa": "10/min"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "security_alert": {"()": "apps.core.logging.SecurityAlertFilter"},
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "security_alert": {"()": "apps.core.logging.SecurityAlertFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        # Só emite e-mail para os eventos em apps.core.logging.ALERT_EVENTS
        # (filtro abaixo) — o resto do tráfego de warning/erro continua só
        # no log estruturado do console, sem spam de e-mail.
        "security_alert_mail": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "WARNING",
            "filters": ["security_alert"],
            "formatter": "security_alert",
        },
    },
    "root": {
        "handlers": ["console", "security_alert_mail"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
}

# Autenticação condicional (ENABLE_OIDC) — sobrescreve AUTHENTICATION_BACKENDS
# e LOGIN_*. Fica aqui, e não só em settings/__init__.py, porque o Django carrega
# config.settings.development/production direto: o __init__ do pacote roda,
# mas o que ele importa não chega nesses módulos.
from .auth import *  # noqa: E402,F401,F403

