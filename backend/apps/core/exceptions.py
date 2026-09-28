import logging

from rest_framework.exceptions import NotAuthenticated, PermissionDenied, Throttled
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.net import client_ip

logger = logging.getLogger("apps.core")


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    request = context["request"]

    if isinstance(exc, Throttled):
        logger.warning(
            "request_throttled",
            extra={"origin": client_ip(request), "path": request.path},
        )
    elif isinstance(exc, (NotAuthenticated, PermissionDenied)):
        user = getattr(request, "user", None)
        user_id = user.id if user is not None and user.is_authenticated else None
        logger.warning(
            "permission_denied",
            extra={"user_id": user_id, "origin": client_ip(request), "path": request.path},
        )

    return response
