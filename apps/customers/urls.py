from django.urls import path
from .views import (
    CouponDetailView,
    CouponListCreateView,
    CouponValidateView,
    CustomerAdjustPointsView,
    CustomerDetailView,
    CustomerFeedbackListCreateView,
    CustomerListCreateView,
    CustomerLookupView,
)

urlpatterns = [
    path("customers/", CustomerListCreateView.as_view(), name="customer-list-create"),
    path(
        "customers/lookup/",
        CustomerLookupView.as_view(),
        name="customer-lookup",
    ),
    path("customers/<int:pk>/", CustomerDetailView.as_view(), name="customer-detail"),
    path(
        "customers/<int:pk>/adjust-points/",
        CustomerAdjustPointsView.as_view(),
        name="customer-adjust-points",
    ),
    path(
        "customers/coupons/",
        CouponListCreateView.as_view(),
        name="coupon-list-create",
    ),
    path(
        "customers/coupons/validate/",
        CouponValidateView.as_view(),
        name="coupon-validate",
    ),
    path(
        "customers/coupons/<int:pk>/",
        CouponDetailView.as_view(),
        name="coupon-detail",
    ),
    path(
        "customers/feedback/",
        CustomerFeedbackListCreateView.as_view(),
        name="customer-feedback-list-create",
    ),
]
