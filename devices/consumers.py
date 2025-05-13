import json
import logging
import uuid
from datetime import timedelta
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q
from django.utils.timezone import now

from devices.models import Device, Session
from posture.serializers.device_posture_data_serializers import PostureReadingSerializer

logger = logging.getLogger(__name__)


class DeviceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.device_id = self.scope["url_route"]["kwargs"]["device_id"]
        query_string = parse_qs(self.scope["query_string"].decode())
        api_key = query_string.get("api_key", [None])[0]

        # Authenticate the device
        self.device = await self.get_device(self.device_id, api_key)
        if not self.device:
            await self.close(code=4003)
            return

        # Add to device-specific group
        self.group_name = f"device_settings_{self.device_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Accept the connection
        await self.accept()

        # Send initial device settings
        await self.send_device_settings()

    async def disconnect(self, close_code):
        if hasattr(self, "device"):
            await self.stop_active_session()

        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "")

            # Handle client-initiated heartbeats
            if message_type == "heartbeat":
                await self.update_last_seen()
                # Check if session should be stopped due to inactivity
                if await self.set_idle_mode():
                    await self.send_device_settings()
                    await self.send(
                        text_data=json.dumps(
                            {"type": "session_status", "action": "stop", "has_active_session": False, "is_idle": False}
                        )
                    )
                return

            # Handle other message types
            if message_type == "settings_request":
                await self.send_device_settings()
            elif message_type == "posture_data":
                await self.process_posture_data(data.get("data", {}))
            elif message_type == "exit_idle_mode":
                await self.exit_idle_mode(data.get("data", {}))

            # Update last_seen on any message
            await self.update_last_seen()

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "error": "Invalid JSON format"}))
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self.send(text_data=json.dumps({"type": "error", "error": f"Error processing message: {str(e)}"}))

    @sync_to_async
    def update_last_seen(self):
        try:
            self.device.last_seen = now()
            self.device.save(update_fields=["last_seen"])
            return True
        except Exception as e:
            logger.error(f"Error updating last_seen: {str(e)}")
            return False

    @sync_to_async
    def set_idle_mode(self):
        try:
            session = Session.objects.filter(device=self.device, end_time__isnull=True).first()
            if not session:
                return False

            # Check if the last PostureReading is older than 60 minutes
            time_threshold = now() - timedelta(seconds=60)  # TODO: Adjust this to 60 minutes
            last_reading = self.device.posture_readings.order_by("-timestamp").first()

            if last_reading and last_reading.timestamp < time_threshold:
                session.is_idle = True
                session.save(update_fields=["is_idle"])
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting idle mode: {str(e)}")
            return False

    @sync_to_async
    def get_device(self, device_id, api_key):
        try:
            device_uuid = uuid.UUID(device_id)
            device = Device.objects.get(Q(id=device_uuid) & Q(api_key=api_key))
            device.last_seen = now()
            device.save(update_fields=["last_seen"])
            return device
        except (Device.DoesNotExist, ValueError):
            return None

    @sync_to_async
    def refresh_device(self):
        try:
            self.device.refresh_from_db()
            return True
        except Exception as e:
            logger.error(f"Error refreshing device data: {str(e)}")
            return False

    @sync_to_async
    def get_device_settings(self):
        try:
            self.device.last_seen = now()
            self.device.save(update_fields=["last_seen"])

            session = Session.objects.filter(device=self.device, end_time__isnull=True).first()
            has_active_session = session is not None
            is_idle = session.is_idle if session else False

            return {
                "sensitivity": self.device.sensitivity,
                "vibration_intensity": self.device.vibration_intensity,
                "audio_intensity": self.device.audio_intensity,
                "has_active_session": has_active_session,
                "is_idle": is_idle,
            }
        except Exception as e:
            logger.error(f"Error getting device settings: {str(e)}")
            return {
                "sensitivity": 0,
                "vibration_intensity": 0,
                "audio_intensity": 0,
                "has_active_session": False,
                "is_idle": False,
                "error": str(e),
            }

    async def send_device_settings(self):
        settings = await self.get_device_settings()
        await self.send(text_data=json.dumps({"type": "settings", "data": settings}))

    @sync_to_async
    def process_posture_data_sync(self, data):
        try:
            if not Session.objects.filter(device=self.device, end_time__isnull=True).exists():
                return False, "Device must have an active session to submit posture data"

            data["device"] = self.device.id
            serializer = PostureReadingSerializer(data=data)
            if serializer.is_valid():
                serializer.save(device=self.device)
                return True, None
            return False, serializer.errors
        except Exception as e:
            logger.error(f"Error saving posture data: {str(e)}")
            return False, str(e)

    @sync_to_async
    def exit_idle_mode_sync(self, data):
        try:
            session = Session.objects.filter(device=self.device, end_time__isnull=True).first()
            if session:
                session.is_idle = False
                session.save(update_fields=["is_idle"])
                return True, None
            return False, "No active session found"
        except Exception as e:
            logger.error(f"Error exiting idle mode: {str(e)}")
            return False, str(e)

    async def process_posture_data(self, data):
        success, error = await self.process_posture_data_sync(data)
        response = {"type": "posture_data_response", "status": "success" if success else "error"}
        if not success:
            response["error"] = error
        await self.send(text_data=json.dumps(response))

    async def exit_idle_mode(self, data):
        success, error = await self.exit_idle_mode_sync(data)
        response = {"type": "exit_idle_mode_response", "status": "success" if success else "error"}
        if not success:
            response["error"] = error
        await self.send(text_data=json.dumps(response))

    async def device_settings_update(self, event):
        if event.get("device_id") == self.device_id:
            await self.refresh_device()
            settings = await self.get_device_settings()
            await self.send(text_data=json.dumps({"type": "settings", "data": settings}))

    async def session_status_event(self, event):
        if event.get("device_id") == self.device_id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "session_status",
                        "action": event.get("action"),
                        "has_active_session": event.get("has_active_session", False),
                    }
                )
            )

    @sync_to_async
    def stop_active_session(self):
        try:
            session = Session.objects.filter(device=self.device, end_time__isnull=True).first()
            if session:
                session.end_time = now()
                session.save(update_fields=["end_time"])
                return True
            return False
        except Exception as e:
            logger.error(f"Error stopping active session: {str(e)}")
            return False
