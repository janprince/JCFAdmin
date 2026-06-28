"""
Generalized "Programs" domain.

A Program is any event/offering members or the public can register for (the
annual retreat is one members-only Program). Admins author a new Program each
year with a dynamic registration form (`form_schema`), optional accommodation
tiers, and cost line items — no hardcoded fees/dates in code.
"""
from decimal import Decimal

from django.db import models
from django.utils.text import slugify


class Program(models.Model):
    class Audience(models.TextChoices):
        PUBLIC = 'public', 'Public (everyone)'
        MEMBERS = 'members', 'Members & students only'
        STUDENTS = 'students', 'Students only'

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    year = models.PositiveIntegerField(help_text='Edition year, used in the registration reference.')
    description = models.TextField(blank=True)
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.PUBLIC)

    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    venue = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to='programs/', blank=True)

    registration_opens_at = models.DateTimeField(null=True, blank=True)
    registration_closes_at = models.DateTimeField(null=True, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True, help_text='Max registrations (blank = unlimited).')

    requires_payment = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default='GHS')

    # Dynamic registration form: a list of field definitions, e.g.
    # [{"name": "emergency_contact", "label": "Emergency contact", "type": "text", "required": true}]
    form_schema = models.JSONField(default=list, blank=True)

    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', 'title']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f'{self.title}-{self.year}')
        super().save(*args, **kwargs)

    def compute_amount(self, quantity=1, tier=None) -> Decimal:
        """Server-side price: flat + per-person line items + tier * quantity."""
        quantity = max(1, int(quantity or 1))
        total = Decimal('0')
        for item in self.cost_line_items.filter(is_active=True):
            if item.unit == CostLineItem.Unit.PER_PERSON:
                total += item.amount * quantity
            else:
                total += item.amount
        if tier is not None:
            total += tier.price_per_person * quantity
        return total

    def __str__(self):
        return f'{self.title} ({self.year})'


class AccommodationTier(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='accommodation_tiers')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price_per_person = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_rooms = models.PositiveIntegerField(default=0)
    rooms_confirmed = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    @property
    def rooms_available(self):
        return max(0, self.total_rooms - self.rooms_confirmed)

    @property
    def is_sold_out(self):
        return self.total_rooms > 0 and self.rooms_confirmed >= self.total_rooms

    def __str__(self):
        return f'{self.name} — {self.program.title}'


class CostLineItem(models.Model):
    class Unit(models.TextChoices):
        FLAT = 'flat', 'Flat (once per registration)'
        PER_PERSON = 'per_person', 'Per person'

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='cost_line_items')
    label = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=12, choices=Unit.choices, default=Unit.FLAT)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.label}: {self.amount} ({self.unit})'


class Registration(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending payment'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='registrations')
    contact = models.ForeignKey('members.Contact', on_delete=models.CASCADE, related_name='registrations')
    reference = models.CharField(max_length=40, unique=True, blank=True)

    quantity = models.PositiveSmallIntegerField(default=1, help_text='Number of people in this registration.')
    accommodation_tier = models.ForeignKey(
        AccommodationTier, on_delete=models.SET_NULL, null=True, blank=True, related_name='registrations'
    )
    answers = models.JSONField(default=dict, blank=True, help_text='Responses to the program form_schema.')

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='GHS')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    paystack_reference = models.CharField(max_length=100, blank=True)
    qr = models.ImageField(upload_to='programs/qr/', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def assign_reference(self):
        """JCF-{year}-{5-digit id} — set after the first save."""
        if not self.reference and self.pk:
            self.reference = f'JCF-{self.program.year}-{self.pk:05d}'
            self.save(update_fields=['reference'])
        return self.reference

    def __str__(self):
        return self.reference or f'Registration #{self.pk}'
