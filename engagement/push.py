"""
Push delivery (FCM). Best-effort and gated: until a Firebase service account is
provisioned (FCM_ENABLED), sends are logged and skipped — wiring real FCM later
is a localized change to send_push().
"""
import logging

from django.conf import settings
from django.db.models import Q

from members.models import Contact
from .models import Announcement, DeviceToken, Notification

logger = logging.getLogger(__name__)


def fcm_configured() -> bool:
    return bool(getattr(settings, 'FCM_ENABLED', False))


def send_push(tokens, title, body, data=None) -> int:
    """Send a push to the given FCM tokens. Returns the number targeted."""
    tokens = [t for t in tokens if t]
    if not tokens:
        return 0
    if not fcm_configured():
        logger.info('FCM not configured; skipping push "%s" to %d device(s).', title, len(tokens))
        return 0
    # TODO: integrate firebase-admin once a service account is available.
    logger.info('Push "%s" -> %d device(s).', title, len(tokens))
    return len(tokens)


def audience_contacts(audience):
    qs = Contact.objects.filter(is_active=True)
    if audience == Announcement.Audience.MEMBERS:
        return qs.filter(Q(is_member=True) | Q(is_student=True))
    if audience == Announcement.Audience.STUDENTS:
        return qs.filter(is_student=True)
    return qs  # public -> everyone


def broadcast_announcement(announcement) -> int:
    """Push an announcement to its audience; create in-app notifications for
    targeted members (skipped for public to avoid fanning out to everyone)."""
    audience = announcement.audience
    if audience == Announcement.Audience.PUBLIC:
        tokens = DeviceToken.objects.filter(is_active=True).values_list('token', flat=True)
    else:
        contacts = audience_contacts(audience)
        tokens = DeviceToken.objects.filter(
            is_active=True, contact__in=contacts
        ).values_list('token', flat=True)
        Notification.objects.bulk_create([
            Notification(
                contact=c, title=announcement.title, body=announcement.body,
                data={'type': 'announcement', 'id': announcement.id},
            )
            for c in contacts
        ])
    return send_push(
        list(tokens), announcement.title, announcement.body,
        data={'type': 'announcement', 'id': announcement.id},
    )
