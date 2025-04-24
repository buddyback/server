from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse, extend_schema_view
from rest_framework import viewsets, permissions, mixins

from devices.models import Device
from posture.authentication import DeviceAPIKeyAuthentication  # custom auth
from posture.models import PostureData
from posture.serializers.device_posture_data_serializers import PostureDataSerializer


class IsDeviceAuthenticated(permissions.BasePermission):
    """
    Custom permission to check if the authenticated user is a Device instance.
    This is used in conjunction with DeviceAPIKeyAuthentication.
    """

    def has_permission(self, request, view):
        return isinstance(request.user, Device)


@extend_schema_view(
    create=extend_schema(
        tags=["posture-data-device"],
        description=(
                "Submit posture data from a Raspberry Pi device. "
                "Requires `X-Device-ID` and `X-API-KEY` headers for authentication."
        ),
        summary="Submit posture data",
        request=PostureDataSerializer,
        responses={
            201: PostureDataSerializer,
            400: OpenApiResponse(description="Invalid data or authentication"),
            403: OpenApiResponse(description="Authentication failed or device not active")
        },
        examples=[
            OpenApiExample(
                name="Posture Example",
                description="Correct shoulder and neck position submitted by a device",
                value={
                    "correct_shoulder_position": True,
                    "correct_neck_position": False
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
                description="UUID of the device"
            ),
            OpenApiParameter(
                name="X-API-KEY",
                location=OpenApiParameter.HEADER,
                required=True,
                type=str,
                description="API key associated with the device"
            ),
        ],
        auth=[]
    )
)
class PostureDataViewSet(mixins.CreateModelMixin,
                         viewsets.GenericViewSet):
    """
    ViewSet for handling posture data creation.

    Only the POST method is allowed. Devices must authenticate using custom headers:
    - `id`: the device UUID
    - `api_key`: the device’s unique API key

    Authenticated and active devices can post posture data, which will be associated
    to their device.
    """
    queryset = PostureData.objects.all()
    serializer_class = PostureDataSerializer
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = [permissions.AllowAny]  # Handled by DeviceAPIKeyAuthentication

    def get_queryset(self):
        """
        Returns posture data belonging to the authenticated device only.
        (Shouldn’t be used unless extended to support GET methods).
        """
        return PostureData.objects.filter(device=self.request.user)

    def perform_create(self, serializer):
        """
        Automatically sets the authenticated device on new posture entries.
        """
        serializer.save(device=self.request.user)
