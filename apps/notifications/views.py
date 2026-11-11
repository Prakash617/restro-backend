from django.db.models import Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsRestaurantStaff
from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsRestaurantStaff]

    def get_queryset(self):
        qs = Notification.objects.select_related("branch", "recipient").filter(
            Q(recipient__isnull=True) | Q(recipient=self.request.user)
        )
        unread = self.request.query_params.get("unread")
        category = self.request.query_params.get("category")
        if unread and unread.lower() in ("true", "1"):
            qs = qs.filter(is_read=False)
        if category:
            qs = qs.filter(category=category)
        return qs[:100]


class NotificationMarkReadView(APIView):
    permission_classes = [IsRestaurantStaff]

    def post(self, request, pk):
        notif = generics.get_object_or_404(Notification, pk=pk)
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notif).data, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsRestaurantStaff]

    def post(self, request):
        updated = Notification.objects.filter(
            Q(recipient__isnull=True) | Q(recipient=request.user),
            is_read=False,
        ).update(is_read=True)
        return Response(
            {"detail": f"Marked {updated} notifications as read.", "updated_count": updated},
            status=status.HTTP_200_OK,
        )
