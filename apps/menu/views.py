from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.accounts.permissions import IsRestaurantStaff
from .models import MenuCategory, MenuItem
from .serializers import MenuCategorySerializer, MenuItemSerializer


class MenuCategoryListCreateView(generics.ListCreateAPIView):
    queryset = MenuCategory.objects.select_related("parent").prefetch_related("items").all()
    serializer_class = MenuCategorySerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsRestaurantStaff()]


class MenuCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MenuCategory.objects.select_related("parent").prefetch_related("items").all()
    serializer_class = MenuCategorySerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsRestaurantStaff()]


class MenuItemListCreateView(generics.ListCreateAPIView):
    serializer_class = MenuItemSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsRestaurantStaff()]

    def get_queryset(self):
        qs = (
            MenuItem.objects.select_related("category")
            .prefetch_related("recipe_items__inventory_item")
            .all()
        )
        category = self.request.query_params.get("category")
        station = self.request.query_params.get("kitchen_station")
        available = self.request.query_params.get("is_available")
        featured = self.request.query_params.get("is_featured")
        if category:
            qs = qs.filter(category_id=category)
        if station:
            qs = qs.filter(kitchen_station=station)
        if available is not None:
            qs = qs.filter(is_available=available.lower() in ("true", "1"))
        if featured is not None:
            qs = qs.filter(is_featured=featured.lower() in ("true", "1"))
        return qs

    def create(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(tenant, "schema_name", "public") != "public" and getattr(tenant, "plan", None):
            max_items = tenant.plan.max_menu_items
            current_items = MenuItem.objects.count()
            if current_items >= max_items:
                return Response(
                    {
                        "code": "QUOTA_EXCEEDED",
                        "detail": (
                            f"Menu item quota reached ({current_items}/{max_items}) for the "
                            f"{tenant.plan.name} plan. Please upgrade your subscription plan."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().create(request, *args, **kwargs)


class MenuItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = (
        MenuItem.objects.select_related("category")
        .prefetch_related("recipe_items__inventory_item")
        .all()
    )
    serializer_class = MenuItemSerializer
    permission_classes = [permissions.AllowAny]

    def perform_update(self, serializer):
        old_price = serializer.instance.price
        item = serializer.save()
        if old_price != item.price:
            AuditLog.objects.create(
                actor=self.request.user if self.request.user.is_authenticated else None,
                actor_name=getattr(self.request.user, "full_name", "Staff"),
                action=AuditLog.Action.PRICE_UPDATED,
                target_model="MenuItem",
                target_id=str(item.id),
                description=f"Updated price of '{item.name}' from {old_price} to {item.price}.",
                metadata_json={"old_price": str(old_price), "new_price": str(item.price)},
            )


class MenuItemToggleAvailabilityView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        item = generics.get_object_or_404(MenuItem, pk=pk)
        if "is_available" in request.data:
            item.is_available = bool(request.data["is_available"])
        else:
            item.is_available = not item.is_available
        item.save(update_fields=["is_available"])
        return Response(MenuItemSerializer(item).data, status=status.HTTP_200_OK)
