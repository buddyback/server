from rest_framework import serializers

from posture.models import PostureComponent, PostureReading


class PostureComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostureComponent
        fields = ["component_type", "is_correct", "score", "correction"]


class PostureReadingSerializer(serializers.ModelSerializer):
    components = PostureComponentSerializer(many=True)

    class Meta:
        model = PostureReading
        fields = ["device", "timestamp", "overall_score", "components"]
        read_only_fields = ["timestamp", "device", "overall_score"]

    def create(self, validated_data):
        components_data = validated_data.pop("components")

        # First create the reading with default score of 0
        reading = PostureReading.objects.create(**validated_data)

        # Calculate total score from components
        total_score = 0
        component_count = len(components_data)

        # Create all component records
        for component_data in components_data:
            PostureComponent.objects.create(reading=reading, **component_data)
            total_score += component_data["score"]

        # Calculate and save the overall score
        if component_count > 0:
            reading.overall_score = total_score // component_count
            reading.save(update_fields=["overall_score"])

        return reading

    def validate_components(self, components):
        """Validate that all required component types are present and no duplicates exist"""
        if not components:
            raise serializers.ValidationError("At least one posture component is required")

        component_types = [component["component_type"] for component in components]
        required_types = ["neck", "torso", "shoulders"]

        # Check for duplicates
        if len(component_types) != len(set(component_types)):
            raise serializers.ValidationError("Duplicate component types are not allowed")

        # Check for all required component types
        missing_types = set(required_types) - set(component_types)
        if missing_types:
            raise serializers.ValidationError(f"Missing required component types: {', '.join(missing_types)}")

        return components


class PostureChartDataSerializer(serializers.Serializer):
    """Serializer for aggregated posture chart data"""
    time_marker = serializers.CharField()  # Could be hour, day, or week depending on view
    overall = serializers.IntegerField()
    neck = serializers.IntegerField()
    torso = serializers.IntegerField()
    shoulders = serializers.IntegerField()
