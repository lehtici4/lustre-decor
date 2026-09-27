from rest_framework import serializers

from apps.catalog.models import Product
from apps.core.services import partner_service
from apps.orders.models import OrderItem

from .models import Store


class PartnerStoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "name"]
        read_only_fields = fields


class PartnerProductSerializer(serializers.ModelSerializer):
    store = serializers.PrimaryKeyRelatedField(queryset=Store.objects.none())
    store_name = serializers.CharField(source="store.name", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "store", "store_name", "name", "description", "price", "active", "image_url", "updated_at"]
        read_only_fields = ["id", "store_name", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            # Só as lojas do próprio parceiro são aceitas — produto em loja
            # alheia é recusado como "objeto inexistente" (400).
            self.fields["store"].queryset = partner_service.partner_stores(request.user)

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("O preço deve ser maior que zero.")
        return value

    def validate_image_url(self, value: str) -> str:
        # Só caminho local (/products/x.webp) ou https — nada de javascript:,
        # data: ou http em claro vindo de um usuário não-admin.
        if value and not (value.startswith("/") or value.startswith("https://")):
            raise serializers.ValidationError("Use um caminho /... ou uma URL https://.")
        return value


class PartnerOrderItemSerializer(serializers.ModelSerializer):
    """Item de pedido visto pelo parceiro: o necessário para despachar, sem
    dados do cliente (username/e-mail) nem os itens de outras lojas."""

    order_id = serializers.IntegerField(source="order.id", read_only=True)
    order_created_at = serializers.DateTimeField(source="order.created_at", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order_id",
            "order_created_at",
            "order_status",
            "store_name",
            "product_name",
            "unit_price",
            "quantity",
            "fulfillment_status",
        ]
        read_only_fields = [f for f in fields if f != "fulfillment_status"]
