from django.conf import settings
from django.db import models


class Store(models.Model):
    """Loja parceira do marketplace. Os usuários em `members` são os
    parceiros que administram os produtos e os pedidos dessa loja.

    Só um administrador cria lojas e vincula parceiros (Django Admin, com
    MFA) — o cadastro público sempre gera cliente. Ver docs/authorization.md."""

    name = models.CharField("nome", max_length=200, unique=True)
    active = models.BooleanField("ativa", default=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="stores",
        blank=True,
        verbose_name="parceiros",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "loja"
        verbose_name_plural = "lojas"

    def __str__(self) -> str:
        return self.name
