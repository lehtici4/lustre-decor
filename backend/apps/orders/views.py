from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.services import cart_service, order_service
from apps.core.services.order_service import EmptyCartError

from .models import Order
from .serializers import (
    AddCartItemSerializer,
    CartSerializer,
    OrderSerializer,
    UpdateCartItemSerializer,
)


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart = cart_service.get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)


class CartItemListView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = cart_service.add_item(
            request.user,
            product_id=serializer.validated_data["product_id"],
            quantity=serializer.validated_data["quantity"],
        )
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        item = cart_service.get_owned_item(request.user, pk)
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = cart_service.update_item_quantity(item, serializer.validated_data["quantity"])
        return Response(CartSerializer(cart).data)

    def delete(self, request, pk):
        item = cart_service.get_owned_item(request.user, pk)
        cart = cart_service.remove_item(item)
        return Response(CartSerializer(cart).data)


class OrderListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).prefetch_related("items")
        return Response(OrderSerializer(orders, many=True).data)

    def post(self, request):
        try:
            order = order_service.create_order_from_cart(request.user)
        except EmptyCartError:
            return Response({"detail": "O carrinho está vazio."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        order = order_service.get_owned_order(request.user, pk)
        return Response(OrderSerializer(order).data)
