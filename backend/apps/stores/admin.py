from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group

from apps.accounts import roles
from apps.core.services import mfa_service

from .models import Store


class StoreAdminForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ["name", "active", "members"]

    def clean_members(self):
        members = self.cleaned_data["members"]
        exempt = [user.username for user in members if mfa_service.is_exempt(user)]
        if exempt:
            raise forms.ValidationError(
                f"Conta(s) isenta(s) de MFA não podem ser parceiras: {', '.join(exempt)}."
            )
        return members


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    """Conceder o papel de parceiro = vincular o usuário a uma loja aqui.
    O grupo `parceiro` é adicionado automaticamente ao salvar."""

    form = StoreAdminForm
    list_display = ["name", "active", "created_at"]
    list_filter = ["active"]
    search_fields = ["name"]
    filter_horizontal = ["members"]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        partner_group, _ = Group.objects.get_or_create(name=roles.PARCEIRO)
        for user in form.instance.members.all():
            user.groups.add(partner_group)
