from datetime import date
from django.db import models
from members.models import Contact


class Consultation(models.Model):
    class Mode(models.TextChoices):
        REMOTE = 'Remote', 'Remote'
        ONSITE = 'Onsite', 'Onsite'

    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        CONFIRMED = 'confirmed', 'Confirmed'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='consultations')
    mode = models.CharField(max_length=10, choices=Mode.choices)
    scheduled_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    note = models.TextField(blank=True, help_text='Reason / notes from the member.')
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Consultation: {self.contact.full_name}"

    @property
    def is_today(self):
        return self.scheduled_date == date.today()
