from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from custom_permissions.custom_permissions import IsDeviceOwner
from devices.models import Device
from devices.serializers.sessions_statistic_serializers import SessionStatisticsResponseSerializer


class SessionStatisticsView(APIView):
    """Calculate and return session usage statistics for a device"""

    permission_classes = [IsAuthenticated, IsDeviceOwner]

    @extend_schema(
        summary="Get device session statistics",
        description="""
        Returns comprehensive usage statistics for a specific device.

        Statistics include:
        - Current active session (if any)
        - Summary of usage (average session time, total sessions, consistency)
        - Current period stats (today, this week, this month)
        - Comparisons with previous periods
        - Usage patterns by weekday and hour
        - Chart data for daily, weekly, and monthly trends
        """,
        parameters=[
            OpenApiParameter(
                name="device_id",
                description="The unique identifier of the device",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            )
        ],
        responses={
            200: SessionStatisticsResponseSerializer,
            403: {"description": "Permission denied - not the device owner"},
            404: {"description": "Device not found"},
        },
        examples=[
            OpenApiExample(
                "Example Response",
                summary="Example response with device statistics",
                value={
                    "device_id": "12345",
                    "device_name": "Living Room Device",
                    "active_session": {
                        "start_time": "2025-04-28T10:00:00Z",
                        "current_duration_minutes": 45.5,
                        "current_duration_hours": 0.76,
                    },
                    "summary": {
                        "average_session_minutes": 32.5,
                        "total_sessions": 127,
                        "total_minutes": 4127.5,
                        "consistency_score": 78,
                        "current_streak_days": 5,
                    },
                    "current_period": {
                        "today_minutes": 65.2,
                        "today_sessions": 2,
                        "this_week_minutes": 175.5,
                        "this_week_sessions": 6,
                        "this_month_minutes": 850.3,
                        "this_month_sessions": 26,
                    },
                    "comparisons": {
                        "day_change_percent": 15.3,
                        "week_change_percent": -5.2,
                        "month_change_percent": 12.8,
                    },
                },
            )
        ],
    )
    def get(self, request, device_id):
        device = Device.objects.get(id=device_id)
        now = timezone.now()

        # Get all completed sessions
        completed_sessions = device.sessions.filter(end_time__isnull=False)
        all_completed_sessions = list(completed_sessions)

        # Collect all data components
        active_session_data = self._get_active_session_data(device, now)
        total_minutes = self._get_total_minutes(all_completed_sessions)
        avg_minutes = self._get_avg_minutes(completed_sessions)

        # Calculate time period statistics
        period_stats = self._calculate_period_stats(all_completed_sessions, now)

        # Get chart data
        chart_data = self._generate_chart_data(all_completed_sessions, now)

        # Get consistency metrics
        consistency_metrics = self._calculate_consistency_metrics(all_completed_sessions, device, now)

        # Calculate usage patterns
        usage_patterns = self._calculate_usage_patterns(all_completed_sessions)

        # Build response data
        response_data = {
            "device_id": str(device.id),
            "device_name": device.name,
            "active_session": active_session_data,
            "summary": {
                "average_session_minutes": round(avg_minutes, 1),
                "total_sessions": completed_sessions.count(),
                "total_minutes": round(total_minutes, 1),
                "consistency_score": consistency_metrics["consistency_score"],
                "current_streak_days": consistency_metrics["current_streak"],
            },
            "current_period": {
                "today_minutes": round(period_stats["today_minutes"], 1),
                "today_sessions": len(period_stats["today_sessions"]),
                "this_week_minutes": round(period_stats["this_week_minutes"], 1),
                "this_week_sessions": len(period_stats["this_week_sessions"]),
                "this_month_minutes": round(period_stats["this_month_minutes"], 1),
                "this_month_sessions": len(period_stats["this_month_sessions"]),
            },
            "comparisons": {
                "day_change_percent": (
                    round(period_stats["day_change"], 1) if period_stats["day_change"] is not None else None
                ),
                "week_change_percent": (
                    round(period_stats["week_change"], 1) if period_stats["week_change"] is not None else None
                ),
                "month_change_percent": (
                    round(period_stats["month_change"], 1) if period_stats["month_change"] is not None else None
                ),
            },
            "patterns": usage_patterns,
            "charts": chart_data,
        }

        return Response(response_data)

    def _get_active_session_data(self, device, now):
        """Get information about any currently active session"""
        active_session = device.sessions.filter(end_time__isnull=True).first()
        if not active_session:
            return None

        current_duration = now - active_session.start_time
        return {
            "start_time": active_session.start_time,
            "current_duration_minutes": round(current_duration.total_seconds() / 60, 1),
            "current_duration_hours": round(current_duration.total_seconds() / 3600, 2),
        }

    def _get_total_minutes(self, sessions):
        """Calculate total minutes from a list of sessions"""
        total_seconds = 0
        for session in sessions:
            if session.end_time:
                total_seconds += (session.end_time - session.start_time).total_seconds()
        return total_seconds / 60

    def _get_avg_minutes(self, queryset):
        """Calculate average minutes per session"""
        if not queryset.exists():
            return 0
        return self._get_total_minutes(queryset) / queryset.count()

    def _calculate_period_stats(self, all_completed_sessions, now):
        """Calculate statistics for different time periods"""
        yesterday = now - timedelta(days=1)

        # Get today's sessions
        today_sessions = [s for s in all_completed_sessions if s.start_time.date() == now.date()]
        today_minutes = self._get_total_minutes(today_sessions)

        # Get yesterday's sessions
        yesterday_sessions = [s for s in all_completed_sessions if s.start_time.date() == yesterday.date()]
        yesterday_minutes = self._get_total_minutes(yesterday_sessions)

        # Get this week's sessions (from Monday to now)
        this_week_sessions = [s for s in all_completed_sessions if s.start_time >= now - timedelta(days=now.weekday())]
        this_week_minutes = self._get_total_minutes(this_week_sessions)

        # Get last week's sessions
        last_week_sessions = [
            s
            for s in all_completed_sessions
            if s.start_time >= now - timedelta(days=now.weekday() + 7)
            and s.start_time < now - timedelta(days=now.weekday())
        ]
        last_week_minutes = self._get_total_minutes(last_week_sessions)

        # Get this month's sessions
        this_month_sessions = [
            s for s in all_completed_sessions if s.start_time.month == now.month and s.start_time.year == now.year
        ]
        this_month_minutes = self._get_total_minutes(this_month_sessions)

        # Get last month's sessions
        last_month = now.month - 1 if now.month > 1 else 12
        last_month_year = now.year if now.month > 1 else now.year - 1
        last_month_sessions = [
            s
            for s in all_completed_sessions
            if s.start_time.month == last_month and s.start_time.year == last_month_year
        ]
        last_month_minutes = self._get_total_minutes(last_month_sessions)

        # Calculate period comparisons
        day_change = ((today_minutes - yesterday_minutes) / yesterday_minutes * 100) if yesterday_minutes > 0 else None
        week_change = (
            ((this_week_minutes - last_week_minutes) / last_week_minutes * 100) if last_week_minutes > 0 else None
        )
        month_change = (
            ((this_month_minutes - last_month_minutes) / last_month_minutes * 100) if last_month_minutes > 0 else None
        )

        return {
            "today_sessions": today_sessions,
            "today_minutes": today_minutes,
            "yesterday_sessions": yesterday_sessions,
            "yesterday_minutes": yesterday_minutes,
            "this_week_sessions": this_week_sessions,
            "this_week_minutes": this_week_minutes,
            "last_week_sessions": last_week_sessions,
            "last_week_minutes": last_week_minutes,
            "this_month_sessions": this_month_sessions,
            "this_month_minutes": this_month_minutes,
            "last_month_sessions": last_month_sessions,
            "last_month_minutes": last_month_minutes,
            "day_change": day_change,
            "week_change": week_change,
            "month_change": month_change,
        }

    def _calculate_usage_patterns(self, all_completed_sessions):
        """Calculate usage patterns by weekday and hour"""
        # Calculate weekday patterns
        weekday_stats = {}
        for session in all_completed_sessions:
            weekday = session.start_time.weekday()
            if weekday not in weekday_stats:
                weekday_stats[weekday] = {"count": 0, "total_minutes": 0}
            weekday_stats[weekday]["count"] += 1
            if session.end_time:
                weekday_stats[weekday]["total_minutes"] += (session.end_time - session.start_time).total_seconds() / 60

        weekday_patterns = []
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for weekday in range(7):
            if weekday in weekday_stats:
                stats = weekday_stats[weekday]
                weekday_patterns.append(
                    {
                        "weekday": weekday_names[weekday],
                        "count": stats["count"],
                        "avg_minutes": round(stats["total_minutes"] / stats["count"], 1) if stats["count"] > 0 else 0,
                    }
                )

        # Calculate hourly patterns
        hourly_stats = {}
        for session in all_completed_sessions:
            hour = session.start_time.hour
            if hour not in hourly_stats:
                hourly_stats[hour] = {"count": 0, "total_minutes": 0}
            hourly_stats[hour]["count"] += 1
            if session.end_time:
                hourly_stats[hour]["total_minutes"] += (session.end_time - session.start_time).total_seconds() / 60

        hourly_patterns = []
        for hour in range(24):
            if hour in hourly_stats:
                stats = hourly_stats[hour]
                hourly_patterns.append(
                    {
                        "hour": hour,
                        "count": stats["count"],
                        "avg_minutes": round(stats["total_minutes"] / stats["count"], 1) if stats["count"] > 0 else 0,
                    }
                )

        return {"by_weekday": weekday_patterns, "by_hour": hourly_patterns}

    def _calculate_consistency_metrics(self, all_completed_sessions, device, now):
        """Calculate consistency score and current streak"""
        # Calculate consistency score (0-100) based on regular usage patterns
        total_days = (now.date() - device.registration_date.date()).days + 1
        days_with_sessions = len(set(session.start_time.date() for session in all_completed_sessions))
        consistency_score = round((days_with_sessions / total_days) * 100) if total_days > 0 else 0

        # Calculate streak (consecutive days with sessions)
        day_list = sorted(set(session.start_time.date() for session in all_completed_sessions), reverse=True)
        current_streak = 0
        if day_list:
            current_date = now.date()
            for i, day in enumerate(day_list):
                if day == current_date - timedelta(days=i):
                    current_streak += 1
                else:
                    break

        return {"consistency_score": consistency_score, "current_streak": current_streak}

    def _generate_chart_data(self, all_completed_sessions, now):
        """Generate time-based chart data"""
        # Group sessions by day for daily stats (last 30 days)
        days_dict = {}
        for session in all_completed_sessions:
            if session.start_time >= now - timedelta(days=30):
                day_key = session.start_time.date()
                if day_key not in days_dict:
                    days_dict[day_key] = []
                days_dict[day_key].append(session)

        formatted_daily = []
        for day, day_sessions in sorted(days_dict.items()):
            formatted_daily.append(
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "sessions": len(day_sessions),
                    "minutes": round(self._get_total_minutes(day_sessions), 1),
                }
            )

        # Group sessions by week for weekly stats (last 90 days)
        weeks_dict = {}
        for session in all_completed_sessions:
            if session.start_time >= now - timedelta(days=90):
                # Calculate week start date (Monday)
                week_start = session.start_time.date() - timedelta(days=session.start_time.weekday())
                if week_start not in weeks_dict:
                    weeks_dict[week_start] = []
                weeks_dict[week_start].append(session)

        formatted_weekly = []
        for week_start, week_sessions in sorted(weeks_dict.items()):
            formatted_weekly.append(
                {
                    "week": week_start.strftime("%Y-%m-%d"),
                    "sessions": len(week_sessions),
                    "minutes": round(self._get_total_minutes(week_sessions), 1),
                }
            )

        # Group sessions by month for monthly stats (last 365 days)
        months_dict = {}
        for session in all_completed_sessions:
            if session.start_time >= now - timedelta(days=365):
                month_key = session.start_time.strftime("%Y-%m")
                if month_key not in months_dict:
                    months_dict[month_key] = []
                months_dict[month_key].append(session)

        formatted_monthly = []
        for month, month_sessions in sorted(months_dict.items()):
            formatted_monthly.append(
                {
                    "month": month,
                    "sessions": len(month_sessions),
                    "minutes": round(self._get_total_minutes(month_sessions), 1),
                }
            )

        return {"daily": formatted_daily, "weekly": formatted_weekly, "monthly": formatted_monthly}
