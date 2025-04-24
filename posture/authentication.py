import uuid
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Device

class DeviceAPIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        device_id = request.headers.get('X-Device-ID')
        api_key = request.headers.get('X-API-KEY')

        if not device_id or not api_key:
            return None

        # Validate UUID format
        try:
            uuid_obj = uuid.UUID(device_id)
        except ValueError:
            raise AuthenticationFailed("Invalid device ID format (must be a UUID)")

        try:
            device = Device.objects.get(id=uuid_obj, api_key=api_key, is_active=True)
        except Device.DoesNotExist:
            raise AuthenticationFailed("Invalid device credentials")

        return device, None
