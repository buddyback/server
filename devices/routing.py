from django.urls import re_path

from devices.consumers import DeviceSettingsConsumer

websocket_urlpatterns = [
    re_path(r'ws/device-settings/(?P<device_id>[0-9a-f-]+)/$', DeviceSettingsConsumer.as_asgi()),
]
