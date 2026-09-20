from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "active", "updated_at"]
    list_filter = ["active"]
    search_fields = ["name"]
