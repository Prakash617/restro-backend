from rest_framework import generics, permissions, status
from rest_framework.response import Response
from apps.accounts.permissions import IsRestaurantStaff
from .models import Branch
from .serializers import BranchSerializer


class BranchListCreateView(generics.ListCreateAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(tenant, "schema_name", "public") != "public" and getattr(tenant, "plan", None):
            max_branches = getattr(tenant.plan, "max_branches", 10)
            current_branches = Branch.objects.count()
            if current_branches >= max_branches:
                return Response(
                    {
                        "code": "QUOTA_EXCEEDED",
                        "detail": (
                            f"Branch quota reached ({current_branches}/{max_branches}) for the "
                            f"{tenant.plan.name} plan. Please upgrade your subscription plan."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().create(request, *args, **kwargs)


class BranchDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsRestaurantStaff]
