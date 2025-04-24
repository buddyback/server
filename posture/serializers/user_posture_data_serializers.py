# serializers.py

from rest_framework import serializers

from posture.models import PostureData


class PostureDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostureData
        fields = ['id', 'device', 'correct_shoulder_position', 'correct_neck_position', 'timestamp']
        read_only_fields = ['device', 'timestamp']
