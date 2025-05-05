from rest_framework import serializers

from ranks.models import RankTier, UserRank


class RankTierSerializer(serializers.ModelSerializer):
    """Serializer for RankTier model"""

    class Meta:
        model = RankTier
        fields = ['id', 'name', 'minimum_score']
        read_only_fields = ['id']


class NextRankInfoSerializer(serializers.Serializer):
    """Serializer for next rank information"""
    name = serializers.CharField(read_only=True)
    minimum_score = serializers.IntegerField(read_only=True)
    points_needed = serializers.IntegerField(read_only=True)


class UserRankSerializer(serializers.ModelSerializer):
    """Serializer for UserRank model"""
    user = serializers.StringRelatedField()
    tier = RankTierSerializer()
    next_tier = NextRankInfoSerializer(read_only=True)

    class Meta:
        model = UserRank
        fields = ['id', 'user', 'category', 'tier', 'current_score', 'last_updated', 'next_tier']
        read_only_fields = ['id', 'last_updated']

    def to_representation(self, instance):
        """Add next tier information to the serialized data"""
        representation = super().to_representation(instance)

        # Get the next rank tier
        next_tier = RankTier.objects.filter(
            minimum_score__gt=instance.current_score
        ).order_by('minimum_score').first()

        if next_tier:
            representation['next_tier'] = {
                'name': next_tier.name,
                'minimum_score': next_tier.minimum_score,
                'points_needed': next_tier.minimum_score - instance.current_score
            }
        else:
            # If there's no next tier (user is at max rank)
            representation['next_tier'] = None

        return representation