# ranks/serializers.py
from rest_framework import serializers
from ranks.models import RankTier, UserRank

class RankTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = RankTier
        fields = ['id', 'name', 'minimum_score']
        read_only_fields = ['id']

class UserRankSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    tier = RankTierSerializer()

    class Meta:
        model = UserRank
        fields = ['id', 'user', 'category', 'tier', 'current_score', 'last_updated', 'next_tier']
        read_only_fields = ['id', 'last_updated']

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Find next tier (with higher minimum score)
        next_tier = RankTier.objects.filter(
            minimum_score__gt=instance.tier.minimum_score
        ).order_by('minimum_score').first()

        if next_tier:
            # Calculate points needed to reach next tier
            points_needed = max(0, next_tier.minimum_score - instance.current_score)
            representation['next_tier'] = {
                'name': next_tier.name,
                'minimum_score': next_tier.minimum_score,
                'points_needed': points_needed
            }
        else:
            # User has reached the highest tier
            representation['next_tier'] = None

        return representation