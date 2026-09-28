from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _ensure_roles(sender, **kwargs):
    # "stores" é o último app do projeto: quando o post_migrate dele roda, as
    # permissões de catalog/orders/stores/auth já foram criadas.
    if sender.label != "stores":
        return
    from .roles import ensure_groups

    ensure_groups()


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        post_migrate.connect(_ensure_roles, dispatch_uid="lustre_ensure_roles")
