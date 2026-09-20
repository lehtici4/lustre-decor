import logging

from django.db import transaction
from django.http import Http404

from apps.orders.models import Cart, Order, OrderItem

logger = logging.getLogger("apps.orders")


class EmptyCartError(Exception):
    """Levantado ao tentar registrar um pedido a partir de um carrinho vazio."""


@transaction.atomic
def create_order_from_cart(user) -> Order:
    cart = Cart.objects.filter(user=user).first()
    items = list(cart.items.select_related("product")) if cart else []

    if not items:
        raise EmptyCartError

    total = sum((item.product.price * item.quantity for item in items), start=0)
    order = Order.objects.create(user=user, total=total)
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product_name=item.product.name,
                unit_price=item.product.price,
                quantity=item.quantity,
            )
            for item in items
        ]
    )
    cart.items.all().delete()

    logger.info("order_created", extra={"user_id": user.id, "order_id": order.id})
    return order


def get_owned_order(user, pk: int) -> Order:
    order = Order.objects.filter(pk=pk).prefetch_related("items").first()
    if order is None:
        raise Http404

    if order.user_id != user.id:
        logger.warning(
            "forbidden_object_access",
            extra={"user_id": user.id, "model": "Order", "object_id": pk},
        )
        raise Http404

    return order
