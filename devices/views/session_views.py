# views.py

from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from custom_permissions.custom_permissions import IsDeviceOwner
from devices.models import Device, Session


@extend_schema_view(
    put=extend_schema(
        description="Start a new session for a device",
        summary="Start device session",
        tags=["device-sessions"],
        responses={
            201: {"description": "Session started successfully"},
            200: {"description": "Session already active"},
            404: {"description": "Device not found"},
        },
    )
)
class SessionStartView(APIView):
    """Start a new session for a device"""

    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def put(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        active_session = device.sessions.filter(end_time__isnull=True).first()
        if active_session:
            return Response({"message": "Session already active"}, status=status.HTTP_200_OK)

        Session.objects.create(device=device)
        return Response({"message": "Session started"}, status=status.HTTP_201_CREATED)


@extend_schema_view(
    put=extend_schema(
        description="Stop the active session for a device",
        summary="Stop device session",
        tags=["device-sessions"],
        responses={
            200: {"description": "Session stopped successfully or no active session found"},
            404: {"description": "Device not found"},
        },
    )
)
class SessionStopView(APIView):
    """Stop the active session for a device"""

    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def put(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        active_session = device.sessions.filter(end_time__isnull=True).first()
        if not active_session:
            return Response({"message": "No active session"}, status=status.HTTP_200_OK)

        active_session.end_time = timezone.now()
        active_session.save()
        return Response({"message": "Session stopped"}, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        description="Check if a device has an active session",
        summary="Get device session status",
        tags=["device-sessions"],
        responses={
            200: {"description": "Returns session active status"},
            404: {"description": "Device not found"},
        },
    )
)
class SessionStatusView(APIView):
    """Check if a device has an active session"""

    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def get(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        is_active = device.sessions.filter(end_time__isnull=True).exists()
        return Response({"session_active": is_active})


@extend_schema_view(
    get=extend_schema(
        description="Check if a device is alive based on its last seen timestamp",
        summary="Check device alive status",
        tags=["device-sessions"],
        responses={
            200: {"description": "Returns device alive status"},
            404: {"description": "Device not found"},
        },
        examples=[
            OpenApiExample("Alive Example", value={"is_alive": True}),
        ],
    )
)
class IsDeviceAlive(APIView):
    """
    Check if a device is alive based on its last seen timestamp.
    """

    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def get(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        # Check if the device is alive
        is_alive = device.last_seen and (timezone.now() - device.last_seen).total_seconds() < 5

        return Response({"is_alive": is_alive})
