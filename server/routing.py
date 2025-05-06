from django.urls import path

from devices.consumers import DeviceSettingsConsumer

websocket_urlpatterns = [
    path("ws/device-settings/<str:device_id>/", DeviceSettingsConsumer.as_asgi()),
]