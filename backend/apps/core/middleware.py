import logging

from apps.core.net import client_ip

logger = logging.getLogger("apps.core")


class PrivilegedRouteAuditMiddleware:
    """Registra quando um usuário AUTENTICADO sem direito ao Django Admin
    (cliente, parceiro, conta de avaliação — ou um staff cuja sessão não
    passou pelo segundo fator) pede uma página do /admin/ (VULN-07).

    O admin não usa o exception_handler do DRF: para quem não tem permissão
    ele só redireciona para a tela de login, sem deixar rastro. Para um
    usuário já logado, esse redirecionamento é tentativa de escalonamento — o
    mesmo evento privileged_route_denied das rotas de parceiro da API.

    Precisa vir depois do AuthenticationMiddleware e do OTPMiddleware
    (user.is_verified()).
    """

    PREFIX = "/admin/"
    # Telas que o próprio fluxo do admin visita; contá-las duplicaria o evento.
    EXEMPT_PREFIXES = ("/admin/login/", "/admin/logout/", "/admin/jsi18n/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith(self.PREFIX) and not path.startswith(self.EXEMPT_PREFIXES):
            self._audit(request, path)
        return self.get_response(request)

    def _audit(self, request, path):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return
        verified = bool(getattr(user, "is_verified", lambda: False)())
        if user.is_staff and verified:
            return
        logger.warning(
            "privileged_route_denied",
            extra={
                "user_id": user.id,
                "origin": client_ip(request),
                "path": path[:200],
                "reason": "otp_not_verified" if user.is_staff else "not_staff",
            },
        )
