from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/", include("apps.tenants.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.branches.urls")),
    path("api/v1/", include("apps.menu.urls")),
    path("api/v1/", include("apps.tables.urls")),
    path("api/v1/", include("apps.orders.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.customers.urls")),
    path("api/v1/", include("apps.reservations.urls")),
    path("api/v1/", include("apps.finance.urls")),
    path("api/v1/", include("apps.website.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.offline.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
