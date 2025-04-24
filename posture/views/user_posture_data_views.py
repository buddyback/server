from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from devices.models import Device
from posture.models import PostureReading
from posture.serializers.device_posture_data_serializers import PostureReadingSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["posture-data-user"],
        summary="List posture data for a device owned by the authenticated user",
        description="Returns posture data from a specific device if the authenticated user is its owner. "
                    "Supports optional filtering by a specific date or a date range.",
        parameters=[
            OpenApiParameter(
                name='date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filter data by a specific date (e.g. 2025-04-24). Cannot be used with start_date or end_date.'
            ),
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Start date for date range filtering (e.g. 2025-04-01). Used with or without end_date.'
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='End date for date range filtering (e.g. 2025-04-24). Used with or without start_date.'
            ),
        ],
    )
)
class UserPostureDataByDeviceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for accessing posture data for a specific device owned by the authenticated user."""

    serializer_class = PostureReadingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_device(self):
        """Get and validate the device belongs to the requesting user."""
        device_id = self.kwargs.get('device_id')
        device = get_object_or_404(Device, id=device_id)

        if device.user != self.request.user:
            raise PermissionDenied(detail="You do not have access to this device's data.")

        return device

    def validate_date_params(self):
        """Validate date parameters and check for conflicting filters."""
        date_str = self.request.query_params.get('date')
        start_date_str = self.request.query_params.get('start_date')
        end_date_str = self.request.query_params.get('end_date')

        # Check for conflicting date parameters
        if date_str and (start_date_str or end_date_str):
            raise ValidationError({
                'error': "'date' parameter cannot be used with 'start_date' or 'end_date'"
            })

        # Process single date
        date = None
        if date_str:
            date = parse_date(date_str)
            if not date:
                raise ValidationError({'date': f"Invalid date format: {date_str}. Use YYYY-MM-DD."})

        # Process date range
        start_date = None
        end_date = None
        if start_date_str or end_date_str:
            if start_date_str:
                start_date = parse_date(start_date_str)
                if not start_date:
                    raise ValidationError({'start_date': f"Invalid date format: {start_date_str}. Use YYYY-MM-DD."})

            if end_date_str:
                end_date = parse_date(end_date_str)
                if not end_date:
                    raise ValidationError({'end_date': f"Invalid date format: {end_date_str}. Use YYYY-MM-DD."})

            # Validate date range if both dates provided
            if start_date and end_date and start_date > end_date:
                raise ValidationError({'error': "'start_date' cannot be after 'end_date'"})

        return {
            'date': date,
            'start_date': start_date,
            'end_date': end_date
        }

    def apply_date_filters(self, queryset, dates):
        """Apply date filters to the queryset."""
        if dates['date']:
            return queryset.filter(timestamp__date=dates['date'])

        elif dates['start_date'] or dates['end_date']:
            if dates['start_date'] and dates['end_date']:
                return queryset.filter(timestamp__date__range=(dates['start_date'], dates['end_date']))
            elif dates['start_date']:
                return queryset.filter(timestamp__date__gte=dates['start_date'])
            else:  # Only end_date
                return queryset.filter(timestamp__date__lte=dates['end_date'])

        return queryset

    def list(self, request, *args, **kwargs):
        """Override list method to handle validation errors properly."""
        try:
            # First check device ownership
            device = self.get_device()

            # Validate and parse date parameters
            dates = self.validate_date_params()

            # Base queryset - using prefetch_related to optimize component queries
            queryset = PostureReading.objects.filter(device=device).prefetch_related(
                'components'  # Prefetch related components for performance
            )

            # Apply date filters
            queryset = self.apply_date_filters(queryset, dates)

            # Order by timestamp for consistent results
            queryset = queryset.order_by('-timestamp')

            # Set the queryset for pagination and serialization
            self.queryset = queryset

            # Continue with the standard list processing
            return super().list(request, *args, **kwargs)

        except ValidationError as e:
            return Response(
                e.detail,
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_queryset(self):
        """
        Return an empty queryset initially.
        The actual queryset is set in the list method.
        """
        if hasattr(self, 'queryset'):
            return self.queryset
        return PostureReading.objects.none()