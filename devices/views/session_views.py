# views.py

from django.utils import timezone
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from custom_permissions.custom_permissions import IsDeviceOwner
from devices.models import Device, Session


class SessionStartView(APIView):
    """Start a new session for a device"""
    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def put(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        active_session = device.sessions.filter(end_time__isnull=True).first()
        if active_session:
            return Response({"message": "Session already active"}, status=status.HTTP_200_OK)

        Session.objects.create(device=device)
        return Response({"message": "Session started"}, status=status.HTTP_201_CREATED)


class SessionStopView(APIView):
    """Stop the active session for a device"""
    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def put(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        active_session = device.sessions.filter(end_time__isnull=True).first()
        if not active_session:
            return Response({"message": "No active session"}, status=status.HTTP_200_OK)

        active_session.end_time = timezone.now()
        active_session.save()
        return Response({"message": "Session stopped"}, status=status.HTTP_200_OK)


class SessionStatusView(APIView):
    """Check if a device has an active session"""
    permission_classes = [IsAuthenticated, IsDeviceOwner]

    def get(self, request, device_id):
        device = get_object_or_404(Device, id=device_id)

        is_active = device.sessions.filter(end_time__isnull=True).exists()
        return Response({"session_active": is_active})
