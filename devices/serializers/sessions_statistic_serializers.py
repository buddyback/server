from rest_framework import serializers


class ActiveSessionSerializer(serializers.Serializer):
    start_time = serializers.DateTimeField()
    current_duration_minutes = serializers.FloatField()
    current_duration_hours = serializers.FloatField()


class SummarySerializer(serializers.Serializer):
    average_session_minutes = serializers.FloatField()
    total_sessions = serializers.IntegerField()
    total_minutes = serializers.FloatField()
    consistency_score = serializers.IntegerField()
    current_streak_days = serializers.IntegerField()


class CurrentPeriodSerializer(serializers.Serializer):
    today_minutes = serializers.FloatField()
    today_sessions = serializers.IntegerField()
    this_week_minutes = serializers.FloatField()
    this_week_sessions = serializers.IntegerField()
    this_month_minutes = serializers.FloatField()
    this_month_sessions = serializers.IntegerField()


class ComparisonsSerializer(serializers.Serializer):
    day_change_percent = serializers.FloatField(allow_null=True)
    week_change_percent = serializers.FloatField(allow_null=True)
    month_change_percent = serializers.FloatField(allow_null=True)


class WeekdayPatternSerializer(serializers.Serializer):
    weekday = serializers.CharField()
    count = serializers.IntegerField()
    avg_minutes = serializers.FloatField()


class HourlyPatternSerializer(serializers.Serializer):
    hour = serializers.IntegerField()
    count = serializers.IntegerField()
    avg_minutes = serializers.FloatField()


class PatternsSerializer(serializers.Serializer):
    by_weekday = WeekdayPatternSerializer(many=True)
    by_hour = HourlyPatternSerializer(many=True)


class DailyChartSerializer(serializers.Serializer):
    date = serializers.CharField()
    sessions = serializers.IntegerField()
    minutes = serializers.FloatField()


class WeeklyChartSerializer(serializers.Serializer):
    week = serializers.CharField()
    sessions = serializers.IntegerField()
    minutes = serializers.FloatField()


class MonthlyChartSerializer(serializers.Serializer):
    month = serializers.CharField()
    sessions = serializers.IntegerField()
    minutes = serializers.FloatField()


class ChartsSerializer(serializers.Serializer):
    daily = DailyChartSerializer(many=True)
    weekly = WeeklyChartSerializer(many=True)
    monthly = MonthlyChartSerializer(many=True)


class SessionStatisticsResponseSerializer(serializers.Serializer):
    device_id = serializers.CharField()
    device_name = serializers.CharField()
    active_session = ActiveSessionSerializer(allow_null=True)
    summary = SummarySerializer()
    current_period = CurrentPeriodSerializer()
    comparisons = ComparisonsSerializer()
    patterns = PatternsSerializer()
    charts = ChartsSerializer()
