from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from devices.models import Device


class DeviceSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source="user.username")
    has_active_session = serializers.SerializerMethodField(
        help_text="Indicates whether the device has an active session"
    )

    name = serializers.CharField(max_length=100, required=False, default="My Device")
    sensitivity = serializers.IntegerField(
        min_value=0, max_value=100, required=False, default=50, help_text="Device sensitivity level (0-100)"
    )
    vibration_intensity = serializers.IntegerField(
        min_value=0, max_value=100, required=False, default=50, help_text="Device vibration intensity level (0-100)"
    )
    audio_intensity = serializers.IntegerField(
        min_value=0, max_value=100, required=False, default=50, help_text="Device audio intensity level (0-100)"
    )

    class Meta:
        model = Device
        fields = [
            "id",
            "user",
            "user_username",
            "name",
            "registration_date",
            "is_active",
            "sensitivity",
            "vibration_intensity",
            "audio_intensity",
            "api_key",
            "has_active_session",
            "last_seen",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_username",
            "registration_date",
            "is_active",
            "has_active_session",
            "api_key",
            "last_seen",
        ]

        swagger_schema_fields = {
            "example": {
                "name": "My Smart Device",
                "sensitivity": 75,
                "vibration_intensity": 50,
                "audio_intensity": 50,
                "has_active_session": False,
                "last_seen": "2023-10-01T12:00:00Z",
            }
        }

    def get_has_active_session(self, obj):
        """
        Check if the device has an active session
        """
        return obj.sessions.filter(end_time__isnull=True).exists()

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Only include `api_key` if user is admin
        request = self.context.get("request")
        if not request or not request.user.is_staff:
            representation.pop("api_key", None)

        return representation

    def validate_sensitivity(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(_("Sensitivity must be between 0 and 100"))
        return value

    def validate_vibration_intensity(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(_("Vibration intensity must be between 0 and 100"))
        return value

    def validate_audio_intensity(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(_("Audio intensity must be between 0 and 100"))
        return value


class DeviceClaimSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=True, help_text="Name to assign to the device")

    class Meta:
        # Add example for drf-spectacular
        swagger_schema_fields = {"example": {"name": "Living Room Sensor"}}

    def validate_name(self, value):
        if len(value.strip()) == 0:
            raise serializers.ValidationError(_("Device name cannot be empty"))
        return value


class DeviceSettingsSerializer(serializers.Serializer):
    sensitivity = serializers.IntegerField()
    vibration_intensity = serializers.IntegerField()
    audio_intensity = serializers.IntegerField()
    has_active_session = serializers.BooleanField()
