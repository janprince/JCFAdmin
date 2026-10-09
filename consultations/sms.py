"""Text a consultation's date to the person booked, through Arkesel.

Only Ghanaian numbers are texted — Arkesel delivers within Ghana, and the
office reaches anyone abroad another way. The text is plain GSM characters
(no curly quotes or long dashes) so it stays one SMS where it can, and it
never blocks a booking: the consultation is saved first, and a failed send
is reported to staff as a warning.
"""
from django.utils import timezone
from django.utils.dateformat import format as dateformat

from dashboard.templatetags.jcf_ui import person_name
from website.notifications import SmsNotSent, deliver_sms, is_ghana_number

MODE_WORDS = {'Onsite': 'in person', 'Remote': 'by phone or video'}


def booking_message(consultation, rescheduled=False):
    first_name = person_name(consultation.contact.full_name).split(' ')[0] or 'there'
    when = dateformat(consultation.scheduled_date, 'l, j F Y')
    how = MODE_WORDS.get(consultation.mode, '')
    verb = 'has been moved to' if rescheduled else 'is on'
    return (f'Dear {first_name}, your consultation with Dr. Baffour Jan {verb} {when}'
            f'{f" ({how})" if how else ""}. See you then. - Jan Cosmic Foundation')


def text_booking(consultation, rescheduled=False):
    """Send the SMS. Returns (sent, note for staff)."""
    phone = consultation.contact.phone
    if consultation.scheduled_date < timezone.localdate():
        return False, 'No SMS sent: the date has already passed.'
    if not phone or not is_ghana_number(phone):
        return False, f'No SMS sent: {phone or "there is no phone number"} is not a Ghana number.'
    try:
        deliver_sms(phone, booking_message(consultation, rescheduled))
    except SmsNotSent as exc:
        return False, f'The SMS was not sent. {exc}'
    consultation.sms_sent_at = timezone.now()
    consultation.save(update_fields=['sms_sent_at'])
    return True, f'SMS sent to {phone.as_international}.'
