import logging

from rest_framework.exceptions import (
    NotAuthenticated,
    ParseError,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.net import client_ip

logger = logging.getLogger("apps.core")
auth_logger = logging.getLogger("apps.accounts")

# Requisição malformada (campo faltando, JSON quebrado, content-type errado)
# num endpoint de autenticação. É o que uma ferramenta de força bruta mal
# configurada recebe (HTTP 400) — no pentest, o ataque inteiro passou sem
# nenhum evento porque só a senha errada (401) era registrada (VULN-06).
_INVALID_REQUEST_ERRORS = (ValidationError, ParseError, UnsupportedMediaType)


def _user_id(request):
    user = getattr(request, "user", None)
    return user.id if user is not None and user.is_authenticated else None


def _is_privileged_view(view) -> bool:
    """A view exige um papel acima de cliente (ex.: IsPartner)? As classes de
    permissão assim marcadas têm `privileged = True` (apps/accounts/permissions.py)."""
    return any(getattr(perm, "privileged", False) for perm in getattr(view, "permission_classes", ()))


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    request = context["request"]
    view = context.get("view")

    if isinstance(exc, Throttled):
        logger.warning(
            "request_throttled",
            extra={"origin": client_ip(request), "path": request.path},
        )
    elif isinstance(exc, PermissionDenied) and _user_id(request) is not None and _is_privileged_view(view):
        # Usuário autenticado (ex.: cliente) tentando rota de parceiro/admin:
        # tentativa de escalonamento, não um simples "faça login" (VULN-07).
        logger.warning(
            "privileged_route_denied",
            extra={"user_id": _user_id(request), "origin": client_ip(request), "path": request.path[:200]},
        )
    elif isinstance(exc, (NotAuthenticated, PermissionDenied)):
        logger.warning(
            "permission_denied",
            extra={"user_id": _user_id(request), "origin": client_ip(request), "path": request.path},
        )
    elif isinstance(exc, _INVALID_REQUEST_ERRORS) and getattr(view, "invalid_request_event", None):
        detail = getattr(exc, "detail", None)
        auth_logger.warning(
            view.invalid_request_event,
            extra={
                "origin": client_ip(request),
                "path": request.path,
                "reason": "invalid_request",
                # Só os NOMES dos campos do serializer que falharam, nunca os valores.
                "fields": sorted(detail.keys()) if isinstance(detail, dict) else [],
            },
        )

    return response
