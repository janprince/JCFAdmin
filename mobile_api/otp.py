"""
Helpers to resolve a Contact from a phone/email identifier and deliver the
one-time login code BY EMAIL.

A member may identify themselves by phone or email, but the verification code is
always emailed to the address on their Contact record. Delivery failures are
logged (never fatal). Requires EMAIL_HOST_USER / EMAIL_HOST_PASSWORD in the
environment to actually send (see .env.example).
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q

from members.models import Contact
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


def send_code(contact):
    """Issue a login code and email it to the contact's address.

    Returns (LoginCode, plaintext_code), or (None, None) if the contact has no
    email on file (so they can't receive a code).
    """
    email = (contact.email or '').strip()
    if not email:
        logger.warning('Contact %s has no email on file; cannot send OTP.', contact.pk)
        return None, None

    login_code, code = LoginCode.issue(contact, LoginCode.Channel.EMAIL, email)
    subject = 'Your JCF verification code'
    message = (
        f'Hello {contact.full_name},\n\n'
        f'Your JCF verification code is {code}. It expires in 10 minutes.\n\n'
        f'If you did not request this, you can ignore this email.'
    )
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception:  # pragma: no cover - delivery must never 500 the request
        logger.exception('Failed to email login code to %s', email)

    if settings.DEBUG:
        logger.info('DEBUG login code for %s: %s', email, code)

    return login_code, code
