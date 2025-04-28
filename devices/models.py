import secrets
import uuid

from django.contrib.auth.models import User
from django.db import models


class Device(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices", null=True, blank=True)
    name = models.CharField(max_length=100, default="My Device")
    registration_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)
    sensitivity = models.PositiveIntegerField(default=50)
    vibration_intensity = models.PositiveIntegerField(default=50)
    api_key = models.CharField(max_length=255, unique=True, editable=False)

    def __str__(self):
        return f"{self.name} ({self.id})"

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)


class Session(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="sessions")
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)

    def is_active(self):
        """Returns True if session is still ongoing"""
        return self.end_time is None

    def duration(self):
        """Returns session duration if ended"""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def __str__(self):
        return f"Session for {self.device.name} starting {self.start_time}"
