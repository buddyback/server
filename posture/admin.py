from django.contrib import admin

from posture.models import PostureReading, PostureComponent

admin.site.register(PostureReading)
admin.site.register(PostureComponent)