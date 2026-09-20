from django.contrib import admin
from django.urls import include, path
from two_factor.admin import AdminSiteOTPRequired
from two_factor.urls import urlpatterns as tf_urls

admin.site.__class__ = AdminSiteOTPRequired

urlpatterns = [
    path("", include(tf_urls)),
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.orders.urls")),
]
