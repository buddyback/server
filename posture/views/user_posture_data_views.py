from datetime import datetime, timedelta

from django.db.models import Avg
from django.db.models.functions import TruncDay, TruncWeek
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from devices.models import Device
from posture.models import PostureComponent, PostureReading
from posture.serializers.device_posture_data_serializers import PostureChartDataSerializer, PostureReadingSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["posture-data-user"],
        summary="List posture data for a device owned by the authenticated user",
        description="Returns posture data from a specific device if the authenticated user is its owner. "
        "Supports optional filtering by a specific date or a date range.",
        parameters=[
            OpenApiParameter(
                name="date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filter data by a specific date (e.g. 2025-04-24). Cannot be used with start_date or end_date.",
            ),
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Start date for date range filtering (e.g. 2025-04-01). Used with or without end_date.",
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="End date for date range filtering (e.g. 2025-04-24). Used with or without start_date.",
            ),
        ],
    )
)
class UserPostureDataByDeviceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for accessing posture data for a specific device owned by the authenticated user."""

    serializer_class = PostureReadingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_device(self):
        """Get and validate the device belongs to the requesting user."""
        device_id = self.kwargs.get("device_id")
        device = get_object_or_404(Device, id=device_id)

        if device.user != self.request.user:
            raise PermissionDenied(detail="You do not have access to this device's data.")

        return device

    def validate_date_params(self):
        """Validate date parameters and check for conflicting filters."""
        date_str = self.request.query_params.get("date")
        start_date_str = self.request.query_params.get("start_date")
        end_date_str = self.request.query_params.get("end_date")

        # Check for conflicting date parameters
        if date_str and (start_date_str or end_date_str):
            raise ValidationError({"error": "'date' parameter cannot be used with 'start_date' or 'end_date'"})

        # Process single date
        date = None
        if date_str:
            date = parse_date(date_str)
            if not date:
                raise ValidationError({"date": f"Invalid date format: {date_str}. Use YYYY-MM-DD."})

        # Process date range
        start_date = None
        end_date = None
        if start_date_str or end_date_str:
            if start_date_str:
                start_date = parse_date(start_date_str)
                if not start_date:
                    raise ValidationError({"start_date": f"Invalid date format: {start_date_str}. Use YYYY-MM-DD."})

            if end_date_str:
                end_date = parse_date(end_date_str)
                if not end_date:
                    raise ValidationError({"end_date": f"Invalid date format: {end_date_str}. Use YYYY-MM-DD."})

            # Validate date range if both dates provided
            if start_date and end_date and start_date > end_date:
                raise ValidationError({"error": "'start_date' cannot be after 'end_date'"})

        return {"date": date, "start_date": start_date, "end_date": end_date}

    def apply_date_filters(self, queryset, dates):
        """Apply date filters to the queryset."""
        if dates["date"]:
            return queryset.filter(timestamp__date=dates["date"])

        elif dates["start_date"] or dates["end_date"]:
            if dates["start_date"] and dates["end_date"]:
                return queryset.filter(timestamp__date__range=(dates["start_date"], dates["end_date"]))
            elif dates["start_date"]:
                return queryset.filter(timestamp__date__gte=dates["start_date"])
            else:  # Only end_date
                return queryset.filter(timestamp__date__lte=dates["end_date"])

        return queryset

    def list(self, request, *args, **kwargs):
        """Override list method to handle validation errors properly."""
        try:
            # First check device ownership
            device = self.get_device()

            # Validate and parse date parameters
            dates = self.validate_date_params()

            # Base queryset - using prefetch_related to optimize component queries
            queryset = PostureReading.objects.filter(device=device).prefetch_related(
                "components"  # Prefetch related components for performance
            )

            # Apply date filters
            queryset = self.apply_date_filters(queryset, dates)

            # Order by timestamp for consistent results
            queryset = queryset.order_by("-timestamp")

            # Set the queryset for pagination and serialization
            self.queryset = queryset

            # Continue with the standard list processing
            return super().list(request, *args, **kwargs)

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(self):
        """
        Return an empty queryset initially.
        The actual queryset is set in the list method.
        """
        if hasattr(self, "queryset"):
            return self.queryset
        return PostureReading.objects.none()

    @extend_schema(
        tags=["posture-data-user"],
        parameters=[
            OpenApiParameter(
                name="date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Date for which to get daily data (default: today)",
            ),
            OpenApiParameter(
                name="interval",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Aggregation interval in minutes (default: 1)",
            ),
        ],
        responses={200: PostureChartDataSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="daily-chart")
    def daily_chart(self, request, *args, **kwargs):
        """Return aggregated data for a specific day using configurable interval."""
        try:
            device = self.get_device()

            # Get date from query params or use today's date
            date_str = request.query_params.get("date")
            if date_str:
                chart_date = parse_date(date_str)
                if not chart_date:
                    raise ValidationError({"date": f"Invalid date format: {date_str}. Use YYYY-MM-DD."})
            else:
                chart_date = datetime.now().date()

            # Get interval from query params (in minutes)
            try:
                interval = int(request.query_params.get("interval", 1))
                if interval <= 0:
                    raise ValidationError({"interval": "Interval must be a positive integer."})
            except ValueError:
                raise ValidationError({"interval": "Interval must be a valid integer."})

            # Get all readings for the day with their components in one efficient query
            readings = (
                PostureReading.objects.filter(device=device, timestamp__date=chart_date)
                .prefetch_related("components")
                .order_by("timestamp")
            )

            # Group readings by interval
            interval_data = {}

            for reading in readings:
                # Get interval timestamp (rounded down to nearest interval)
                minutes_since_midnight = reading.timestamp.hour * 60 + reading.timestamp.minute
                interval_group = minutes_since_midnight // interval

                # Calculate the hour and minute for this interval
                interval_hour = (interval_group * interval) // 60
                interval_minute = (interval_group * interval) % 60
                time_marker = f"{interval_hour:02d}:{interval_minute:02d}"

                # Initialize interval data if needed
                if time_marker not in interval_data:
                    interval_data[time_marker] = {
                        "overall_scores": [],
                        "neck_scores": [],
                        "torso_scores": [],
                        "shoulders_scores": [],
                    }

                # Add overall score
                interval_data[time_marker]["overall_scores"].append(reading.overall_score)

                # Add component scores
                for component in reading.components.all():
                    if component.component_type == "neck":
                        interval_data[time_marker]["neck_scores"].append(component.score)
                    elif component.component_type == "torso":
                        interval_data[time_marker]["torso_scores"].append(component.score)
                    elif component.component_type == "shoulders":
                        interval_data[time_marker]["shoulders_scores"].append(component.score)

            # Calculate averages and format for frontend
            chart_data = []
            for time_marker, data in sorted(interval_data.items()):
                # Calculate averages or use 0 if no data
                overall_avg = sum(data["overall_scores"]) / len(data["overall_scores"]) if data["overall_scores"] else 0
                neck_avg = sum(data["neck_scores"]) / len(data["neck_scores"]) if data["neck_scores"] else 0
                torso_avg = sum(data["torso_scores"]) / len(data["torso_scores"]) if data["torso_scores"] else 0
                shoulders_avg = (
                    sum(data["shoulders_scores"]) / len(data["shoulders_scores"]) if data["shoulders_scores"] else 0
                )

                chart_data.append(
                    {
                        "time_marker": time_marker,
                        "overall": round(overall_avg),
                        "neck": round(neck_avg),
                        "torso": round(torso_avg),
                        "shoulders": round(shoulders_avg),
                    }
                )

            return Response(chart_data)

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["posture-data-user"],
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Start date for weekly range (default: 7 days ago)",
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="End date for weekly range (default: today)",
            ),
        ],
        responses={200: PostureChartDataSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="weekly-chart")
    def weekly_chart(self, request, *args, **kwargs):
        """Return daily aggregated data for a week for charting."""
        try:
            device = self.get_device()

            # Get date range from query params or use last 7 days
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")

            today = datetime.now().date()
            if start_date_str:
                start_date = parse_date(start_date_str)
                if not start_date:
                    raise ValidationError({"start_date": f"Invalid date format: {start_date_str}. Use YYYY-MM-DD."})
            else:
                start_date = today - timedelta(days=6)  # Last 7 days including today

            if end_date_str:
                end_date = parse_date(end_date_str)
                if not end_date:
                    raise ValidationError({"end_date": f"Invalid date format: {end_date_str}. Use YYYY-MM-DD."})
            else:
                end_date = today

            if start_date > end_date:
                raise ValidationError({"error": "'start_date' cannot be after 'end_date'"})

            # Get base queryset for the date range
            queryset = PostureReading.objects.filter(device=device, timestamp__date__range=(start_date, end_date))

            # Get component scores by type
            neck_scores = PostureComponent.objects.filter(reading__in=queryset, component_type="neck").values("reading")

            torso_scores = PostureComponent.objects.filter(reading__in=queryset, component_type="torso").values(
                "reading"
            )

            shoulders_scores = PostureComponent.objects.filter(reading__in=queryset, component_type="shoulders").values(
                "reading"
            )

            # Aggregate by day
            daily_data = (
                queryset.annotate(day=TruncDay("timestamp"))
                .values("day")
                .annotate(overall=Avg("overall_score"))
                .order_by("day")
            )

            # Format for frontend
            chart_data = []
            for entry in daily_data:
                day_str = entry["day"].strftime("%a")  # Short day name (Mon, Tue, etc.)

                # Find component scores for this day
                day_neck = (
                    neck_scores.filter(reading__timestamp__date=entry["day"].date()).aggregate(avg=Avg("score"))["avg"]
                    or 0
                )

                day_torso = (
                    torso_scores.filter(reading__timestamp__date=entry["day"].date()).aggregate(avg=Avg("score"))["avg"]
                    or 0
                )

                day_shoulders = (
                    shoulders_scores.filter(reading__timestamp__date=entry["day"].date()).aggregate(avg=Avg("score"))[
                        "avg"
                    ]
                    or 0
                )

                chart_data.append(
                    {
                        "time_marker": day_str,
                        "overall": round(entry["overall"]),
                        "neck": round(day_neck),
                        "torso": round(day_torso),
                        "shoulders": round(day_shoulders),
                    }
                )

            return Response(chart_data)

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["posture-data-user"],
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Start date for monthly range (default: 4 weeks ago)",
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="End date for monthly range (default: today)",
            ),
        ],
        responses={200: PostureChartDataSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="monthly-chart")
    def monthly_chart(self, request, *args, **kwargs):
        """Return weekly aggregated data for a month for charting."""
        try:
            device = self.get_device()

            # Get date range from query params or use last 4 weeks
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")

            today = datetime.now().date()
            if start_date_str:
                start_date = parse_date(start_date_str)
                if not start_date:
                    raise ValidationError({"start_date": f"Invalid date format: {start_date_str}. Use YYYY-MM-DD."})
            else:
                start_date = today - timedelta(weeks=4)

            if end_date_str:
                end_date = parse_date(end_date_str)
                if not end_date:
                    raise ValidationError({"end_date": f"Invalid date format: {end_date_str}. Use YYYY-MM-DD."})
            else:
                end_date = today

            if start_date > end_date:
                raise ValidationError({"error": "'start_date' cannot be after 'end_date'"})

            # Get base queryset for the date range
            queryset = PostureReading.objects.filter(device=device, timestamp__date__range=(start_date, end_date))

            # Get component scores by type
            neck_scores = PostureComponent.objects.filter(reading__in=queryset, component_type="neck").values("reading")

            torso_scores = PostureComponent.objects.filter(reading__in=queryset, component_type="torso").values(
                "reading"
            )

            shoulders_scores = PostureComponent.objects.filter(reading__in=queryset, component_type="shoulders").values(
                "reading"
            )

            # Aggregate by week
            weekly_data = (
                queryset.annotate(week=TruncWeek("timestamp"))
                .values("week")
                .annotate(overall=Avg("overall_score"))
                .order_by("week")
            )

            # Format for frontend
            chart_data = []
            for i, entry in enumerate(weekly_data):
                week_str = f"Week {i + 1}"
                week_date = entry["week"].date()

                # Find component scores for this week
                week_neck = (
                    neck_scores.filter(
                        reading__timestamp__date__range=(week_date, week_date + timedelta(days=6))
                    ).aggregate(avg=Avg("score"))["avg"]
                    or 0
                )

                week_torso = (
                    torso_scores.filter(
                        reading__timestamp__date__range=(week_date, week_date + timedelta(days=6))
                    ).aggregate(avg=Avg("score"))["avg"]
                    or 0
                )

                week_shoulders = (
                    shoulders_scores.filter(
                        reading__timestamp__date__range=(week_date, week_date + timedelta(days=6))
                    ).aggregate(avg=Avg("score"))["avg"]
                    or 0
                )

                chart_data.append(
                    {
                        "time_marker": week_str,
                        "overall": round(entry["overall"]),
                        "neck": round(week_neck),
                        "torso": round(week_torso),
                        "shoulders": round(week_shoulders),
                    }
                )

            return Response(chart_data)

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
