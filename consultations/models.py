from datetime import date
from django.db import models
from members.models import Contact


class Consultation(models.Model):
    class Mode(models.TextChoices):
        REMOTE = 'Remote', 'Remote'
        ONSITE = 'Onsite', 'Onsite'

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='consultations')
    mode = models.CharField(max_length=10, choices=Mode.choices)
    scheduled_date = models.DateField()
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Consultation: {self.contact.full_name}"

    @property
    def is_today(self):
        return self.scheduled_date == date.today()
