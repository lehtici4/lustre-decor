"""Papéis (RBAC) do Lustre Decor, implementados como grupos do Django.

| Papel          | Como se obtém                                   | O que pode                                     |
|----------------|-------------------------------------------------|------------------------------------------------|
| cliente        | automático no cadastro público                  | catálogo, carrinho e pedidos PRÓPRIOS          |
| parceiro       | admin vincula o usuário a uma Loja (Admin)      | produtos e itens de pedido da(s) SUA(S) loja(s) |
| administrador  | admin marca is_staff + grupo administrador      | Django Admin (com MFA) sobre lojas/produtos/pedidos/usuários |
| tester         | só a conta de avaliação (seed_test_user)        | igual a cliente — nada além                     |

Regras de segurança:
- Ninguém se promove: o cadastro público sempre cria `cliente`.
- Conta isenta de MFA (MFA_EXEMPT_USERS) nunca exerce papel privilegiado
  (parceiro/administrador), mesmo que alguém a coloque no grupo ou marque
  is_staff — a checagem é feita aqui, na hora da autorização, e o Admin
  também recusa salvar essa combinação (apps/accounts/admin.py).
- Na Sprint 2 (Keycloak/OIDC) os papéis do IdP são mapeados para estes
  mesmos grupos — as checagens abaixo não mudam.
"""

from apps.core.services import mfa_service

CLIENTE = "cliente"
PARCEIRO = "parceiro"
ADMINISTRADOR = "administrador"
TESTER = "tester"

ALL_ROLES = (CLIENTE, PARCEIRO, ADMINISTRADOR, TESTER)
PRIVILEGED_ROLES = (PARCEIRO, ADMINISTRADOR)

# Permissões de modelo do grupo administrador (Django Admin). Superusuário
# continua existindo só para a instalação; o dia a dia usa este grupo.
ADMIN_PERMISSIONS = {
    "catalog": {"product": ("view", "add", "change", "delete")},
    "orders": {"order": ("view", "change"), "orderitem": ("view", "change")},
    "stores": {"store": ("view", "add", "change", "delete")},
    "auth": {"user": ("view", "change")},
}


def user_roles(user) -> list[str]:
    if not (user and user.is_authenticated):
        return []
    names = set(user.groups.values_list("name", flat=True))
    roles = [role for role in ALL_ROLES if role in names]
    if mfa_service.is_exempt(user):
        roles = [role for role in roles if role not in PRIVILEGED_ROLES]
    return roles


def can_hold_privileged_role(user) -> bool:
    return not mfa_service.is_exempt(user)


def is_partner(user) -> bool:
    """Parceiro de fato = grupo parceiro + ao menos uma loja ativa + não isento."""
    if not (user and user.is_authenticated) or not can_hold_privileged_role(user):
        return False
    return (
        user.groups.filter(name=PARCEIRO).exists()
        and user.stores.filter(active=True).exists()
    )


def is_administrator(user) -> bool:
    if not (user and user.is_authenticated) or not can_hold_privileged_role(user):
        return False
    return user.is_superuser or (user.is_staff and user.groups.filter(name=ADMINISTRADOR).exists())


def ensure_groups(**kwargs) -> None:
    """Cria os 4 grupos e as permissões do administrador (idempotente).
    Ligado ao post_migrate em apps/accounts/apps.py."""
    from django.contrib.auth.models import Group, Permission

    groups = {name: Group.objects.get_or_create(name=name)[0] for name in ALL_ROLES}

    codenames = []
    for app_label, models in ADMIN_PERMISSIONS.items():
        for model, actions in models.items():
            codenames += [(app_label, f"{action}_{model}") for action in actions]
    perms = [
        perm
        for perm in Permission.objects.select_related("content_type").filter(
            content_type__app_label__in=ADMIN_PERMISSIONS.keys()
        )
        if (perm.content_type.app_label, perm.codename) in codenames
    ]
    groups[ADMINISTRADOR].permissions.set(perms)
