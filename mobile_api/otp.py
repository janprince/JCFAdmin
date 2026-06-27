"""
Helpers to resolve a Contact from a phone/email identifier and deliver the
one-time login code. Delivery reuses the existing Arkesel SMS + email helpers
and is best-effort (failures are logged, not fatal, so dev works without keys).
"""
import logging

from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q

from members.models import Contact
from website.notifications import send_sms_arkesel
from .models import LoginCode

logger = logging.getLogger(__name__)


def looks_like_email(identifier: str) -> bool:
    return '@' in identifier


def normalize(identifier: str) -> str:
    return (identifier or '').strip()


def find_contact(identifier: str):
    """Find a single active Contact by email or phone. Returns None if absent/ambiguous."""
    identifier = normalize(identifier)
    if not identifier:
        return None

    if looks_like_email(identifier):
        qs = Contact.objects.filter(is_active=True, email__iexact=identifier)
    else:
        # Match against either phone field. PhoneNumberField stores E.164.
        digits = identifier.replace(' ', '')
        qs = Contact.objects.filter(is_active=True).filter(
            Q(phone__icontains=digits) | Q(telephone__icontains=digits)
        )
    return qs.first()


def send_code(contact, identifier: str):
    """Issue and deliver a login code. Returns (LoginCode, plaintext_code)."""
    identifier = normalize(identifier)
    is_email = looks_like_email(identifier)
    channel = LoginCode.Channel.EMAIL if is_email else LoginCode.Channel.SMS
    login_code, code = LoginCode.issue(contact, channel, identifier)

    message = f'Your JCF verification code is {code}. It expires in 10 minutes.'
    try:
        if is_email:
            send_mail(
                'Your JCF login code',
                message,
                settings.DEFAULT_FROM_EMAIL,
                [identifier],
                fail_silently=True,
            )
        else:
            send_sms_arkesel(identifier, message)
    except Exception:  # pragma: no cover - delivery must never 500 the request
        logger.exception('Failed to deliver login code to %s', identifier)

    if settings.DEBUG:
        logger.info('DEBUG login code for %s: %s', identifier, code)

    return login_code, code
