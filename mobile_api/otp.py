"""
Helpers to resolve a Contact from a phone/email identifier and deliver the
one-time login code.

Delivery channel follows the identifier ("Continue with Phone" -> SMS via
Arkesel, "Continue with Email" -> email), falling back to email when SMS
isn't possible (no Arkesel key, no phone, send failure). Delivery failures
are logged (never fatal).
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q

from members.models import Contact
from website.notifications import send_sms_arkesel

from .models import LoginCode

logger = logging.getLogger(__name__)


def looks_like_email(identifier: str) -> bool:
    return '@' in identifier


def normalize(identifier: str) -> str:
    return (identifier or '').strip()


def find_any_contact(identifier: str):
    """Find a Contact by email or phone WITHOUT the active/approved filter —
    used to distinguish 'not found' from 'found but awaiting approval'."""
    identifier = normalize(identifier)
    if not identifier:
        return None
    if looks_like_email(identifier):
        qs = Contact.objects.filter(email__iexact=identifier)
    else:
        digits = identifier.replace(' ', '')
        qs = Contact.objects.filter(
            Q(phone__icontains=digits) | Q(telephone__icontains=digits)
        )
    return qs.first()


def is_approved(contact) -> bool:
    """Approved for the app: active AND flagged member or student."""
    return bool(contact and contact.is_active
                and (contact.is_member or contact.is_student))


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


def _email_code(contact, email, code):
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


def send_code(contact, prefer_sms=False):
    """Issue a login code and deliver it.

    prefer_sms=True (the app's "Continue with Phone") sends by SMS to the
    contact's phone; otherwise — or when SMS isn't possible — the code is
    emailed. Returns (LoginCode, plaintext_code), or (None, None) when the
    contact has neither a usable phone nor an email.
    """
    phone = str(contact.phone) if contact.phone else ''
    email = (contact.email or '').strip()

    use_sms = prefer_sms and bool(phone)
    if not use_sms and not email:
        use_sms = bool(phone)  # email-less contact: SMS is the only route
    if not use_sms and not email:
        logger.warning('Contact %s has no phone or email; cannot send OTP.', contact.pk)
        return None, None

    channel = LoginCode.Channel.SMS if use_sms else LoginCode.Channel.EMAIL
    login_code, code = LoginCode.issue(contact, channel, phone if use_sms else email)

    if use_sms:
        sent = send_sms_arkesel(
            phone, f'Your JCF verification code is {code}. It expires in 10 minutes.')
        if not sent and email:
            # Arkesel unavailable or send failed — same code goes out by email.
            _email_code(contact, email, code)
    else:
        _email_code(contact, email, code)

    if settings.DEBUG:
        logger.info('DEBUG login code for %s: %s', contact.pk, code)

    return login_code, code

RESEND_COOLDOWN_SECONDS = 30


def mask_phone(phone: str) -> str:
    """+233201234824 -> '+233 ••• ••• 824' (country prefix + last 3)."""
    phone = (phone or '').strip()
    if len(phone) < 7:
        return '•••'
    return f'{phone[:4]} ••• ••• {phone[-3:]}'


def mask_email(email: str) -> str:
    """ama@example.com -> 'a•••@example.com'."""
    email = (email or '').strip()
    if '@' not in email:
        return '•••'
    local, domain = email.split('@', 1)
    return f'{local[:1]}•••@{domain}'

