from django.db import models
from django.utils.text import slugify
from phonenumber_field.modelfields import PhoneNumberField


class CauseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'cause categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Cause(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(help_text='Short summary for listing cards.')
    content = models.TextField(help_text='Full cause details (rich text).')
    image = models.ImageField(upload_to='causes/', blank=True)
    gallery = models.JSONField(default=list, blank=True, help_text='List of additional image paths.')
    goal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='GHS')
    category = models.ForeignKey(CauseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='causes')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def raised_amount(self):
        total = self.donations.filter(status='completed').aggregate(total=models.Sum('amount'))['total']
        return total or 0

    @property
    def donors_count(self):
        return self.donations.filter(status='completed').values('donor_email').distinct().count()

    @property
    def progress_percent(self):
        if self.goal_amount:
            return min(100, int(self.raised_amount / self.goal_amount * 100))
        return 0

    def __str__(self):
        return self.title


class Donation(models.Model):
    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        MOBILE_MONEY = 'mobile_money', 'Mobile Money'
        ONLINE = 'online', 'Online (Paystack)'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    cause = models.ForeignKey(Cause, on_delete=models.SET_NULL, null=True, blank=True, related_name='donations',
                              help_text='Leave blank for general donations.')
    donor_name = models.CharField(max_length=255)
    donor_email = models.EmailField(blank=True)
    donor_phone = PhoneNumberField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='GHS')
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    reference = models.CharField(max_length=100, blank=True, help_text='Bank or mobile money reference.')
    paystack_reference = models.CharField(max_length=100, blank=True, help_text='Paystack transaction reference.')
    notes = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    donated_at = models.DateTimeField(help_text='When the donation was made.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-donated_at']

    def __str__(self):
        name = 'Anonymous' if self.is_anonymous else self.donor_name
        return f'{name} — {self.currency} {self.amount}'
