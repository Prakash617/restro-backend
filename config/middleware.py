from django.db import connection
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

PUBLIC_PATH_PREFIXES = (
    "/api/v1/auth/login/",
    "/api/v1/public/",
    "/api/v1/superadmin/",
    "/api/docs/",
    "/api/schema/",
    "/admin/",
    "/media/",
)

OPTIONAL_TENANT_PREFIXES = (
    "/api/v1/auth/refresh/",
    "/api/v1/auth/me/",
    "/api/v1/auth/pin-login/",
)


def is_public_path(path):
    path = path or "/"
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def is_optional_tenant_path(path):
    path = path or "/"
    return any(path.startswith(prefix) for prefix in OPTIONAL_TENANT_PREFIXES)


class HeaderAwareTenantMainMiddleware(MiddlewareMixin):
    """
    Hybrid Multi-Tenant Resolution Middleware:
    1. Routes under /api/v1/superadmin/, /api/v1/public/, /api/docs/, /api/schema/, /admin/
       always execute against the `public` schema.
    2. Otherwise checks `X-Tenant-Slug` HTTP header or `?tenant=` query parameter.
    3. Otherwise extracts subdomain from the `Host` header (`{slug}.localhost` or Domain table).
    4. Falls back to `public` schema.
    5. Enforces suspension status (HTTP 403 TENANT_SUSPENDED) for suspended/inactive tenants.
    """

    PUBLIC_PATH_PREFIXES = PUBLIC_PATH_PREFIXES

    def _get_public_tenant(self, ClientModel):
        return ClientModel.objects.filter(schema_name="public").first()

    def _resolve_tenant(self, request, ClientModel, DomainModel):
        path = request.path_info or "/"
        if is_public_path(path):
            return self._get_public_tenant(ClientModel)

        header_slug = (
            request.META.get("HTTP_X_TENANT_SLUG")
            or request.GET.get("tenant")
            or ""
        ).strip().lower()

        if header_slug:
            if header_slug == "public":
                return self._get_public_tenant(ClientModel)
            tenant = (
                ClientModel.objects.select_related("plan")
                .filter(slug__iexact=header_slug)
                .first()
            )
            if not tenant:
                tenant = (
                    ClientModel.objects.select_related("plan")
                    .filter(schema_name__iexact=header_slug)
                    .first()
                )
            if tenant:
                return tenant

        host_header = request.get_host() if hasattr(request, "get_host") else ""
        hostname = host_header.split(":")[0].strip().lower()

        if hostname and hostname not in ("localhost", "127.0.0.1", "testserver"):
            domain_obj = (
                DomainModel.objects.select_related("tenant", "tenant__plan")
                .filter(domain__iexact=hostname)
                .first()
            )
            if domain_obj and domain_obj.tenant:
                return domain_obj.tenant

            parts = hostname.split(".")
            if len(parts) >= 2 and parts[0] not in ("www", "localhost", "127"):
                sub_slug = parts[0]
                tenant = (
                    ClientModel.objects.select_related("plan")
                    .filter(slug__iexact=sub_slug)
                    .first()
                )
                if tenant:
                    return tenant

        return self._get_public_tenant(ClientModel)

    def process_request(self, request):
        from apps.tenants.models import Client, Domain

        connection.set_schema_to_public()
        try:
            tenant = self._resolve_tenant(request, Client, Domain)
        except Exception:
            tenant = None

        path = request.path_info or "/"
        is_public_route = is_public_path(path)
        is_optional_route = is_optional_tenant_path(path)

        if tenant is not None:
            request.tenant = tenant
            connection.set_tenant(tenant)

            if not is_public_route and not is_optional_route and tenant.schema_name == "public":
                return JsonResponse(
                    {
                        "code": "TENANT_REQUIRED",
                        "detail": (
                            "No active restaurant workspace selected. "
                            "Please pass X-Tenant-Slug header or use a tenant subdomain."
                        ),
                    },
                    status=400,
                )

            if tenant.schema_name != "public" and (
                not tenant.is_active or tenant.subscription_status == "SUSPENDED"
            ):
                return JsonResponse(
                    {
                        "code": "TENANT_SUSPENDED",
                        "detail": f"{tenant.name} workspace is currently suspended by platform administration.",
                        "tenant": tenant.name,
                        "tenant_name": tenant.name,
                        "tenant_slug": tenant.slug,
                    },
                    status=403,
                )
        else:
            request.tenant = None
            connection.set_schema_to_public()
        return None
