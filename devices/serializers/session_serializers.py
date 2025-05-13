from rest_framework import serializers

from devices.models import Session


class SessionSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = "__all__"
        read_only_fields = ("start_time", "end_time", "device", "is_idle")

    def get_duration(self, obj):
        return obj.duration()
