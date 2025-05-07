from django.urls import re_path

from devices.consumers import DeviceConsumer

websocket_urlpatterns = [
    re_path(r"ws/device-connection/(?P<device_id>[0-9a-f-]+)/$", DeviceConsumer.as_asgi()),
]
