from django.db import models


class Teaching(models.Model):
    class Format(models.TextChoices):
        LECTURE = 'lecture', 'Lecture'
        INTERVIEW = 'interview', 'Interview'
        LIVE = 'live', 'Live'
        DOCUMENTARY = 'documentary', 'Documentary'
        PROMOTIONAL = 'promotional', 'Promotional'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ARCHIVE = 'archive', 'Archive'
        PUBLISHED = 'published', 'Published'

    class Language(models.TextChoices):
        ENGLISH = 'english', 'English'
        TWI = 'twi', 'Twi'

    topic = models.CharField(max_length=255, unique=True)
    format = models.CharField(max_length=50, choices=Format.choices, default=Format.LECTURE)
    language = models.CharField(max_length=50, choices=Language.choices, default=Language.ENGLISH)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.topic
