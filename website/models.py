from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class GalleryItem(models.Model):
    class Type(models.TextChoices):
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'

    CATEGORY_CHOICES = [
        ('events', 'Events'),
        ('community', 'Community'),
        ('spiritual', 'Spiritual'),
        ('centres', 'Centres'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='gallery/', blank=True, help_text='For image type items.')
    thumbnail = models.ImageField(upload_to='gallery/thumbs/', blank=True, help_text='Auto-generated if left blank.')
    video_url = models.URLField(blank=True, help_text='YouTube/Vimeo URL for video type.')
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.IMAGE)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    date = models.DateField()
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title


class VolunteerOpportunity(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    commitment = models.CharField(max_length=255, help_text='e.g. 2 hours per week')
    skills = models.JSONField(default=list, help_text='List of required/preferred skills.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'volunteer opportunities'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Testimonial(models.Model):
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, help_text='e.g. Community Member')
    avatar = models.ImageField(upload_to='testimonials/', blank=True)
    quote = models.TextField()
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Lower numbers appear first.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f'{self.name} — {self.role}'


class TeamMember(models.Model):
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255)
    bio = models.TextField()
    image = models.ImageField(upload_to='team/', blank=True)
    order = models.PositiveIntegerField(default=0, help_text='Lower numbers appear first.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f'{self.name} — {self.role}'


class ImpactStat(models.Model):
    label = models.CharField(max_length=100, help_text='e.g. Lives Transformed')
    value = models.PositiveIntegerField()
    prefix = models.CharField(max_length=10, blank=True, help_text='e.g. $')
    suffix = models.CharField(max_length=10, blank=True, help_text='e.g. +')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.label}: {self.prefix}{self.value}{self.suffix}'


class ContactSubmission(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.subject}'


class VolunteerApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        REVIEWED = 'reviewed', 'Reviewed'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'

    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = PhoneNumberField()
    centre_preference = models.CharField(max_length=255, blank=True)
    skills = models.TextField(blank=True)
    availability = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.get_status_display()}'


class JoinCentreRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        DECLINED = 'declined', 'Declined'

    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = PhoneNumberField()
    centre = models.ForeignKey('centres.Centre', on_delete=models.CASCADE, related_name='join_requests')
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} → {self.centre.name}'


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-subscribed_at']

    def __str__(self):
        return self.email
