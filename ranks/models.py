from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class RankTier(models.Model):
    """Defines the tier levels and their minimum requirements"""

    TIER_CHOICES = [
        ("NONE", "None"),
        ("BRONZE", "Bronze"),
        ("SILVER", "Silver"),
        ("GOLD", "Gold"),
        ("PLATINUM", "Platinum"),
        ("DIAMOND", "Diamond"),
    ]

    name = models.CharField(max_length=20, choices=TIER_CHOICES)
    minimum_score = models.IntegerField()

    def __str__(self):
        return f"{self.name} (min: {self.minimum_score})"

    class Meta:
        ordering = ["minimum_score"]


class UserRank(models.Model):
    CATEGORY_CHOICES = [
        ("OVERALL", "Overall"),
        ("NECK", "Neck"),
        ("SHOULDERS", "Shoulders"),
        ("TORSO", "Torso"),
    ]

    """Stores user's current rank for each category"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ranks")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    tier = models.ForeignKey(RankTier, on_delete=models.CASCADE)
    current_score = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "category")

    def __str__(self):
        return f"{self.user.username} - {self.category}: {self.tier.name}"
