from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

PUBLIC_SCHEMA_NAME = "public"
TENANT_TOKEN_MISMATCH = "tenant_token_mismatch"
TENANT_TOKEN_ON_PUBLIC = "tenant_token_on_public_endpoint"


class TenantBoundJWTAuthentication(JWTAuthentication):
    """Rejects JWTs whose ``tenant_slug`` claim disagrees with the active tenant."""

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        self.assert_tenant_binding(request, validated_token)
        return self.get_user(validated_token), validated_token

    @staticmethod
    def assert_tenant_binding(request, validated_token):
        token_slug = (
            validated_token.payload.get("tenant_slug")
            or validated_token.payload.get("tenant")
            or ""
        )
        if not isinstance(token_slug, str) or not token_slug.strip():
            return

        token_slug = token_slug.strip().lower()

        tenant = getattr(request, "tenant", None)
        active_slug = (
            getattr(tenant, "slug", None)
            or getattr(tenant, "schema_name", None)
            or ""
        )
        if not isinstance(active_slug, str) or not active_slug.strip():
            return

        active_slug = active_slug.strip().lower()

        if active_slug == PUBLIC_SCHEMA_NAME:
            if token_slug != PUBLIC_SCHEMA_NAME:
                raise exceptions.AuthenticationFailed(
                    "This session token belongs to a restaurant workspace and "
                    "cannot be used on platform (public) endpoints.",
                    code=TENANT_TOKEN_ON_PUBLIC,
                )
            return

        if token_slug != active_slug:
            raise exceptions.AuthenticationFailed(
                f"Session token does not belong to the active restaurant workspace (expected '{active_slug}').",
                code=TENANT_TOKEN_MISMATCH,
            )
