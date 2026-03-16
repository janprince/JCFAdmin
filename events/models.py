from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class EventCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'event categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Event(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(help_text='Short summary for listing cards.')
    content = models.TextField(help_text='Full event details (rich text).')
    date = models.DateField(help_text='Event start date.')
    end_date = models.DateField(blank=True, null=True, help_text='Optional end date for multi-day events.')
    time = models.TimeField(help_text='Event start time.')
    location = models.CharField(max_length=255, help_text='Venue or city name.')
    address = models.CharField(max_length=500, blank=True)
    image = models.ImageField(upload_to='events/', blank=True)
    category = models.ForeignKey(EventCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    registration_url = models.URLField(blank=True, help_text='External registration link.')
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def is_past(self):
        return self.date < timezone.now().date()

    def __str__(self):
        return self.title
