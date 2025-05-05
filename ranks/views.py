from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions

from .models import UserRank
from .serializers import UserRankSerializer


@extend_schema_view(
    get=extend_schema(
        description="Retrieve all ranks for the authenticated user",
        summary="Get user ranks",
        tags=["ranks"],
        responses={
            200: UserRankSerializer(many=True),
            401: {"description": "Not authenticated"},
        },
    )
)
class UserRankListView(generics.ListAPIView):
    """Retrieve all ranks for the authenticated user"""

    serializer_class = UserRankSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserRank.objects.filter(user=self.request.user).select_related('tier')
