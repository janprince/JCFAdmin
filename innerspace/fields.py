"""Field types bridging Prisma's column choices to Django's expectations."""

from datetime import timezone as dt_timezone

from django.db import models
from django.utils import timezone


class PrismaDateTimeField(models.DateTimeField):
    """A Prisma `DateTime`, stored as `timestamp(3)` — *without* a time zone.

    Prisma writes UTC into a naive column. Django, running with USE_TZ = True,
    assumes `timestamptz` and so hands back naive datetimes it then refuses to
    compare against `timezone.now()`:

        TypeError: can't compare offset-naive and offset-aware datetimes

    Converting in both directions here means the rest of the codebase — views,
    templates, the service layer — only ever sees aware UTC datetimes, and
    query parameters land in the column in exactly the form Prisma expects.
    """

    def from_db_value(self, value, expression, connection):
        if value is not None and timezone.is_naive(value):
            return value.replace(tzinfo=dt_timezone.utc)
        return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is not None and timezone.is_aware(value):
            return timezone.make_naive(value, dt_timezone.utc)
        return value
