import logging

from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.catalog.models import Product
from apps.orders.models import Cart, CartItem

logger = logging.getLogger("apps.orders")


def get_or_create_cart(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def add_item(user, product_id: int, quantity: int) -> Cart:
    cart = get_or_create_cart(user)
    product = get_object_or_404(Product, id=product_id, active=True)

    item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={"quantity": quantity}
    )
    if not created:
        item.quantity += quantity
        item.save()

    return cart


def get_owned_item(user, pk: int) -> CartItem:
    item = CartItem.objects.filter(pk=pk).select_related("cart", "product").first()
    if item is None:
        raise Http404

    if item.cart.user_id != user.id:
        logger.warning(
            "forbidden_object_access",
            extra={"user_id": user.id, "model": "CartItem", "object_id": pk},
        )
        raise Http404

    return item


def update_item_quantity(item: CartItem, quantity: int) -> Cart:
    item.quantity = quantity
    item.save()
    return item.cart


def remove_item(item: CartItem) -> Cart:
    cart = item.cart
    item.delete()
    return cart
