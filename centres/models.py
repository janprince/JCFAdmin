from django.db import models
from django.utils.text import slugify
from phonenumber_field.modelfields import PhoneNumberField


class Centre(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    location = models.CharField(max_length=255, help_text='City name, e.g. Accra')
    address = models.CharField(max_length=500)
    country = models.CharField(max_length=100, default='Ghana')
    image = models.ImageField(upload_to='centres/', blank=True)
    description = models.TextField()
    leader_name = models.CharField(max_length=255)
    leader_title = models.CharField(max_length=255, help_text='e.g. Centre Director')
    leader_avatar = models.ImageField(upload_to='centres/leaders/', blank=True)
    contact_email = models.EmailField()
    contact_phone = PhoneNumberField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    member_count = models.PositiveIntegerField(default=0, help_text='Approximate number of members.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.country})'
