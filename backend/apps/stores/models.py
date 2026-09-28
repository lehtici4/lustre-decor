from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


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


class Campaign(models.Model):
    """Vitrine temática de uma loja (ex.: "Refúgio Boho"): nome, texto de
    apresentação, cor de destaque e uma seleção de produtos DA PRÓPRIA LOJA.
    Não altera preço. Aparece na home e em /vitrines/<slug> enquanto estiver
    ativa, dentro do período (se houver) e com a loja ativa."""

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="campaigns", verbose_name="loja")
    name = models.CharField("nome", max_length=120)
    slug = models.SlugField("endereço (slug)", max_length=80, unique=True)
    description = models.TextField("descrição", blank=True)
    accent_color = models.CharField(
        "cor de destaque",
        max_length=7,
        default="#795b3d",
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use o formato #RRGGBB.")],
    )
    active = models.BooleanField("ativa", default=True)
    starts_at = models.DateTimeField("início", null=True, blank=True)
    ends_at = models.DateTimeField("fim", null=True, blank=True)
    products = models.ManyToManyField("catalog.Product", related_name="campaigns", blank=True, verbose_name="produtos")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["store__name", "name"]
        verbose_name = "vitrine"
        verbose_name_plural = "vitrines"

    def __str__(self) -> str:
        return f"{self.name} ({self.store})"

    @classmethod
    def live(cls):
        now = timezone.now()
        return (
            cls.objects.filter(active=True, store__active=True)
            .filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now))
            .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now))
            .select_related("store")
        )
