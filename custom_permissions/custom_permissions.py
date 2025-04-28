from rest_framework import permissions

from devices.models import Device


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_staff:
            return True
        if view.action in ["list", "claim_device", "release_device", "retrieve", "update", "partial_update"]:
            return request.user and request.user.is_authenticated
        return False


class IsDeviceOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of a device to access its sessions.
    """

    def has_permission(self, request, view):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Get device_id from URL kwargs
        device_id = view.kwargs.get('device_id')
        if not device_id:
            return False

        # Check if the user is the owner of this device
        try:
            device = Device.objects.get(id=device_id)
            return device.user == request.user
        except Device.DoesNotExist:
            return False
