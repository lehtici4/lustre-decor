from django.urls import path

from .views import (
    PartnerOrderItemDetailView,
    PartnerOrderItemListView,
    PartnerProductDetailView,
    PartnerProductListView,
    PartnerStoreListView,
)

urlpatterns = [
    path("partner/stores/", PartnerStoreListView.as_view(), name="partner-stores"),
    path("partner/products/", PartnerProductListView.as_view(), name="partner-products"),
    path("partner/products/<int:pk>/", PartnerProductDetailView.as_view(), name="partner-product-detail"),
    path("partner/order-items/", PartnerOrderItemListView.as_view(), name="partner-order-items"),
    path("partner/order-items/<int:pk>/", PartnerOrderItemDetailView.as_view(), name="partner-order-item-detail"),
]
