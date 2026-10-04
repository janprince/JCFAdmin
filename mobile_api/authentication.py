"""
DRF authentication + permissions for mobile members.

Members are `members.Contact` records, not Django users, so we use a custom
token scheme instead of session/JWT-for-User auth. A valid access token sets
`request.member` (the Contact) and `request.auth` (the MobileToken).
"""
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
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
            raise exceptions.AuthenticationFailed(_('Invalid authorization header.'))

        key = header[1].decode()
        try:
            token = MobileToken.objects.select_related('contact').get(access_token=key)
        except MobileToken.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        if not token.access_valid:
            raise exceptions.AuthenticationFailed(_('Token expired or revoked.'))

        token.last_used_at = timezone.now()
        token.save(update_fields=['last_used_at'])

        # Expose the Contact as request.member; DRF also sets request.user/auth.
        request.member = token.contact
        return (token.contact, token)

    def authenticate_header(self, request):
        # Ensures failed/missing auth yields 401 (not 403).
        return self.keyword


class OptionalMobileTokenAuthentication(MobileTokenAuthentication):
    """Validates a token when one is sent, and treats a bad one as absent.

    For endpoints that must answer a launching app whatever state its
    stored credentials are in. A stale token has to leave the caller a
    guest, not lock them out of the call that would have told them to sign
    in again.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except exceptions.AuthenticationFailed:
            return None


class IsSignedIn(permissions.BasePermission):
    """Allow only requests carrying a valid mobile token.

    Named for what it checks. It was called IsMember, which read as a tier
    test and never was one — it only ever asked whether a token was
    present, and several views relied on exactly that.
    """

    message = _('Sign-in required.')

    def has_permission(self, request, view):
        return isinstance(request.auth, MobileToken)


class IsStudent(IsSignedIn):
    """Restrict to an approved, active Contact.

    The app has two tiers: guests, who are not signed in, and students,
    who are. `is_member` is still a JCFAdmin CRM flag and still marks an
    approved contact, so it grants the same access here as `is_student` —
    nobody who could use the app yesterday is locked out today.
    """

    message = _('This content is for signed-in students.')

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        contact = request.auth.contact
        return bool(contact.is_active
                    and (contact.is_student or contact.is_member))
