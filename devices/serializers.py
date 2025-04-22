from rest_framework import serializers
from .models import Device


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['id', 'user', 'name', 'registration_date', 'is_active', 'sensitivity', 'vibration_intensity']
        read_only_fields = ['id', 'user', 'registration_date', 'is_active']

class DeviceClaimSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    name = serializers.CharField(max_length=100)

class DeviceReleaseSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()

class DeviceRenameSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    name = serializers.CharField(max_length=100)
