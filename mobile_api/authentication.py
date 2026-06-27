"""
DRF authentication + permissions for mobile members.

Members are `members.Contact` records, not Django users, so we use a custom
token scheme instead of session/JWT-for-User auth. A valid access token sets
`request.member` (the Contact) and `request.auth` (the MobileToken).
"""
from django.utils import timezone
from rest_framework import authentication, exceptions, permissions

from .models import MobileToken


class MobileTokenAuthentication(authentication.BaseAuthentication):
    """Authorize via `Authorization: Bearer <access_token>`."""

    keyword = 'Bearer'

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None
        if len(header) != 2:
            raise exceptions.AuthenticationFailed('Invalid authorization header.')

        key = header[1].decode()
        try:
            token = MobileToken.objects.select_related('contact').get(access_token=key)
        except MobileToken.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token.')

        if not token.access_valid:
            raise exceptions.AuthenticationFailed('Token expired or revoked.')

        token.last_used_at = timezone.now()
        token.save(update_fields=['last_used_at'])

        # Expose the Contact as request.member; DRF also sets request.user/auth.
        request.member = token.contact
        return (token.contact, token)

    def authenticate_header(self, request):
        # Ensures failed/missing auth yields 401 (not 403).
        return self.keyword


class IsMember(permissions.BasePermission):
    """Allow only requests carrying a valid mobile token."""

    message = 'Member authentication required.'

    def has_permission(self, request, view):
        return isinstance(request.auth, MobileToken)


class IsStudentOrMember(IsMember):
    """Restrict to Contacts flagged as an active member or student."""

    message = 'This content is for registered members or students.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        contact = request.auth.contact
        return bool(contact.is_active and (contact.is_member or contact.is_student))
