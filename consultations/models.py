from datetime import date
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from members.models import Contact


class Consultation(models.Model):
    class Mode(models.TextChoices):
        REMOTE = 'Remote', 'Remote'
        ONSITE = 'Onsite', 'Onsite'

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='consultations')
    mode = models.CharField(max_length=10, choices=Mode.choices)
    scheduled_date = models.DateField()
    done = models.BooleanField(default=False)
    sms_sent_at = models.DateTimeField(null=True, blank=True, help_text='When the date was last texted to the contact.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Consultation: {self.contact.full_name}"

    @property
    def is_today(self):
        return self.scheduled_date == date.today()


class ConsultationRequest(models.Model):
    """Details sent through the public booking form, waiting to be scheduled.

    Replaces the questionnaire the office used to send on WhatsApp. Each
    request is linked to a contact: a new one, or an existing contact with the
    same name and phone. Existing contacts are never changed by the public form.
    """
    class Status(models.TextChoices):
        NEW = 'new', 'New'
        BOOKED = 'booked', 'Booked'
        CLOSED = 'closed', 'Closed'

    class Heard(models.TextChoices):
        FRIEND = 'friend', 'A friend or family member'
        YOUTUBE = 'youtube', 'YouTube'
        FACEBOOK = 'facebook', 'Facebook'
        TIKTOK = 'tiktok', 'TikTok'
        INSTAGRAM = 'instagram', 'Instagram'
        RADIO_TV = 'radio_tv', 'Radio or TV'
        WEBSITE = 'website', 'The Foundation website'
        CENTRE = 'centre', 'A JCF centre or event'
        OTHER = 'other', 'Somewhere else'

    class Preference(models.TextChoices):
        ONSITE = 'Onsite', 'In person'
        REMOTE = 'Remote', 'Remotely (phone or video)'

    full_name = models.CharField(max_length=255)
    phone = PhoneNumberField()
    email = models.EmailField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    day_of_birth = models.CharField(max_length=10, choices=Contact.Weekday.choices, blank=True)
    profession = models.CharField(max_length=255)
    hometown = models.CharField('Home town / region', max_length=255)
    religion = models.CharField(max_length=255)
    residence = models.CharField('Current residence', max_length=255)
    heard_from = models.CharField(max_length=20, choices=Heard.choices, blank=True)
    heard_detail = models.CharField(max_length=255, blank=True)
    preferred_mode = models.CharField(max_length=10, choices=Preference.choices, blank=True)
    note = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name='booking_requests')
    created_contact = models.BooleanField(default=False, help_text='The form added this person to contacts.')
    consultation = models.ForeignKey(Consultation, null=True, blank=True, on_delete=models.SET_NULL, related_name='requests')
    handled_by = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'Booking request from {self.full_name}'

    @property
    def birth_weekday(self):
        if self.date_of_birth:
            return Contact.Weekday.values[self.date_of_birth.weekday()]
        return self.day_of_birth

    @property
    def referral(self):
        """How they heard, as one line for the contact's "Referred by"."""
        label = self.get_heard_from_display() if self.heard_from else ''
        return ' — '.join(part for part in (label, self.heard_detail) if part)
