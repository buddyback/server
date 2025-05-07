import asyncio
import json
import logging
import uuid
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q
from django.utils.timezone import now

from devices.models import Device, Session

logger = logging.getLogger(__name__)


class DeviceSettingsConsumer(AsyncWebsocketConsumer):
    # Add these attributes to the class
    heartbeat_interval = 30  # seconds
    heartbeat_task = None

    async def connect(self):
        # Get device_id from URL route
        self.device_id = self.scope['url_route']['kwargs']['device_id']
        logger.info(f"WebSocket connection attempt for device: {self.device_id}")

        # Get API key from query string
        query_string = parse_qs(self.scope['query_string'].decode())
        api_key = query_string.get('api_key', [None])[0]

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

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        logger.info(f"Added to group: {self.group_name}")

        # Accept the connection
        await self.accept()
        logger.info(f"WebSocket connection accepted for device: {self.device_id}")

        # Send initial device settings
        await self.send_device_settings()

        # Start heartbeat
        self.heartbeat_task = asyncio.create_task(self.send_heartbeat())

    async def send_heartbeat(self):
        """Send periodic heartbeats to verify connection is still alive"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                print(f"⏱️ SENDING HEARTBEAT to device: {self.device_id}")  # Visible console indicator
                await self.send(text_data=json.dumps({"type": "heartbeat"}))
                logger.debug(f"Heartbeat sent to device: {self.device_id}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat: {str(e)}")
                break

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnecting for device: {self.device_id}, code: {close_code}")

        # Cancel heartbeat task
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        # Remove from device group
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"Removed from group: {self.group_name}")

    async def receive(self, text_data):
        logger.info(f"Received WebSocket message from device: {self.device_id}")
        # Handle incoming messages
        try:
            data = json.loads(text_data)

            # Handle heartbeat responses
            if data.get('type') == 'heartbeat_response':
                logger.debug(f"Heartbeat response received from device: {self.device_id}")
                await self.update_last_seen()
                return

            # Handle settings requests
            if data.get('action') == 'get_settings':
                logger.info(f"Get settings request from device: {self.device_id}")
                await self.send_device_settings()

            # Always update last_seen on any message
            await self.update_last_seen()

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received from device: {self.device_id}")
            pass

    @sync_to_async
    def update_last_seen(self):
        """Update the device's last_seen timestamp"""
        try:
            self.device.last_seen = now()
            self.device.save(update_fields=['last_seen'])
            logger.debug(f"Updated last_seen for device: {self.device_id}")
            return True
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
            device.save(update_fields=['last_seen'])

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
            self.device.save(update_fields=['last_seen'])

            # Check if there's an active session
            has_active_session = Session.objects.filter(
                device=self.device,
                end_time__isnull=True
            ).exists()

            settings = {
                "sensitivity": self.device.sensitivity,
                "vibration_intensity": self.device.vibration_intensity,
                "has_active_session": has_active_session,
            }

            logger.info(f"Device settings retrieved: {settings}")
            return settings
        except Exception as e:
            logger.error(f"Error getting device settings: {str(e)}")
            return {
                "sensitivity": 0,
                "vibration_intensity": 0,
                "has_active_session": False,
                "error": str(e)
            }

    async def send_device_settings(self):
        """Send current device settings to the client"""
        settings = await self.get_device_settings()
        logger.info(f"Sending settings to device: {self.device_id}, settings: {settings}")
        await self.send(text_data=json.dumps(settings))

    async def device_settings_update(self, event):
        """Handle device settings update event from channel layer"""
        device_id = event.get('device_id')
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
            await self.send(text_data=json.dumps(settings))
            logger.info(f"Settings update message sent successfully at {now()}")
        else:
            logger.warning(f"Ignoring settings update - device ID mismatch: expected {self.device_id}, got {device_id}")

    async def session_status_event(self, event):
        """Handle session status events (start/stop)"""
        device_id = event.get('device_id')
        action = event.get('action')
        has_active_session = event.get('has_active_session', False)
        
        # Only process if it's for this device
        if device_id == self.device_id:
            logger.info(f"Received session {action} event for device: {self.device_id}")
            
            # Send the session event to the client
            await self.send(text_data=json.dumps({
                "type": "session_status",
                "action": action,
                "has_active_session": has_active_session
            }))
            
            # Also refresh and send updated device settings
            refresh_success = await self.refresh_device()
            await self.send_device_settings()
        else:
            logger.warning(f"Ignoring session event - device ID mismatch: expected {self.device_id}, got {device_id}")