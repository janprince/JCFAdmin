"""Registration confirmation: atomic room allocation + QR generation."""
import io

import qrcode
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import AccommodationTier, Registration


class RoomSoldOut(Exception):
    """Raised when the selected accommodation tier has no rooms left."""


def generate_qr(registration):
    """Render the registration reference as a QR PNG into registration.qr (R2)."""
    img = qrcode.make(registration.reference)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    registration.qr.save(
        f'{registration.reference}.png', ContentFile(buf.getvalue()), save=False
    )


@transaction.atomic
def confirm_registration(registration, paystack_reference=''):
    """Confirm a registration: allocate a room atomically, set status, make QR.

    Idempotent — confirming an already-confirmed registration is a no-op.
    Raises RoomSoldOut if the chosen tier is full.
    """
    if registration.status == Registration.Status.CONFIRMED:
        return registration

    tier = registration.accommodation_tier
    if tier is not None:
        # Atomic: only increment if a room is available (0 total = unlimited).
        allocated = (
            AccommodationTier.objects.filter(pk=tier.pk)
            .filter(Q(total_rooms=0) | Q(rooms_confirmed__lt=F('total_rooms')))
            .update(rooms_confirmed=F('rooms_confirmed') + 1)
        )
        if not allocated:
            raise RoomSoldOut()

    registration.status = Registration.Status.CONFIRMED
    registration.confirmed_at = timezone.now()
    if paystack_reference:
        registration.paystack_reference = paystack_reference
    if not registration.qr:
        generate_qr(registration)
    registration.save()
    return registration
