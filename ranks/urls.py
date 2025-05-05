from django.urls import path
from .views import UserRankListView

app_name = 'ranks'

urlpatterns = [
    path('ranks', UserRankListView.as_view(), name='user-ranks'),
]