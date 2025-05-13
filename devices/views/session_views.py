# views.py

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from django.utils.timezone import now
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from custom_permissions.custom_permissions import IsDeviceOwner
from devices.models import Device, Session
from posture.models import PostureReading
from ranks.models import RankTier, UserRank

logger = logging.getLogger(__name__)


@extend_schema_view(
    put=extend_schema(
        description="Start a new session for a device",
        summary="Start device session",
        tags=["device-sessions"],
        responses={
            201: {"description": "Session started successfully"},
            200: {"description": "Session already active"},
            404: {"description": "Device not found"},
        },
    )
)
class SessionStartView(APIView):
    """Start a new session for a device"""

    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def put(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        active_session = device.sessions.filter(end_time__isnull=True).first()
        if active_session:
            return Response({"message": "Session already active"}, status=status.HTTP_200_OK)

        Session.objects.create(device=device)

        # Notify WebSocket clients about session status change
        self.notify_settings_change(device)

        return Response({"message": "Session started"}, status=status.HTTP_201_CREATED)

    def notify_settings_change(self, device):
        """
        Notify WebSocket clients about device setting changes
        """
        channel_layer = get_channel_layer()

        # Add debugging
        if channel_layer:
            # Make sure we're using the device ID in the correct format - with hyphens
            device_id = str(device.id)  # This will include hyphens
            group_name = f"device_settings_{device_id}"

            try:
                # Include more data in the event for debugging

                # Check if the device is idle
                is_idle = device.sessions.filter(end_time__isnull=True, is_idle=True).exists()

                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "device_settings_update",
                        "device_id": device_id,
                        "timestamp": str(now()),
                        "settings": {
                            "sensitivity": device.sensitivity,
                            "vibration_intensity": device.vibration_intensity,
                            "audio_intensity": device.audio_intensity,
                            "has_active_session": True,
                            "is_idle": is_idle,
                        },
                    },
                )
            except Exception as e:
                logger.error(f"Failed to send WebSocket notification: {str(e)}")
                logger.exception("WebSocket notification error details:")


@extend_schema_view(
    put=extend_schema(
        description="Stop the active session for a device",
        summary="Stop device session",
        tags=["device-sessions"],
        responses={
            200: {"description": "Session stopped successfully or no active session found"},
            404: {"description": "Device not found"},
        },
    )
)
class SessionStopView(APIView):
    """Stop the active session for a device"""

    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def put(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        active_session = device.sessions.filter(end_time__isnull=True).first()
        if not active_session:
            return Response({"message": "No active session"}, status=status.HTTP_200_OK)

        active_session.end_time = timezone.now()
        active_session.is_idle = False
        active_session.save()

        user = self.request.user

        # Calculate session metrics and update ranks
        self._process_session_data(user, device, active_session)

        # Initialize user ranks if they don't exist
        self._initialize_user_ranks(user)

        # Notify WebSocket clients about a session status change
        self.notify_settings_change(device)

        return Response({"message": "Session stopped"}, status=status.HTTP_200_OK)

    def _process_session_data(self, user, device, session):
        """Process all session data and calculate rank points"""
        # Get all readings created during this session
        readings = PostureReading.objects.filter(
            device=device, timestamp__gte=session.start_time, timestamp__lte=session.end_time
        )

        if not readings.exists():
            return

        # Calculate session duration in minutes
        session_duration = (session.end_time - session.start_time).total_seconds() / 60

        # Initialize category data
        categories = ["OVERALL", "NECK", "SHOULDERS", "TORSO"]
        category_data = {
            category: {
                "total_score": 0,
                "count": 0,
                "streak": 0,
                "best_streak": 0,
                "good_posture_time": 0,  # in seconds
                "bad_posture_time": 0,  # in seconds
                "prev_timestamp": None,
                "prev_was_good": False,
            }
            for category in categories
        }

        GOOD_POSTURE_THRESHOLD = device.sensitivity

        # Streaks and time tracking
        readings_sorted = readings.order_by("timestamp")

        for reading in readings_sorted:
            # Process overall score
            category_data["OVERALL"]["total_score"] += reading.overall_score
            category_data["OVERALL"]["count"] += 1

            # Track streak and time for overall
            self._track_metrics(
                category_data["OVERALL"], reading.timestamp, reading.overall_score, GOOD_POSTURE_THRESHOLD
            )

            # Process component scores
            components = reading.components.all()
            for component in components:
                category = None
                if component.component_type == "neck":
                    category = "NECK"
                elif component.component_type == "shoulders":
                    category = "SHOULDERS"
                elif component.component_type == "torso":
                    category = "TORSO"

                if category:
                    category_data[category]["total_score"] += component.score
                    category_data[category]["count"] += 1

                    # Track streak and time for this component
                    self._track_metrics(
                        category_data[category], reading.timestamp, component.score, GOOD_POSTURE_THRESHOLD
                    )

        # Calculate and award points for each category
        for category, data in category_data.items():
            if data["count"] == 0:
                continue

            # Base points from average score (0-100 scale)
            avg_score = data["total_score"] / data["count"]

            # Points calculation
            # 1. Base points from average score
            base_points = int(avg_score / 2)  # Maximum 50 points from average score

            # 2. Bonus points for session duration (up to 20 points)
            # Longer sessions give more points, capped at 30 minutes
            duration_bonus = min(int(session_duration / 1.5), 20)

            # 3. Bonus for streak (up to 15 points)
            streak_bonus = min(data["best_streak"] // 5, 15)

            # 4. Bonus for good posture percentage (up to 15 points)
            total_time = data["good_posture_time"] + data["bad_posture_time"]
            if total_time > 0:
                good_percentage = data["good_posture_time"] / total_time
                posture_bonus = int(good_percentage * 15)
            else:
                posture_bonus = 0

            # Total points for this category
            total_points = base_points + duration_bonus + streak_bonus + posture_bonus

            # Update user rank with the calculated points
            self._update_user_rank(user, category, total_points)

    def _track_metrics(self, data, timestamp, score, threshold):
        """Track streak and time metrics for a reading"""
        is_good_posture = score >= threshold

        # Update streak
        if is_good_posture:
            data["streak"] += 1
            data["best_streak"] = max(data["best_streak"], data["streak"])
        else:
            data["streak"] = 0

        # Update posture time if not the first reading
        if data["prev_timestamp"] is not None:
            time_diff = (timestamp - data["prev_timestamp"]).total_seconds()

            if data["prev_was_good"]:
                data["good_posture_time"] += time_diff
            else:
                data["bad_posture_time"] += time_diff

        # Store current state for next reading
        data["prev_timestamp"] = timestamp
        data["prev_was_good"] = is_good_posture

    def _update_user_rank(self, user, category, points):
        """Update user's rank for a specific category based on session performance"""
        user_rank, created = UserRank.objects.get_or_create(
            user=user,
            category=category,
            defaults={"tier": RankTier.objects.filter(name="NONE").first(), "current_score": 0},
        )

        # Add new points to existing score
        user_rank.current_score += points

        # Find appropriate tier based on total score
        new_tier = (
            RankTier.objects.filter(minimum_score__lte=user_rank.current_score).order_by("-minimum_score").first()
        )

        if new_tier:
            user_rank.tier = new_tier

        user_rank.save()

    def _initialize_user_ranks(self, user):
        """Ensure user has rank entries for all categories"""
        # Check if user already has any ranks
        has_ranks = UserRank.objects.filter(user=user).exists()

        if not has_ranks:
            # Get the lowest tier (NONE)
            none_tier = RankTier.objects.filter(name="NONE").first()
            if none_tier:
                # Create initial ranks for all categories
                for category_code, _ in UserRank.CATEGORY_CHOICES:
                    UserRank.objects.get_or_create(
                        user=user, category=category_code, defaults={"tier": none_tier, "current_score": 0}
                    )

    def notify_settings_change(self, device):
        """
        Notify WebSocket clients about device setting changes
        """
        channel_layer = get_channel_layer()

        # Add debugging
        if channel_layer:
            # Make sure we're using the device ID in the correct format - with hyphens
            device_id = str(device.id)  # This will include hyphens
            group_name = f"device_settings_{device_id}"

            try:

                # Check if the device is idle
                is_idle = device.sessions.filter(end_time__isnull=True, is_idle=True).exists()

                # Include more data in the event for debugging
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "device_settings_update",
                        "device_id": device_id,
                        "timestamp": str(now()),
                        "settings": {
                            "sensitivity": device.sensitivity,
                            "vibration_intensity": device.vibration_intensity,
                            "audio_intensity": device.audio_intensity,
                            "has_active_session": False,
                            "is_idle": is_idle,
                        },
                    },
                )
            except Exception as e:
                logger.error(f"Failed to send WebSocket notification: {str(e)}")
                logger.exception("WebSocket notification error details:")


@extend_schema_view(
    get=extend_schema(
        description="Check if a device has an active session",
        summary="Get device session status",
        tags=["device-sessions"],
        responses={
            200: {"description": "Returns session active status"},
            404: {"description": "Device not found"},
        },
    )
)
class SessionStatusView(APIView):
    """Check if a device has an active session"""

    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def get(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        # Get the active session (if any)
        session = device.sessions.filter(end_time__isnull=True).first()

        # A session is active if it was found, since we already filtered for end_time is None
        has_active_session = session is not None
        is_idle = session.is_idle if has_active_session else False

        return Response({"has_active_session": has_active_session, "is_idle": is_idle})


@extend_schema_view(
    get=extend_schema(
        description="Check if a device is alive based on its last seen timestamp",
        summary="Check device alive status",
        tags=["device-sessions"],
        responses={
            200: {"description": "Returns device alive status"},
            404: {"description": "Device not found"},
        },
        examples=[
            OpenApiExample("Alive Example", value={"is_alive": True}),
        ],
    )
)
class IsDeviceAlive(APIView):
    """
    Check if a device is alive based on its last seen timestamp.
    """

    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def get(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        # Check if the device is alive
        is_alive = device.last_seen and (timezone.now() - device.last_seen).total_seconds() < 60

        return Response({"is_alive": is_alive})
