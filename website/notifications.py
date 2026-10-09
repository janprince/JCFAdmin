import logging

import phonenumbers
import requests
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def is_ghana_number(phone):
    """Check if a phone number is a Ghana number (+233)."""
    try:
        parsed = phonenumbers.parse(str(phone), 'GH')
        return parsed.country_code == 233 and phonenumbers.is_valid_number(parsed)
    except phonenumbers.NumberParseException:
        return False


class SmsNotSent(Exception):
    """Why an SMS did not go out, in words staff can act on."""


def arkesel_recipient(phone):
    """Arkesel wants international digits with no plus sign: 233241234567."""
    parsed = phonenumbers.parse(str(phone), 'GH')
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164).lstrip('+')


def deliver_sms(to, message):
    """Send one SMS through Arkesel, or raise SmsNotSent saying why.

    Arkesel can answer 200 and still refuse a message, so the JSON `status`
    is checked as well as the HTTP code.
    """
    api_key = getattr(settings, 'ARKESEL_API_KEY', '')
    if not api_key:
        raise SmsNotSent('SMS is not set up on this server (ARKESEL_API_KEY is empty).')
    payload = {
        'sender': getattr(settings, 'ARKESEL_SENDER_ID', 'JCF'),
        'message': message,
        'recipients': [arkesel_recipient(to)],
    }
    try:
        resp = requests.post('https://sms.arkesel.com/api/v2/sms/send', headers={'api-key': api_key},
                             json=payload, timeout=10)
    except requests.RequestException as exc:
        logger.error('Arkesel SMS to %s failed: %s', to, exc)
        raise SmsNotSent('Could not reach the SMS service. Try again later.') from exc
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if not resp.ok or (body.get('status') and body.get('status') != 'success'):
        reason = body.get('message') or f'the SMS service answered {resp.status_code}'
        logger.error('Arkesel refused SMS to %s: %s %s', to, resp.status_code, reason)
        raise SmsNotSent(f'The SMS service refused it: {reason}.')
    logger.info('SMS sent to %s via Arkesel', to)


def send_sms_arkesel(to, message):
    """Send SMS via Arkesel. Returns True when sent; failures are logged, never raised."""
    try:
        deliver_sms(to, message)
        return True
    except SmsNotSent as exc:
        logger.warning('SMS to %s not sent: %s', to, exc)
        return False


def send_approval_email(to_email, name, centre_name, whatsapp_link, telegram_link):
    """Send approval notification via email (for international numbers)."""
    subject = f'Welcome to {centre_name} - Jan Cosmic Foundation'
    body_lines = [
        f'Dear {name},',
        '',
        f'Your request to join {centre_name} has been approved!',
        '',
    ]
    if whatsapp_link:
        body_lines.append(f'Join our WhatsApp group: {whatsapp_link}')
    if telegram_link:
        body_lines.append(f'Join our Telegram group: {telegram_link}')
    if not whatsapp_link and not telegram_link:
        body_lines.append('Our centre leader will reach out to you shortly.')
    body_lines += ['', 'God bless,', 'Jan Cosmic Foundation']

    message = '\n'.join(body_lines)

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
        logger.info('Approval email sent to %s', to_email)
        return True
    except Exception as e:
        logger.error('Email failed for %s: %s', to_email, e)
        return False


def send_approval_notification(join_request, contact):
    """
    Send notification after join request approval.
    Ghana numbers get SMS; international numbers get email.
    """
    centre = join_request.centre
    whatsapp_link = centre.whatsapp_link
    telegram_link = centre.telegram_link

    if is_ghana_number(contact.phone):
        msg = f'Dear {join_request.name}, welcome to {centre.name}!'
        if whatsapp_link:
            msg += f' Join our WhatsApp group: {whatsapp_link}'
        send_sms_arkesel(contact.phone, msg)
    else:
        if contact.email:
            send_approval_email(
                to_email=contact.email,
                name=join_request.name,
                centre_name=centre.name,
                whatsapp_link=whatsapp_link,
                telegram_link=telegram_link,
            )
        else:
            logger.warning(
                'Cannot notify %s: international number but no email on file.',
                join_request.name,
            )
