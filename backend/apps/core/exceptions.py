import logging

from rest_framework.exceptions import NotAuthenticated, PermissionDenied, Throttled
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("apps.core")


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    request = context["request"]

    if isinstance(exc, Throttled):
        logger.warning(
            "request_throttled",
            extra={"origin": request.META.get("REMOTE_ADDR"), "path": request.path},
        )
    elif isinstance(exc, (NotAuthenticated, PermissionDenied)):
        user = getattr(request, "user", None)
        user_id = user.id if user is not None and user.is_authenticated else None
        logger.warning(
            "permission_denied",
            extra={"user_id": user_id, "origin": request.META.get("REMOTE_ADDR"), "path": request.path},
        )

    return response
