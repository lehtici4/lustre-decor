from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group

from apps.accounts import roles
from apps.core.services import mfa_service

from .models import Campaign, Store


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


class CampaignAdminForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["store", "name", "slug", "description", "accent_color", "active", "starts_at", "ends_at", "products"]

    def clean(self):
        cleaned = super().clean()
        store = cleaned.get("store")
        products = cleaned.get("products") or []
        foreign = [p.name for p in products if p.store_id != getattr(store, "id", None)]
        if foreign:
            raise forms.ValidationError(f"Produtos de outra loja não entram nesta vitrine: {', '.join(foreign)}.")
        starts, ends = cleaned.get("starts_at"), cleaned.get("ends_at")
        if starts and ends and ends < starts:
            raise forms.ValidationError("O fim da vitrine é anterior ao início.")
        return cleaned


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    form = CampaignAdminForm
    list_display = ["name", "store", "active", "starts_at", "ends_at"]
    list_filter = ["active", "store"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    filter_horizontal = ["products"]
