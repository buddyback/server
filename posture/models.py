from django.db import models

from devices.models import Device


class PostureData(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='posture_data')
    timestamp = models.DateTimeField(auto_now_add=True)
    correct_shoulder_position = models.BooleanField()
    correct_neck_position = models.BooleanField()

    def __str__(self):
        return f"{self.device.name} - {self.timestamp}"
