"""
Custom DRF exception handler.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        logger.exception('Unhandled exception in view %s', context.get('view'))
        return Response(
            {'detail': 'An unexpected error occurred. Please try again later.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Normalize error format
    if isinstance(response.data, dict):
        if 'detail' not in response.data:
            response.data = {'errors': response.data}
    return response
