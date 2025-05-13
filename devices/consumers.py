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
        # Get device_id from URL route
        self.device_id = self.scope["url_route"]["kwargs"]["device_id"]
        logger.info(f"WebSocket connection attempt for device: {self.device_id}")

        # Get API key from query string
        query_string = parse_qs(self.scope["query_string"].decode())
        api_key = query_string.get("api_key", [None])[0]

        # Authenticate the device
        device = await self.get_device(self.device_id, api_key)

        if not device:
            # Close connection if authentication fails
            logger.warning(f"WebSocket authentication failed for device: {self.device_id}")
            await self.close(code=4003)
            return

        self.device = device
        logger.info(f"Device authenticated: {self.device_id}")

        # Add to device-specific group
        self.group_name = f"device_settings_{self.device_id}"
        logger.info(f"Adding to group: {self.group_name}")

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        logger.info(f"Added to group: {self.group_name}")

        # Accept the connection
        await self.accept()
        logger.info(f"WebSocket connection accepted for device: {self.device_id}")

        # Send initial device settings
        await self.send_device_settings()

        # Removed server-initiated heartbeat task

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnecting for device: {self.device_id}, code: {close_code}")

        # Stop the session if it exists
        if hasattr(self, "device"):
            session_stopped = await self.stop_active_session()
            if session_stopped:
                logger.info(f"Session ended for device: {self.device_id} on disconnect")
            else:
                logger.info(f"No active session found for device: {self.device_id}")

        # Remove from device group
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(f"Removed from group: {self.group_name}")

    async def receive(self, text_data):
        logger.info(f"Received WebSocket message from device: {self.device_id}")

        # Handle incoming messages
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "")

            # Handle client-initiated heartbeats
            if message_type == "heartbeat":
                logger.debug(f"Heartbeat received from device: {self.device_id}")
                await self.update_last_seen()
                # Check if session should be stopped due to inactivity
                session_stopped = await self.stop_session_if_no_data_received_for_too_long()
                if session_stopped:
                    logger.info(f"Session stopped due to inactivity for device: {self.device_id}")
                    # Send updated settings to notify the device
                    await self.send_device_settings()
                    # Explicitly notify about the session status
                    await self.send(text_data=json.dumps({
                        "type": "session_status",
                        "action": "stop",
                        "has_active_session": False
                    }))
                return

            # Handle settings requests
            if message_type == "settings_request":
                logger.info(f"Get settings request from device: {self.device_id}")
                await self.send_device_settings()

            # Handle posture data submissions
            elif message_type == "posture_data":
                logger.info(f"Posture data received from device: {self.device_id}")
                await self.process_posture_data(data.get("data", {}))

            # Always update last_seen on any message
            await self.update_last_seen()

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received from device: {self.device_id}")
            await self.send(text_data=json.dumps({"type": "error", "error": "Invalid JSON format"}))
        except Exception as e:
            logger.error(f"Error processing message from device: {str(e)}")
            await self.send(text_data=json.dumps({"type": "error", "error": f"Error processing message: {str(e)}"}))

    @sync_to_async
    def update_last_seen(self):
        """Update the device's last_seen timestamp"""
        try:
            self.device.last_seen = now()
            self.device.save(update_fields=["last_seen"])
            logger.debug(f"Updated last_seen for device: {self.device_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating last_seen: {str(e)}")
            return False

    @sync_to_async
    def stop_session_if_no_data_received_for_too_long(self):
        try:
            session = Session.objects.filter(device=self.device, end_time__isnull=True).first()

            if session:
                # Check if the last PostureReading is older than 60 minutes
                time_threshold = now() - timedelta(seconds=60*60)

                last_reading = self.device.posture_readings.order_by("-timestamp").first()

                if last_reading and last_reading.timestamp > time_threshold:
                    session.end_time = now()
                    session.save(update_fields=["end_time"])
                    logger.info(f"Session stopped for device: {self.device_id} due to inactivity")
                    return True
                return False
            return False
        except Exception as e:
            logger.error(f"Error updating last_seen: {str(e)}")
            return False

    @sync_to_async
    def get_device(self, device_id, api_key):
        """Authenticate device using ID and API key"""
        try:
            device_uuid = uuid.UUID(device_id)
            device = Device.objects.get(Q(id=device_uuid) & Q(api_key=api_key))

            # Update last_seen on authentication
            device.last_seen = now()
            device.save(update_fields=["last_seen"])

            return device
        except (Device.DoesNotExist, ValueError) as e:
            logger.warning(f"Device authentication failed: {str(e)}")
            return None

    @sync_to_async
    def refresh_device(self):
        """Refresh device data from the database"""
        try:
            logger.info(f"Refreshing device data for: {self.device_id}")
            self.device.refresh_from_db()
            return True
        except Exception as e:
            logger.error(f"Error refreshing device data: {str(e)}")
            return False

    @sync_to_async
    def get_device_settings(self):
        """Get current device settings"""
        try:
            # Update last_seen timestamp
            self.device.last_seen = now()
            self.device.save(update_fields=["last_seen"])

            # Check if there's an active session
            has_active_session = Session.objects.filter(device=self.device, end_time__isnull=True).exists()

            settings = {
                "sensitivity": self.device.sensitivity,
                "vibration_intensity": self.device.vibration_intensity,
                "audio_intensity": self.device.audio_intensity,
                "has_active_session": has_active_session,
            }

            logger.info(f"Device settings retrieved: {settings}")
            return settings
        except Exception as e:
            logger.error(f"Error getting device settings: {str(e)}")
            return {
                "sensitivity": 0,
                "vibration_intensity": 0,
                "audio_intensity": 0,
                "has_active_session": False,
                "error": str(e),
            }

    async def send_device_settings(self):
        """Send current device settings to the client"""
        settings = await self.get_device_settings()
        logger.info(f"Sending settings to device: {self.device_id}, settings: {settings}")
        await self.send(text_data=json.dumps({"type": "settings", "data": settings}))

    @sync_to_async
    def process_posture_data_sync(self, data):
        """Process and save posture data (synchronous)"""
        try:
            # Check if device has an active session
            has_active_session = Session.objects.filter(device=self.device, end_time__isnull=True).exists()

            if not has_active_session:
                logger.warning(f"Device {self.device_id} attempted to submit posture data without active session")
                return False, "Device must have an active session to submit posture data"

            # Add device to the data
            data["device"] = self.device.id

            # Use the serializer for validation and saving
            serializer = PostureReadingSerializer(data=data)
            if serializer.is_valid():
                serializer.save(device=self.device)
                logger.info(f"Posture data saved successfully for device: {self.device_id}")
                return True, None
            else:
                logger.warning(f"Invalid posture data from device {self.device_id}: {serializer.errors}")
                return False, serializer.errors
        except Exception as e:
            logger.error(f"Error saving posture data: {str(e)}")
            return False, str(e)

    async def process_posture_data(self, data):
        """Process incoming posture data"""
        success, error = await self.process_posture_data_sync(data)

        if success:
            # Send success response
            await self.send(text_data=json.dumps({"type": "posture_data_response", "status": "success"}))
        else:
            # Send error response
            await self.send(text_data=json.dumps({"type": "posture_data_response", "status": "error", "error": error}))

    async def device_settings_update(self, event):
        """Handle device settings update event from channel layer"""
        device_id = event.get("device_id")
        logger.info(f"Received settings update event for device: {device_id} at {now()}")
        logger.info(f"Full event data: {event}")

        # Only send updates if it's for this device
        if device_id == self.device_id:
            logger.info(f"Processing settings update for device: {self.device_id}")
            # The critical fix: Refresh the device data from database before sending settings
            refresh_success = await self.refresh_device()
            logger.info(f"Device refresh {'successful' if refresh_success else 'failed'}")

            # Get updated settings
            settings = await self.get_device_settings()
            logger.info(f"SENDING UPDATED settings to device: {settings}")

            # Send the updated settings to the client
            await self.send(text_data=json.dumps({"type": "settings", "data": settings}))
            logger.info(f"Settings update message sent successfully at {now()}")
        else:
            logger.warning(f"Ignoring settings update - device ID mismatch: expected {self.device_id}, got {device_id}")

    async def session_status_event(self, event):
        """Handle session status events (start/stop)"""
        device_id = event.get("device_id")
        action = event.get("action")
        has_active_session = event.get("has_active_session", False)

        # Only process if it's for this device
        if device_id == self.device_id:
            logger.info(f"Received session {action} event for device: {self.device_id}")

            # Forward the session status to the device
            await self.send(
                text_data=json.dumps(
                    {"type": "session_status", "action": action, "has_active_session": has_active_session}
                )
            )

            logger.info(f"Sent session {action} event to device: {self.device_id}")
        else:
            logger.warning(f"Ignoring session event - device ID mismatch: expected {self.device_id}, got {device_id}")

    @sync_to_async
    def stop_active_session(self):
        """Stop active session for the device"""
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