from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Device
from .serializers import (
    DeviceSerializer,
    DeviceClaimSerializer,
    DeviceReleaseSerializer,
    DeviceRenameSerializer
)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_staff:
            return True
        if view.action in ['list', 'claim_device', 'release_device', 'rename_device']:
            return request.user and request.user.is_authenticated
        return False


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'id']
    filterset_fields = ['is_active']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Device.objects.all()
        return Device.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save()

    @extend_schema(
        request=DeviceClaimSerializer,
        responses=DeviceSerializer,
        methods=['POST'],
        description="Claim a device by providing the device ID and assigning a name to it."
    )
    @action(detail=False, methods=['post'], url_path='claim', permission_classes=[permissions.IsAuthenticated])
    def claim_device(self, request):
        serializer = DeviceClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_id = serializer.validated_data['device_id']
        name = serializer.validated_data['name']

        try:
            device = Device.objects.get(id=device_id, user__isnull=True, is_active=False)
        except Device.DoesNotExist:
            return Response({'error': 'Device not found or already claimed.'}, status=status.HTTP_404_NOT_FOUND)

        device.user = request.user
        device.name = name
        device.is_active = True
        device.save()

        return Response(DeviceSerializer(device).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=DeviceReleaseSerializer,
        responses=DeviceSerializer,
        methods=['POST'],
        description="Release a device previously claimed by the user."
    )
    @action(detail=False, methods=['post'], url_path='release', permission_classes=[permissions.IsAuthenticated])
    def release_device(self, request):
        serializer = DeviceReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_id = serializer.validated_data['device_id']

        try:
            device = Device.objects.get(id=device_id, user=request.user)
        except Device.DoesNotExist:
            return Response({'error': 'Device not found or not owned by you.'}, status=status.HTTP_404_NOT_FOUND)

        device.user = None
        device.is_active = False
        device.save()

        return Response({'status': 'Device released successfully'}, status=status.HTTP_200_OK)

    @extend_schema(
        request=DeviceRenameSerializer,
        responses=DeviceSerializer,
        methods=['PUT'],
        description="Rename a device owned by the current user. You must provide the device ID and the new name."
    )
    @action(detail=False, methods=['put'], url_path='rename', permission_classes=[permissions.IsAuthenticated])
    def rename_device(self, request):
        serializer = DeviceRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_id = serializer.validated_data['device_id']
        name = serializer.validated_data['name']

        try:
            device = Device.objects.get(id=device_id, user=request.user)
        except Device.DoesNotExist:
            return Response({'error': 'Device not found or not owned by you.'}, status=status.HTTP_404_NOT_FOUND)

        device.name = name
        device.save()

        return Response(DeviceSerializer(device).data, status=status.HTTP_200_OK)
