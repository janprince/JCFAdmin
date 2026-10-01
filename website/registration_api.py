from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .serializers import FoundationRegistrationSerializer


class FoundationRegistrationThrottle(SimpleRateThrottle):
    scope = 'foundation_registration'

    def get_rate(self):
        return getattr(settings, 'FOUNDATION_REGISTRATION_RATE', '20/hour')

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class FoundationRegistrationAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [FoundationRegistrationThrottle]

    def post(self, request):
        serializer = FoundationRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Same response on retries; no email lookup, record IDs or private data exposed.
        return Response({'status': 'registered'}, status=201)
