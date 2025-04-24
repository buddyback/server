from django.contrib import admin

from posture.models import PostureComponent, PostureReading

admin.site.register(PostureReading)
admin.site.register(PostureComponent)
