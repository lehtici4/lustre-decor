from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "image_url", "store_name"]
        read_only_fields = fields

    store_name = serializers.SerializerMethodField()

    def get_store_name(self, product) -> str:
        return product.store.name if product.store_id else "Lustre Decor"
