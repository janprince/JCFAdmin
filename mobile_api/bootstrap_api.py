"""App bootstrap (owner spec, splash screen).

One call the app makes before it shows anything: is the service up, is this
build still supported, is the session real, and where should the user land.

Two rules this module is built around:

* **A token is not a session.** The client cannot treat the presence of a
  stored token as proof of anything, so this endpoint reports
  `authenticated` from the token it actually validated, and the user type
  from the contact behind it.
* **`initial_route` is a hint, not a command.** It is a convenience so the
  app does not have to re-derive routing, but the client validates it
  against its own allowlist. The server never gets to name an arbitrary
  route or URL the client will execute.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import OptionalMobileTokenAuthentication

# The oldest build this API still speaks to, and the newest published one.
# Kept here rather than in a model: they change with a deploy, not with an
# editor's action, and a bad value must not be one dashboard click away.
MINIMUM_SUPPORTED_VERSION = '1.0.0'
LATEST_VERSION = '1.0.0'

STORE_URLS = {
    'ios': 'https://apps.apple.com/app/id0000000000',
    'android':
        'https://play.google.com/store/apps/details?id=com.jcf.mobile',
}


def parse_version(raw):
    """'1.2.3' -> (1, 2, 3). Anything unparseable sorts lowest.

    An unreadable version must never be treated as new enough, or a
    malformed header becomes a way past the minimum-version gate.
    """
    # Drop a build suffix first: '1.4.2+87' is version 1.4.2, and simply
    # stripping non-digits would read its patch number as 287.
    head = str(raw or '').split('+')[0].split('-')[0]
    parts = []
    for chunk in head.split('.')[:3]:
        digits = ''.join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def maintenance_state():
    """Maintenance is a settings flag so it can be turned on during an
    incident without a database that may itself be the incident."""
    return {
        'enabled': bool(getattr(settings, 'MOBILE_MAINTENANCE', False)),
        'title': getattr(settings, 'MOBILE_MAINTENANCE_TITLE', '') or None,
        'message':
            getattr(settings, 'MOBILE_MAINTENANCE_MESSAGE', '') or None,
        'allow_offline':
            bool(getattr(settings, 'MOBILE_MAINTENANCE_ALLOW_OFFLINE', True)),
    }


class BootstrapView(APIView):
    """GET /bootstrap/ — what the app needs before it renders anything.

    Public: a guest launching the app needs the version and maintenance
    answer just as much as a member does. A token, when sent, is validated
    and reported on; when absent *or invalid* the caller is simply a
    guest, because an app launching with a stale token must still be able
    to learn that it needs to sign in again.
    """

    authentication_classes = [OptionalMobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        token = getattr(request, 'auth', None)
        contact = token.contact if token is not None else None
        now = timezone.now()

        client_version = request.headers.get('X-App-Version', '')
        update_required = (
            parse_version(client_version)
            < parse_version(MINIMUM_SUPPORTED_VERSION)
            if client_version else False
        )
        platform = (request.headers.get('X-Platform', '') or '').lower()

        if contact is None:
            user_type = 'guest'
        elif contact.is_student:
            user_type = 'student'
        elif contact.is_member:
            user_type = 'member'
        else:
            user_type = 'contact'

        return Response({
            'server_time': now.isoformat(),
            'maintenance': maintenance_state(),
            'version': {
                'minimum_supported': MINIMUM_SUPPORTED_VERSION,
                'latest': LATEST_VERSION,
                'update_required': update_required,
                'store_url': STORE_URLS.get(platform),
            },
            'session': {
                # Reported from the token this request actually validated,
                # never from the client merely claiming to hold one.
                'authenticated': contact is not None,
                'user_type': user_type,
            },
            # A hint the client checks against its own allowlist.
            'initial_route': '/home',
        })
