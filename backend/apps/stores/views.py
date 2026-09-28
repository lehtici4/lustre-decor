import logging

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsPartner
from apps.catalog.views import visible_products
from apps.core.services import partner_service

from .models import Campaign
from .serializers import (
    CampaignDetailSerializer,
    CampaignSummarySerializer,
    PartnerCampaignSerializer,
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


# ---- Vitrines (públicas) -------------------------------------------------------


def _visible_ids_by_campaign(campaigns):
    """Só produtos que o catálogo público mostraria (ativos, loja ativa)."""
    visible = set(visible_products().values_list("id", flat=True))
    through = Campaign.products.through.objects.filter(campaign__in=campaigns)
    result: dict[int, list[int]] = {}
    for row in through.values("campaign_id", "product_id"):
        if row["product_id"] in visible:
            result.setdefault(row["campaign_id"], []).append(row["product_id"])
    return result


class CampaignListView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        campaigns = list(Campaign.live())
        visible_ids = _visible_ids_by_campaign(campaigns)
        campaigns = [c for c in campaigns if visible_ids.get(c.pk)]
        return Response(CampaignSummarySerializer(campaigns, many=True, context={"visible_ids": visible_ids}).data)


class CampaignDetailView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        campaign = Campaign.live().filter(slug=slug).first()
        if campaign is None:
            raise Http404
        visible_ids = _visible_ids_by_campaign([campaign])
        products = visible_products().filter(id__in=visible_ids.get(campaign.pk, []))
        context = {"visible_ids": visible_ids, "visible_products": products}
        return Response(CampaignDetailSerializer(campaign, context=context).data)


# ---- Vitrines do parceiro ------------------------------------------------------


class PartnerCampaignListView(APIView):
    permission_classes = [IsPartner]

    def get(self, request):
        campaigns = partner_service.partner_campaigns(request.user)
        return Response(PartnerCampaignSerializer(campaigns, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = PartnerCampaignSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        logger.info(
            "partner_campaign_created",
            extra={"user_id": request.user.id, "campaign_id": campaign.id, "store_id": campaign.store_id},
        )
        data = PartnerCampaignSerializer(campaign, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class PartnerCampaignDetailView(APIView):
    permission_classes = [IsPartner]

    def get(self, request, pk: int):
        campaign = partner_service.get_owned_campaign(request.user, pk)
        return Response(PartnerCampaignSerializer(campaign, context={"request": request}).data)

    def patch(self, request, pk: int):
        campaign = partner_service.get_owned_campaign(request.user, pk)
        serializer = PartnerCampaignSerializer(campaign, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        logger.info(
            "partner_campaign_updated",
            extra={"user_id": request.user.id, "campaign_id": campaign.id, "store_id": campaign.store_id},
        )
        return Response(PartnerCampaignSerializer(campaign, context={"request": request}).data)
