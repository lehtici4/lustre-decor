from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        from django.contrib.admin.models import LogEntry
        from django.db.models.signals import post_save

        from .signals import log_admin_action

        post_save.connect(log_admin_action, sender=LogEntry)
