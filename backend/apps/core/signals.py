import logging

from django.contrib.admin.models import ADDITION, CHANGE, DELETION

logger = logging.getLogger("apps.core")

ACTION_LABELS = {ADDITION: "created", CHANGE: "changed", DELETION: "deleted"}


def log_admin_action(sender, instance, created, **kwargs):
    if not created:
        return

    logger.info(
        "admin_action",
        extra={
            "user_id": instance.user_id,
            "action": ACTION_LABELS.get(instance.action_flag, "unknown"),
            "model": instance.content_type.model if instance.content_type_id else None,
            "object_id": instance.object_id,
        },
    )
