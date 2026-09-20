from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Product
from .serializers import ProductSerializer


class ProductListView(generics.ListAPIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.filter(active=True)


class ProductDetailView(generics.RetrieveAPIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.filter(active=True)
