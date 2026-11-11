# RestoCloud — Backend API

Multi-tenant backend for restaurant operations: POS & billing, Kitchen Display System (KDS), floor & table management, menu & recipes, inventory, reservations, staff, finance, public ordering website, and offline synchronization — with per-tenant PostgreSQL schema isolation via `django-tenants`.

## Tech Stack

- **Framework**: Python 3.12+ · [Django 5](https://www.djangoproject.com/) · [Django REST Framework](https://www.django-rest-framework.org/)
- **Multi-Tenancy**: [django-tenants](https://github.com/django-tenants/django-tenants) (PostgreSQL schema-per-tenant)
- **Authentication**: JWT via [djangorestframework-simplejwt](https://django-rest-framework-simplejwt.readthedocs.io/)
- **API Documentation**: OpenAPI / Swagger via [drf-spectacular](https://drf-spectacular.readthedocs.io/)
- **Database**: PostgreSQL 16
- **Caching & Brokers**: Redis 7
- **Web Push**: py-vapid (VAPID push notifications for KDS/orders)

## Architecture & Multi-Tenancy

`django-tenants` assigns each restaurant tenant its own PostgreSQL schema for data isolation.

- **Shared Schema (`public`)**:
  - `apps.tenants` (Tenants & Domains)
  - `apps.accounts` (SuperAdmin users)
- **Tenant Schemas**:
  - `accounts`, `branches`, `menu`, `tables`, `orders`, `inventory`
  - `customers`, `reservations`, `finance`, `website`, `notifications`, `offline`

### Tenant Routing
`HeaderAwareTenantMainMiddleware` resolves the active tenant schema from:
1. `X-Tenant-Slug` header (used by SSR, mobile app, API consumers)
2. `{slug}.localhost` subdomain (e.g. `http://himalayan-hearth.localhost:8000`)
3. `/api/v1/superadmin/*` and `/api/v1/public/*` always execute against the `public` schema.

---

## Quick Start

### 1. Prerequisites

- Python ≥ 3.11
- Docker & Docker Compose (for PostgreSQL and Redis)

### 2. Start Services

Start PostgreSQL and Redis:

```bash
docker compose up -d
```

### 3. Setup Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configuration

```bash
cp .env.example .env
```

Ensure `.env` matches your database and Redis settings.

### 5. Database Migrations

Run tenant migrations across schemas:

```bash
python manage.py migrate_schemas
```

### 6. Seed Demo Data

```bash
python manage.py seed_demo_data
```

Demo accounts (default password `Admin@12345`):
- `superadmin@restosaas.com` (SuperAdmin)
- `admin@himalayanhearth.com` (Himalayan Hearth tenant)
- `admin@tokyoramen.com` (Tokyo Ramen Lab tenant)
- `admin@lumieredining.com` (Lumière Fine Dining tenant)
- `admin@nordicroast.com` (Nordic Roast Bakery tenant)

### 7. Run Development Server

```bash
python manage.py runserver 0.0.0.0:8000
```

---

## API Documentation

When the server is running:
- Swagger UI: `http://localhost:8000/api/docs/`
- OpenAPI Schema: `http://localhost:8000/api/schema/`

---

## Verification & Management Commands

```bash
python manage.py check                          # Verify system integrity
python manage.py test                           # Run test suite
python manage.py prune_idempotency --dry-run    # Check expired offline idempotency keys
```
