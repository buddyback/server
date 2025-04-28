from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, viewsets

from devices.models import Device, Session
from posture.authentication import DeviceAPIKeyAuthentication  # custom auth
from posture.models import PostureReading
from posture.serializers.device_posture_data_serializers import PostureReadingSerializer


class IsDeviceAuthenticated(permissions.BasePermission):
    """
    Custom permission to check if the authenticated user is a Device instance.
    This is used in conjunction with DeviceAPIKeyAuthentication.
    """

    def has_permission(self, request, view):
        return isinstance(request.user, Device)


@extend_schema_view(
    create=extend_schema(
        tags=["devices-api"],
        description=(
            "Submit posture data from a Raspberry Pi device. There must be an active session to send data to the server."
            "Requires `X-Device-ID` and `X-API-KEY` headers for authentication."
        ),
        summary="Submit posture data",
        request=PostureReadingSerializer,
        responses={
            201: PostureReadingSerializer,
            400: OpenApiResponse(description="Invalid data or authentication"),
            403: OpenApiResponse(description="Authentication failed or device not active"),
        },
        examples=[
            OpenApiExample(
                name="Posture Example",
                description="Complete posture data with neck, torso, and shoulders measurements",
                value={
                    "components": [
                        {
                            "component_type": "neck",
                            "is_correct": False,
                            "score": 65,
                            "correction": "Adjust neck angle up slightly",
                        },
                        {
                            "component_type": "torso",
                            "is_correct": True,
                            "score": 90,
                            "correction": "",
                        },
                        {
                            "component_type": "shoulders",
                            "is_correct": False,
                            "score": 70,
                            "correction": "Pull shoulders back to reduce hunching",
                        },
                    ]
                },
                request_only=True,
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
        ],
        auth=[],
    )
)
class PostureDataViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for handling posture data creation.

    Only the POST method is allowed. Devices must authenticate using custom headers:
    - `X-Device-ID`: the device UUID
    - `X-API-KEY`: the device's unique API key

    Authenticated and active devices can post posture data, which will be associated
    to their device.
    """

    queryset = PostureReading.objects.all()
    serializer_class = PostureReadingSerializer
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = [permissions.AllowAny]  # Handled by DeviceAPIKeyAuthentication

    def get_queryset(self):
        """
        Returns posture data belonging to the authenticated device only.
        (Shouldn't be used unless extended to support GET methods).
        """
        return PostureReading.objects.filter(device=self.request.user)

    def perform_create(self, serializer):
        """
        Ensure device has an active session before allowing posture data creation.
        """

        device = self.request.user

        # Check if device has an active session
        has_active_session = Session.objects.filter(device=device, end_time__isnull=True).exists()

        if not has_active_session:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Device must have an active session to submit posture data.")

        # If active session exists, proceed to save the posture reading
        serializer.save(device=device)
