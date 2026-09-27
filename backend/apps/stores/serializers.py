from rest_framework import serializers

from apps.catalog.models import Product
from apps.core.services import partner_service
from apps.orders.models import OrderItem

from django.utils.text import slugify

from apps.catalog.serializers import ProductSerializer

from .models import Campaign, Store


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


class CampaignSummarySerializer(serializers.ModelSerializer):
    """Vitrine na listagem pública (home)."""

    store_name = serializers.CharField(source="store.name", read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = ["slug", "name", "description", "accent_color", "store_name", "product_count"]
        read_only_fields = fields

    def get_product_count(self, campaign) -> int:
        return len(self.context["visible_ids"].get(campaign.pk, []))


class CampaignDetailSerializer(CampaignSummarySerializer):
    products = serializers.SerializerMethodField()

    class Meta(CampaignSummarySerializer.Meta):
        fields = CampaignSummarySerializer.Meta.fields + ["products"]
        read_only_fields = fields

    def get_products(self, campaign):
        return ProductSerializer(self.context["visible_products"], many=True).data


class PartnerCampaignSerializer(serializers.ModelSerializer):
    store = serializers.PrimaryKeyRelatedField(queryset=Store.objects.none())
    products = serializers.PrimaryKeyRelatedField(many=True, queryset=Product.objects.none(), required=False)

    class Meta:
        model = Campaign
        fields = ["id", "store", "name", "slug", "description", "accent_color", "active", "starts_at", "ends_at", "products"]
        read_only_fields = ["id", "slug"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            self.fields["store"].queryset = partner_service.partner_stores(request.user)
            self.fields["products"].child_relation.queryset = partner_service.partner_products(request.user)

    def validate(self, attrs):
        store = attrs.get("store") or getattr(self.instance, "store", None)
        products = attrs.get("products")
        if products is not None and any(p.store_id != store.id for p in products):
            raise serializers.ValidationError({"products": "Só produtos desta loja entram na vitrine."})
        starts = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts and ends and ends < starts:
            raise serializers.ValidationError({"ends_at": "O fim é anterior ao início."})
        return attrs

    def create(self, validated_data):
        base = slugify(validated_data["name"])[:60] or "vitrine"
        slug, n = base, 2
        while Campaign.objects.filter(slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        validated_data["slug"] = slug
        return super().create(validated_data)
