from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from .models import Device


class DeviceSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source='user.username')

    # Make fields optional with defaults for creation
    name = serializers.CharField(max_length=100, required=False, default="My Device")
    sensitivity = serializers.IntegerField(
        min_value=0,
        max_value=100,
        required=False,
        default=50,
        help_text="Device sensitivity level (0-100)"
    )
    vibration_intensity = serializers.IntegerField(
        min_value=0,
        max_value=100,
        required=False,
        default=50,
        help_text="Device vibration intensity level (0-100)"
    )

    class Meta:
        model = Device
        fields = ['id', 'user', 'user_username', 'name', 'registration_date', 'is_active',
                  'sensitivity', 'vibration_intensity']
        read_only_fields = ['id', 'user', 'user_username', 'registration_date', 'is_active']

        # Add examples for drf-spectacular
        swagger_schema_fields = {
            "example": {
                "name": "My Smart Device",
                "sensitivity": 75,
                "vibration_intensity": 50
            }
        }

    def validate_sensitivity(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(_("Sensitivity must be between 0 and 100"))
        return value

    def validate_vibration_intensity(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(_("Vibration intensity must be between 0 and 100"))
        return value


class DeviceClaimSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Name to assign to the device"
    )

    class Meta:
        # Add example for drf-spectacular
        swagger_schema_fields = {
            "example": {
                "name": "Living Room Sensor"
            }
        }

    def validate_name(self, value):
        if len(value.strip()) == 0:
            raise serializers.ValidationError(_("Device name cannot be empty"))
        return value