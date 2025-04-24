# views.py

from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from devices.models import Device

from drf_spectacular.utils import extend_schema_view, extend_schema

from posture.models import PostureData
from posture.serializers.user_posture_data_serializers import PostureDataSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["posture-data-user"],
        summary="List posture data for a device owned by the authenticated user",
        description="Returns posture data from a specific device if the authenticated user is its owner.",
    )
)
class UserPostureDataByDeviceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PostureDataSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        device_id = self.kwargs.get('device_id')
        device = get_object_or_404(Device, id=device_id)

        if device.user != self.request.user:
            raise PermissionDenied("You do not have access to this device's data.")

        return PostureData.objects.filter(device=device)
