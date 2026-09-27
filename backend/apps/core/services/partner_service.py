"""Regras do parceiro (marketplace). Mesmo padrão dos outros serviços:
autorização por objeto aqui, não espalhada pelas views, e tentativa de
acessar objeto de outra loja vira 404 + log `forbidden_object_access`
(o mesmo evento que já gera alerta — ver apps/core/logging.py)."""

import logging

from django.http import Http404

from apps.catalog.models import Product
from apps.orders.models import OrderItem

logger = logging.getLogger("apps.stores")


def partner_stores(user):
    return user.stores.filter(active=True)


def partner_products(user):
    return Product.objects.filter(store__in=partner_stores(user)).select_related("store")


def partner_order_items(user):
    return (
        OrderItem.objects.filter(store__in=partner_stores(user))
        .select_related("order", "store")
        .order_by("-order__created_at", "id")
    )


def _forbidden(user, model: str, pk: int):
    logger.warning(
        "forbidden_object_access",
        extra={"user_id": user.id, "model": model, "object_id": pk, "scope": "partner"},
    )
    raise Http404


def get_owned_product(user, pk: int) -> Product:
    product = Product.objects.filter(pk=pk).select_related("store").first()
    if product is None:
        raise Http404
    if product.store_id is None or not partner_stores(user).filter(pk=product.store_id).exists():
        _forbidden(user, "Product", pk)
    return product


def get_owned_order_item(user, pk: int) -> OrderItem:
    item = OrderItem.objects.filter(pk=pk).select_related("order", "store").first()
    if item is None:
        raise Http404
    if item.store_id is None or not partner_stores(user).filter(pk=item.store_id).exists():
        _forbidden(user, "OrderItem", pk)
    return item
