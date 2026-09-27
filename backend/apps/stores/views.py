import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsPartner
from apps.core.services import partner_service

from .serializers import (
    PartnerOrderItemSerializer,
    PartnerProductSerializer,
    PartnerStoreSerializer,
)

logger = logging.getLogger("apps.stores")


class PartnerStoreListView(APIView):
    permission_classes = [IsPartner]

    def get(self, request):
        stores = partner_service.partner_stores(request.user)
        return Response(PartnerStoreSerializer(stores, many=True).data)


class PartnerProductListView(APIView):
    permission_classes = [IsPartner]

    def get(self, request):
        products = partner_service.partner_products(request.user)
        return Response(PartnerProductSerializer(products, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = PartnerProductSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        logger.info(
            "partner_product_created",
            extra={"user_id": request.user.id, "product_id": product.id, "store_id": product.store_id},
        )
        data = PartnerProductSerializer(product, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class PartnerProductDetailView(APIView):
    """Sem DELETE: produto já comprado é referenciado por carrinhos/pedidos.
    Para tirar do catálogo, o parceiro desativa (active=false)."""

    permission_classes = [IsPartner]

    def get(self, request, pk: int):
        product = partner_service.get_owned_product(request.user, pk)
        return Response(PartnerProductSerializer(product, context={"request": request}).data)

    def patch(self, request, pk: int):
        product = partner_service.get_owned_product(request.user, pk)
        serializer = PartnerProductSerializer(product, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        logger.info(
            "partner_product_updated",
            extra={"user_id": request.user.id, "product_id": product.id, "store_id": product.store_id},
        )
        return Response(PartnerProductSerializer(product, context={"request": request}).data)


class PartnerOrderItemListView(APIView):
    permission_classes = [IsPartner]

    def get(self, request):
        items = partner_service.partner_order_items(request.user)
        return Response(PartnerOrderItemSerializer(items, many=True).data)


class PartnerOrderItemDetailView(APIView):
    permission_classes = [IsPartner]

    def patch(self, request, pk: int):
        item = partner_service.get_owned_order_item(request.user, pk)
        serializer = PartnerOrderItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        logger.info(
            "partner_fulfillment_updated",
            extra={"user_id": request.user.id, "order_item_id": item.id, "status": item.fulfillment_status},
        )
        return Response(PartnerOrderItemSerializer(item).data)
