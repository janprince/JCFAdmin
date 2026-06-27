"""Mobile API auth endpoints (namespace: /api/mobile/v1/auth/)."""
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import IsMember, MobileTokenAuthentication
from .models import MAX_CODE_ATTEMPTS, LoginCode, MobileToken
from .otp import find_contact, send_code, normalize
from .serializers import MemberSerializer

# Generic response so we never reveal which phones/emails exist.
_GENERIC = {'detail': 'If the account exists, a verification code has been sent.'}


class RequestCodeView(APIView):
    """POST {identifier} -> sends an OTP if a matching active Contact exists."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        identifier = normalize(request.data.get('identifier', ''))
        if not identifier:
            return Response(
                {'identifier': 'This field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contact = find_contact(identifier)
        payload = dict(_GENERIC)
        if contact:
            _, code = send_code(contact, identifier)
            if settings.DEBUG:
                payload['dev_code'] = code  # convenience for local dev only
        return Response(payload)


class VerifyCodeView(APIView):
    """POST {identifier, code} -> issues access + refresh tokens on success."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        identifier = normalize(request.data.get('identifier', ''))
        code = normalize(request.data.get('code', ''))
        if not identifier or not code:
            return Response(
                {'detail': 'identifier and code are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contact = find_contact(identifier)
        invalid = Response(
            {'detail': 'Invalid or expired code.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
        if not contact:
            return invalid

        login_code = (
            LoginCode.objects.filter(contact=contact, consumed_at__isnull=True)
            .order_by('-created_at')
            .first()
        )
        if not login_code or login_code.is_expired:
            return invalid
        if login_code.attempts >= MAX_CODE_ATTEMPTS:
            return Response(
                {'detail': 'Too many attempts. Request a new code.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not login_code.matches(code):
            login_code.attempts += 1
            login_code.save(update_fields=['attempts'])
            return invalid

        login_code.consumed_at = timezone.now()
        login_code.save(update_fields=['consumed_at'])

        token = MobileToken.issue(contact)
        return Response(
            {
                'access': token.access_token,
                'refresh': token.refresh_token,
                'access_expires_at': token.access_expires_at,
                'member': MemberSerializer(contact).data,
            },
            status=status.HTTP_200_OK,
        )


class RefreshView(APIView):
    """POST {refresh} -> rotates a new access token."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh = normalize(request.data.get('refresh', ''))
        if not refresh:
            return Response(
                {'refresh': 'This field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token = MobileToken.objects.filter(refresh_token=refresh).first()
        if not token or not token.refresh_valid:
            return Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token.rotate_access()
        return Response(
            {'access': token.access_token, 'access_expires_at': token.access_expires_at}
        )


class MeView(APIView):
    """GET -> the authenticated member's profile. DELETE -> logout (revoke token)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def get(self, request):
        return Response(MemberSerializer(request.auth.contact).data)

    def delete(self, request):
        token = request.auth
        token.revoked = True
        token.save(update_fields=['revoked'])
        return Response(status=status.HTTP_204_NO_CONTENT)
