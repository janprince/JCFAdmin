"""Turn a public booking form into a booking request and a contact.

The form is public, so nothing it sends may change a record the office
already keeps. A submission is matched to an existing contact only on the
same name and phone (families often share one phone), and a match is linked,
never edited. Anyone else becomes a new contact with the details they gave.
"""
from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework.throttling import SimpleRateThrottle

from members.models import Contact
from .models import ConsultationRequest

REQUEST_FIELDS = ['full_name', 'phone', 'email', 'date_of_birth', 'day_of_birth', 'profession', 'hometown',
                  'religion', 'residence', 'heard_from', 'heard_detail', 'preferred_mode', 'note']


class BookingThrottle(SimpleRateThrottle):
    """Per-address limit on submissions. Approximate: it uses Django's cache."""
    scope = 'consultation_request'

    def get_rate(self):
        return getattr(settings, 'CONSULTATION_REQUEST_RATE', '10/hour')

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


def tidy(value):
    return ' '.join(str(value or '').split())


def _contact_for(data):
    name, phone = data['full_name'], data['phone']
    existing = Contact.objects.filter(phone=phone, full_name__iexact=name).order_by('pk').first()
    if existing:
        return existing, False
    details = dict(
        email=data.get('email', ''), date_of_birth=data.get('date_of_birth'),
        day_of_birth='' if data.get('date_of_birth') else data.get('day_of_birth', ''),
        profession=data['profession'], hometown=data['hometown'], religion=data['religion'] or 'N/A',
        residence=data['residence'], referral=ConsultationRequest(heard_from=data['heard_from'], heard_detail=data.get('heard_detail', '')).referral,
    )
    try:
        with transaction.atomic():
            return Contact.objects.create(full_name=name, phone=phone, **details), True
    except IntegrityError:
        # The same person submitted twice at once; the other request won.
        return Contact.objects.get(full_name=name, phone=phone), False


@transaction.atomic
def submit_request(data):
    """Save one submission. A repeat while the first is still open is ignored."""
    data = {key: data.get(key) for key in REQUEST_FIELDS}
    for key in ('full_name', 'profession', 'hometown', 'religion', 'residence', 'heard_detail'):
        data[key] = tidy(data[key])
    data['email'] = (data['email'] or '').strip().lower()
    for key in ('day_of_birth', 'preferred_mode', 'note'):
        data[key] = data[key] or ''
    if data['date_of_birth']:
        data['day_of_birth'] = ''
    pending = ConsultationRequest.objects.filter(phone=data['phone'], full_name__iexact=data['full_name'],
                                                 status=ConsultationRequest.Status.NEW).first()
    if pending:
        return pending
    contact, created = _contact_for(data)
    return ConsultationRequest.objects.create(contact=contact, created_contact=created, **data)
