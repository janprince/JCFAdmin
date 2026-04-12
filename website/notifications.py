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
        return parsed.country_code == 233
    except phonenumbers.NumberParseException:
        return False


def send_sms_arkesel(to, message):
    """Send SMS via Arkesel API."""
    api_key = getattr(settings, 'ARKESEL_API_KEY', '')
    if not api_key:
        logger.warning('ARKESEL_API_KEY not configured; skipping SMS to %s', to)
        return False

    payload = {
        'sender': getattr(settings, 'ARKESEL_SENDER_ID', 'JCF'),
        'message': message,
        'recipients': [str(to)],
    }
    try:
        resp = requests.post(
            'https://sms.arkesel.com/api/v2/sms/send',
            headers={'api-key': api_key},
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        logger.info('SMS sent to %s via Arkesel', to)
        return True
    except requests.RequestException as e:
        logger.error('Arkesel SMS failed for %s: %s', to, e)
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
