from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from devices.models import Device


class PostureReading(models.Model):
    """Main model that represents a single posture reading from a device"""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="posture_readings")
    timestamp = models.DateTimeField(auto_now_add=True)
    overall_score = models.IntegerField(validators=[MinValueValidator(0)], default=0)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["device", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.device.name} - {self.timestamp} (Score: {self.overall_score})"

    def calculate_overall_score(self):
        """Calculate the overall score based on component scores"""
        components = self.components.all()
        if components:
            total = sum(component.score for component in components)
            self.overall_score = total // components.count()
            return self.overall_score
        return 0


class PostureComponent(models.Model):
    """Individual posture component measurement (neck, torso, shoulders)"""

    COMPONENT_TYPES = [
        ("neck", "Neck Position"),
        ("torso", "Torso Position"),
        ("shoulders", "Shoulders Position"),
    ]

    reading = models.ForeignKey(PostureReading, on_delete=models.CASCADE, related_name="components")
    component_type = models.CharField(max_length=10, choices=COMPONENT_TYPES)
    is_correct = models.BooleanField()
    score = models.IntegerField(validators=[MinValueValidator(0)])
    correction = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["reading", "component_type"]),
        ]
        unique_together = ["reading", "component_type"]

    def __str__(self):
        return f"{self.get_component_type_display()} for {self.reading}"
