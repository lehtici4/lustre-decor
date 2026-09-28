from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "store", "price", "active", "updated_at"]
    list_filter = ["active", "store"]
    search_fields = ["name"]
