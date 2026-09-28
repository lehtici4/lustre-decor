from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Product
from .serializers import ProductSerializer


def visible_products():
    """Produto ativo da casa, ou de loja parceira ativa."""
    return Product.objects.filter(active=True).filter(Q(store__isnull=True) | Q(store__active=True)).select_related("store")


class ProductListView(generics.ListAPIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    queryset = visible_products()


class ProductDetailView(generics.RetrieveAPIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    queryset = visible_products()
