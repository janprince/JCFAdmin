"""
Mobile API auth models.

Members/students are existing `members.Contact` records (no Django user / no
password). They authenticate from the mobile app via a one-time code (OTP) sent
to their phone or email, and then carry a `MobileToken` (access + refresh).
"""
import hashlib
import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone

from members.models import Contact

# Lifetimes
CODE_TTL = timedelta(minutes=10)
ACCESS_TTL = timedelta(days=7)
REFRESH_TTL = timedelta(days=30)
MAX_CODE_ATTEMPTS = 5


def _hash_code(code: str) -> str:
    """Store only a hash of the OTP, never the plaintext."""
    return hashlib.sha256(code.encode()).hexdigest()


class LoginCode(models.Model):
    """A one-time login code issued to a Contact via SMS or email."""

    class Channel(models.TextChoices):
        SMS = 'sms', 'SMS'
        EMAIL = 'email', 'Email'

    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name='login_codes'
    )
    code_hash = models.CharField(max_length=64)
    channel = models.CharField(max_length=10, choices=Channel.choices)
    destination = models.CharField(max_length=255, help_text='Phone or email the code was sent to.')
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['contact', 'consumed_at'])]

    @classmethod
    def issue(cls, contact, channel, destination):
        """Create a fresh code, invalidating any prior unconsumed ones."""
        cls.objects.filter(contact=contact, consumed_at__isnull=True).update(
            consumed_at=timezone.now()
        )
        code = f'{secrets.randbelow(1_000_000):06d}'
        obj = cls.objects.create(
            contact=contact,
            code_hash=_hash_code(code),
            channel=channel,
            destination=destination,
            expires_at=timezone.now() + CODE_TTL,
        )
        return obj, code

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def matches(self, code: str) -> bool:
        return secrets.compare_digest(self.code_hash, _hash_code(code))


class MobileToken(models.Model):
    """An access + refresh token pair bound to a Contact (mobile session)."""

    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name='mobile_tokens'
    )
    access_token = models.CharField(max_length=64, unique=True, db_index=True)
    refresh_token = models.CharField(max_length=64, unique=True, db_index=True)
    access_expires_at = models.DateTimeField()
    refresh_expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def issue(cls, contact):
        now = timezone.now()
        return cls.objects.create(
            contact=contact,
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(32),
            access_expires_at=now + ACCESS_TTL,
            refresh_expires_at=now + REFRESH_TTL,
        )

    def rotate_access(self):
        """Issue a new access token from a still-valid refresh token."""
        self.access_token = secrets.token_urlsafe(32)
        self.access_expires_at = timezone.now() + ACCESS_TTL
        self.save(update_fields=['access_token', 'access_expires_at'])
        return self

    @property
    def access_valid(self):
        return not self.revoked and timezone.now() < self.access_expires_at

    @property
    def refresh_valid(self):
        return not self.revoked and timezone.now() < self.refresh_expires_at
