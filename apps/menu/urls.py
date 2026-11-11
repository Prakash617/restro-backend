from django.urls import path
from .views import (
    MenuCategoryDetailView,
    MenuCategoryListCreateView,
    MenuItemDetailView,
    MenuItemListCreateView,
    MenuItemToggleAvailabilityView,
)

urlpatterns = [
    path(
        "menu/categories/",
        MenuCategoryListCreateView.as_view(),
        name="menu-category-list-create",
    ),
    path(
        "menu/categories/<int:pk>/",
        MenuCategoryDetailView.as_view(),
        name="menu-category-detail",
    ),
    path(
        "menu/items/",
        MenuItemListCreateView.as_view(),
        name="menu-item-list-create",
    ),
    path(
        "menu/items/<int:pk>/",
        MenuItemDetailView.as_view(),
        name="menu-item-detail",
    ),
    path(
        "menu/items/<int:pk>/toggle-availability/",
        MenuItemToggleAvailabilityView.as_view(),
        name="menu-item-toggle-availability",
    ),
]
