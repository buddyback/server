from rest_framework import serializers
from posture.models import PostureData

class PostureDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostureData
        fields = ['device', 'timestamp', 'correct_shoulder_position', 'correct_neck_position']
        read_only_fields = ['timestamp', 'device']
