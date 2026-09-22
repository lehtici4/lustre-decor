from rest_framework.permissions import BasePermission

from apps.core.services import mfa_service


class IsAuthenticatedWithMfa(BasePermission):
    """Substitui o IsAuthenticated: além da sessão, exige que o segundo fator
    tenha sido verificado nesta sessão (exceto contas em MFA_EXEMPT_USERS).

    Defesa em profundidade — pelo fluxo normal a sessão só é criada depois do
    TOTP, mas isso impede que qualquer outro caminho que crie sessão (ex.: um
    login feito só com senha no /account/login/ do two_factor ou um bug
    futuro) dê acesso à API sem MFA."""

    message = "Autenticação multifator necessária."

    def has_permission(self, request, view) -> bool:
        return mfa_service.is_request_verified(request.user)
