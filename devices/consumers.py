import json
from uuid import UUID

from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone


class DeviceSettingsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for device settings.
    Allows real-time updates for device settings such as sensitivity,
    vibration intensity, and session status.
    """

    async def connect(self):
        """
        Connect to the WebSocket and join the device-specific group.
        Authentication is handled via query parameters containing the device API key.
        """
        from devices.models import Device

        self.device_id = self.scope["url_route"]["kwargs"]["device_id"]
        self.device_settings_group_name = f"device_settings_{self.device_id}"

        # Extract API key from query parameters
        query_string = self.scope.get("query_string", b"").decode()
        query_params = dict(param.split("=") for param in query_string.split("&") if "=" in param)
        api_key = query_params.get("api_key", None)

        # Validate device and API key
        try:
            UUID(self.device_id)  # Validate UUID format
        except ValueError:
            await self.close(code=4001)  # Invalid device ID format
            return

        try:
            device = await self.get_device()
            if not device or device.api_key != api_key:
                await self.close(code=4003)  # Unauthorized
                return

            # Update last seen timestamp
            device.last_seen = timezone.now()
            device.save(update_fields=["last_seen"])
        except Exception:
            await self.close(code=4004)  # Error
            return

        # Add to device-specific group
        await self.channel_layer.group_add(self.device_settings_group_name, self.channel_name)
        await self.accept()

        # Send initial settings to the connected client
        await self.send_device_settings()

    async def disconnect(self, close_code):
        """
        Leave the device-specific group when disconnecting.
        """
        if hasattr(self, "device_settings_group_name"):
            await self.channel_layer.group_discard(self.device_settings_group_name, self.channel_name)

    async def receive(self, text_data):
        """
        Handle incoming messages from devices.
        Currently only used for acknowledging receipt of settings.
        """
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get("type", "")

            if message_type == "acknowledgment":
                # Device acknowledges receipt of settings
                pass
            elif message_type == "ping":
                # Device sends ping to keep connection alive
                await self.send(text_data=json.dumps({"type": "pong"}))
            else:
                # Unknown message type
                pass
        except json.JSONDecodeError:
            pass

    async def device_settings_update(self, event):
        """
        Handle device settings updates from other parts of the application.
        This event is triggered when device settings are updated in the database.
        """
        await self.send_device_settings()

    async def send_device_settings(self):
        """
        Send current device settings to the connected client.
        """
        from devices.models import Session

        device = await self.get_device()
        if not device:
            return

        # Check if session is active
        has_active_session = await self.get_active_session_exists()

        # Send device settings
        await self.send(
            text_data=json.dumps(
                {
                    "type": "settings_update",
                    "settings": {
                        "sensitivity": device.sensitivity,
                        "vibration_intensity": device.vibration_intensity,
                        "has_active_session": has_active_session,
                    },
                }
            )
        )

    async def get_device(self):
        """
        Get device from database using async ORM.
        """
        from channels.db import database_sync_to_async
        from devices.models import Device

        try:
            return await database_sync_to_async(Device.objects.get)(id=self.device_id)
        except Device.DoesNotExist:
            return None

    async def get_active_session_exists(self):
        """
        Check if device has an active session using async ORM.
        """
        from channels.db import database_sync_to_async
        from devices.models import Session

        try:
            return await database_sync_to_async(Session.objects.filter)(
                device_id=self.device_id, end_time__isnull=True
            ).exists()
        except Exception:
            return False