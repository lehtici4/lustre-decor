from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from apps.core.services import mfa_service

from . import roles


class LustreUserChangeForm(DjangoUserAdmin.form):
    """Recusa dar privilégio a uma conta isenta de MFA (ex.: a conta de
    avaliação teste@pucparana.com): sem essa trava, bastaria marcar is_staff
    ou pôr a conta no grupo administrador/parceiro para existir um usuário
    privilegiado entrando só com senha."""

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username") or getattr(self.instance, "username", "")
        probe = User(username=username)
        if mfa_service.is_exempt(probe):
            groups = {group.name for group in cleaned.get("groups") or []}
            if cleaned.get("is_staff") or cleaned.get("is_superuser") or groups & set(roles.PRIVILEGED_ROLES):
                raise forms.ValidationError(
                    "Esta conta está isenta de MFA (MFA_EXEMPT_USERS) e não pode ser "
                    "administrador, staff, superusuário nem parceiro."
                )
        return cleaned


admin.site.unregister(User)


@admin.register(User)
class LustreUserAdmin(DjangoUserAdmin):
    form = LustreUserChangeForm
    list_display = ["username", "email", "is_staff", "is_active", "papeis"]
    list_filter = ["is_staff", "is_active", "groups"]

    @admin.display(description="papéis")
    def papeis(self, obj):
        return ", ".join(roles.user_roles(obj)) or "-"
