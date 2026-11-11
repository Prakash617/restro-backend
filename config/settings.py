"""
Django settings for Multi-Tenant Restaurant Management SaaS Platform.
"""

import os
import re
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

for env_file in [BASE_DIR / ".env", BASE_DIR.parent / ".env"]:
    if env_file.exists():
        load_dotenv(env_file, override=True)
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if "#" in v:
                    match = re.match(r"^['\"](.*?)['\"]\s*(?:#.*)?$", v)
                    if match:
                        v = match.group(1)
                    else:
                        v = v.split("#", 1)[0].strip()
                else:
                    v = v.strip("'\"")
                os.environ[k] = v
        except Exception:
            pass

_DEFAULT_SECRET = "django-insecure-restaurant-saas-super-secret-key-2026-prod"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _DEFAULT_SECRET)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")
    if host.strip()
]

SHARED_APPS = [
    "django_tenants",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "apps.tenants",
    "apps.branches",
    "apps.accounts",
]

TENANT_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "apps.branches",
    "apps.accounts",
    "apps.menu",
    "apps.tables",
    "apps.orders",
    "apps.inventory",
    "apps.customers",
    "apps.reservations",
    "apps.finance",
    "apps.website",
    "apps.notifications",
    "apps.offline",
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

TENANT_MODEL = "tenants.Client"
TENANT_DOMAIN_MODEL = "tenants.Domain"
PUBLIC_SCHEMA_NAME = "public"
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "config.middleware.HeaderAwareTenantMainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.offline.middleware.IdempotencyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.environ.get("POSTGRES_DB", "restaurant_saas"),
        "USER": os.environ.get("POSTGRES_USER", "restaurant_user"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "restaurant_password"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5437"),
    }
}

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-tenant-slug",
    "x-tenant-domain",
    "idempotency-key",
    "x-idempotency-key",
    "x-client-operation-id",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.TenantBoundJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "120"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.environ.get("JWT_REFRESH_DAYS", "30"))
    ),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3001").rstrip("/")

# ---------------------------------------------------------------------------
# Web Push (VAPID)
# ---------------------------------------------------------------------------
# The private key is server-only. The public key is safe to expose to browsers.
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@restosaas.local")
PUSH_NOTIFICATIONS_ENABLED = os.environ.get(
    "PUSH_NOTIFICATIONS_ENABLED", "True"
).lower() in ("true", "1", "yes")

SPECTACULAR_SETTINGS = {
    "TITLE": "Multi-Tenant Restaurant, POS, KDS & Online Ordering SaaS API",
    "DESCRIPTION": "Multi-tenant SaaS platform with SuperAdmin control center, Restaurant internal POS/KDS/Tables/Menu/Inventory/Reservations operations, and 4-theme dynamic public websites.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
