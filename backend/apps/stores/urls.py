from django.urls import path

from .views import (
    CampaignDetailView,
    CampaignListView,
    PartnerCampaignDetailView,
    PartnerCampaignListView,
    PartnerOrderItemDetailView,
    PartnerOrderItemListView,
    PartnerProductDetailView,
    PartnerProductListView,
    PartnerStoreListView,
)

urlpatterns = [
    path("campaigns/", CampaignListView.as_view(), name="campaign-list"),
    path("campaigns/<slug:slug>/", CampaignDetailView.as_view(), name="campaign-detail"),
    path("partner/campaigns/", PartnerCampaignListView.as_view(), name="partner-campaigns"),
    path("partner/campaigns/<int:pk>/", PartnerCampaignDetailView.as_view(), name="partner-campaign-detail"),
    path("partner/stores/", PartnerStoreListView.as_view(), name="partner-stores"),
    path("partner/products/", PartnerProductListView.as_view(), name="partner-products"),
    path("partner/products/<int:pk>/", PartnerProductDetailView.as_view(), name="partner-product-detail"),
    path("partner/order-items/", PartnerOrderItemListView.as_view(), name="partner-order-items"),
    path("partner/order-items/<int:pk>/", PartnerOrderItemDetailView.as_view(), name="partner-order-item-detail"),
]
