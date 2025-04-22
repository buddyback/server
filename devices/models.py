import uuid

from django.contrib.auth.models import User
from django.db import models


class Device(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices', null=True, blank=True)
    name = models.CharField(max_length=100, default="My Device")
    registration_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)
    sensitivity = models.PositiveIntegerField(default=50)
    vibration_intensity = models.PositiveIntegerField(default=50)

    def __str__(self):
        return f"{self.name} ({self.id})"

