from django.urls import path

from .views import AttachmentUploadView

urlpatterns = [
    path("uploads/", AttachmentUploadView.as_view(), name="attachment-upload"),
]
