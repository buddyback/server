import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from custom_permissions.custom_permissions import IsAdminOrReadOnly
from devices.models import Device, Session
from devices.serializers.device_serializers import DeviceClaimSerializer, DeviceSerializer, DeviceSettingsSerializer
from posture.authentication import DeviceAPIKeyAuthentication

# Long polling timeout in seconds - kept for REST API fallback
LONG_POLL_TIMEOUT = 30
POLL_INTERVAL = 0.5  # Half a second between checks

import logging

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=["devices-user"],
        description="List all devices owned by the current user",
        responses={200: DeviceSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Device List Example",
                description="Example response for listing devices",
                value=[
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "user": 1,
                        "user_username": "john_doe",
                        "name": "My Device",
                        "registration_date": "2023-10-01T12:00:00Z",
                        "is_active": True,
                        "sensitivity": 50,
                        "vibration_intensity": 50,
                        "audio_intensity": 50,
                        "has_active_session": True,
                        "is_idle": False,
                    }
                ],
            )
        ],
    ),
    retrieve=extend_schema(
        tags=["devices-user"],
        description="Retrieve a specific device",
        responses={200: DeviceSerializer},
        examples=[
            OpenApiExample(
                "Device Detail Example",
                description="Example response for a single device",
                value={
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "user": 1,
                    "user_username": "john_doe",
                    "name": "My Device",
                    "registration_date": "2023-10-01T12:00:00Z",
                    "is_active": True,
                    "sensitivity": 50,
                    "vibration_intensity": 50,
                    "audio_intensity": 50,
                    "has_active_session": True,
                    "is_idle": False,
                },
            )
        ],
    ),
    update=extend_schema(
        tags=["devices-user"],
        description="Update a device",
        request=DeviceSerializer,
        responses={200: DeviceSerializer},
    ),
    partial_update=extend_schema(
        tags=["devices-user"],
        description="Partially update a device",
        request=DeviceSerializer,
        responses={200: DeviceSerializer},
    ),
    destroy=extend_schema(tags=["devices-admin"], description="Delete a device (admin only)", responses={204: None}),
    create=extend_schema(
        tags=["devices-admin"],
        description="Create a new device (admin only). Empty request body or specify optional values.",
        request=DeviceSerializer,
        responses={201: DeviceSerializer},
        examples=[
            OpenApiExample(
                "Empty Request",
                description="Empty request will create device with default values",
                value={},
            ),
            OpenApiExample(
                "Custom Values",
                description="Specify custom values for the new device",
                value={"name": "Temperature Sensor", "sensitivity": 65, "vibration_intensity": 40},
            ),
        ],
    ),
    claim_device=extend_schema(
        tags=["devices-user"],
        description="Claim an unclaimed device",
        request=DeviceClaimSerializer,
        responses={200: DeviceSerializer},
    ),
    release_device=extend_schema(
        tags=["devices-user"],
        description="Release a device owned by the current user",
        request=None,
        responses={200: OpenApiResponse(description="Device released successfully")},
    ),
    unclaimed_devices=extend_schema(
        tags=["devices-admin"],
        description="List all unclaimed devices (admin only)",
        responses={200: DeviceSerializer(many=True)},
    ),
    device_settings=extend_schema(
        tags=["devices-api"],
        description=(
            "Get device settings including sensitivity, vibration intensity, and active status. "
            "This endpoint now supports WebSockets for real-time updates at ws://domain/ws/device-settings/{device_id}/?api_key={api_key} "
            "For backward compatibility, it also supports polling with query parameters. "
            "Requires `X-Device-ID` and `X-API-KEY` headers for authentication."
        ),
        summary="Get device settings (with optional long polling)",
        responses={
            200: DeviceSettingsSerializer,
            304: OpenApiResponse(description="No changes to device settings (long polling timeout)"),
            401: OpenApiResponse(description="Authentication failed"),
            403: OpenApiResponse(description="Device not active"),
        },
        examples=[
            OpenApiExample(
                name="Device Settings Example",
                description="Example device settings response",
                value={"sensitivity": 50, "vibration_intensity": 50, "audio_intensity": 50, "has_active_session": True},
                response_only=True,
            )
        ],
        parameters=[
            OpenApiParameter(
                name="X-Device-ID",
                location=OpenApiParameter.HEADER,
                required=True,
                type=str,
                description="UUID of the device",
            ),
            OpenApiParameter(
                name="X-API-KEY",
                location=OpenApiParameter.HEADER,
                required=True,
                type=str,
                description="API key associated with the device",
            ),
            OpenApiParameter(
                name="last_sensitivity",
                location=OpenApiParameter.QUERY,
                required=False,
                type=int,
                description="Last known sensitivity value (to enable long polling and detect changes)",
            ),
            OpenApiParameter(
                name="last_vibration_intensity",
                location=OpenApiParameter.QUERY,
                required=False,
                type=int,
                description="Last known vibration intensity (to enable long polling and detect changes)",
            ),
            OpenApiParameter(
                name="last_session_status",
                location=OpenApiParameter.QUERY,
                required=False,
                type=bool,
                description="Last known session status (active or not, to enable long polling and detect changes)",
            ),
        ],
        auth=[],
    ),
)
class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "id"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name", "registration_date"]
    ordering = ["-registration_date"]  # Default ordering

    def get_queryset(self):
        if self.action == "destroy":
            return Device.objects.filter(user__isnull=True, is_active=False)
        user = self.request.user
        return Device.objects.filter(user=user)

    def perform_create(self, serializer):
        # Create device with defaults if not specified
        serializer.save()

    def create(self, request, *args, **kwargs):
        # Handle empty request body by providing defaults
        data = request.data or {}
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not request.user.is_staff and instance.user != request.user:
            return Response({"error": _("You do not own this device.")}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Notify WebSocket clients about settings change
        self.notify_settings_change(instance)

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not request.user.is_staff and instance.user != request.user:
            return Response({"error": _("You do not own this device.")}, status=status.HTTP_403_FORBIDDEN)

        allowed_fields = ["name", "sensitivity", "vibration_intensity", "audio_intensity"]
        data = {key: value for key, value in request.data.items() if key in allowed_fields or request.user.is_staff}

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Notify WebSocket clients about settings change
        self.notify_settings_change(instance)

        return Response(serializer.data)

    def notify_settings_change(self, device):
        """
        Notify WebSocket clients about device setting changes
        """
        channel_layer = get_channel_layer()

        # Add debugging
        if channel_layer:
            # Make sure we're using the device ID in the correct format - with hyphens
            device_id = str(device.id)  # This will include hyphens
            group_name = f"device_settings_{device_id}"

            try:
                # Include more data in the event for debugging
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "device_settings_update",
                        "device_id": device_id,
                        "timestamp": str(now()),
                        "settings": {
                            "sensitivity": device.sensitivity,
                            "vibration_intensity": device.vibration_intensity,
                            "audio_intensity": device.audio_intensity,
                        },
                    },
                )
            except Exception as e:
                logger.error(f"Failed to send WebSocket notification: {str(e)}")
                logger.exception("WebSocket notification error details:")

    def perform_destroy(self, instance):
        # Only allow deletion if the user is an admin and the device is unclaimed
        if self.request.user.is_staff and instance.user is None:
            instance.delete()
            return None
        else:
            return Response(
                {"error": _("You do not have permission to delete this device.")}, status=status.HTTP_403_FORBIDDEN
            )

    @action(detail=True, methods=["post"], url_path="claim", permission_classes=[permissions.IsAuthenticated])
    def claim_device(self, request, pk=None):
        try:
            device = Device.objects.get(id=pk, user__isnull=True, is_active=False)
        except Device.DoesNotExist:
            return Response({"error": _("Device not found or already claimed.")}, status=status.HTTP_404_NOT_FOUND)

        serializer = DeviceClaimSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        name = serializer.validated_data["name"]

        device.user = request.user
        device.name = name
        device.is_active = True
        device.save()

        # Notify WebSocket clients about settings change
        self.notify_settings_change(device)

        return Response(DeviceSerializer(device).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="release", permission_classes=[permissions.IsAuthenticated])
    def release_device(self, request, pk=None):
        try:
            device = Device.objects.get(id=pk, user=request.user)
        except Device.DoesNotExist:
            return Response({"error": _("Device not found or not owned by you.")}, status=status.HTTP_404_NOT_FOUND)

        device.posture_readings.all().delete()
        device.sessions.all().delete()

        device.user = None
        device.name = "My Device"
        device.sensitivity = 50
        device.vibration_intensity = 50
        device.audio_intensity = 50
        device.is_active = False
        device.save()

        # Notify WebSocket clients about settings change
        self.notify_settings_change(device)

        return Response({"status": _("Device released successfully")}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="unclaimed", permission_classes=[permissions.IsAdminUser])
    def unclaimed_devices(self, request):
        devices = Device.objects.filter(user__isnull=True, is_active=False)
        serializer = self.get_serializer(devices, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="settings",
        authentication_classes=[DeviceAPIKeyAuthentication],
        permission_classes=[permissions.AllowAny],
    )
    def device_settings(self, request):
        """
        Get device settings including sensitivity, vibration intensity, and active status.
        If the query parameters last_sensitivity, last_vibration_intensity, or last_session_status are provided,
        this endpoint will use long polling to wait for changes.

        Note: WebSocket connection is now recommended at: ws://domain/ws/device-settings/{device_id}/?api_key={api_key}
        """
        device = request.user

        if not isinstance(device, Device):
            return Response({"error": _("Device authentication required")}, status=status.HTTP_401_UNAUTHORIZED)

        # Parse last known values from query parameters
        try:
            last_sensitivity = int(request.query_params.get("last_sensitivity", None))
        except (TypeError, ValueError):
            last_sensitivity = None

        try:
            last_vibration_intensity = int(request.query_params.get("last_vibration_intensity", None))
        except (TypeError, ValueError):
            last_vibration_intensity = None

        last_session_status = request.query_params.get("last_session_status", None)
        if last_session_status is not None:
            last_session_status = last_session_status.lower() == "true"

        # Update last_seen timestamp
        device.last_seen = now()
        device.save(update_fields=["last_seen"])

        # If no long polling parameters are provided, return current settings immediately
        if last_sensitivity is None and last_vibration_intensity is None and last_session_status is None:
            has_active_session = Session.objects.filter(device=device, end_time__isnull=True).exists()
            data = {
                "sensitivity": device.sensitivity,
                "vibration_intensity": device.vibration_intensity,
                "has_active_session": has_active_session,
            }
            return Response(data, status=status.HTTP_200_OK)

        # Keep checking for changes until timeout
        start_time = time.time()
        while time.time() - start_time < LONG_POLL_TIMEOUT:
            # Refresh device data from database to get latest settings
            device.refresh_from_db()

            # Check if there's an active session for this device
            has_active_session = Session.objects.filter(device=device, end_time__isnull=True).exists()

            # Check if any settings have changed
            settings_changed = (
                (last_sensitivity is not None and device.sensitivity != last_sensitivity)
                or (last_vibration_intensity is not None and device.vibration_intensity != last_vibration_intensity)
                or (last_session_status is not None and has_active_session != last_session_status)
            )

            if settings_changed:
                # Return updated settings
                data = {
                    "sensitivity": device.sensitivity,
                    "vibration_intensity": device.vibration_intensity,
                    "has_active_session": has_active_session,
                }
                return Response(data, status=status.HTTP_200_OK)

            # Wait before checking again to reduce database load
            time.sleep(POLL_INTERVAL)

        # If we reach here, it means timeout occurred with no changes
        return Response(status=status.HTTP_304_NOT_MODIFIED)
