"""
Inner Space records as this admin sees them: plain objects built from the
student platform's API (see client.py), not database models.

drbaffourjan.com owns its database, schema and rules. These classes only give
the JSON the shape the templates expect — `student.display_name`,
`membership.is_active`, `req.get_requested_level_display` — so the pages read
the same as when they were backed by models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class AccessLevel(models.TextChoices):
    BEGINNER = 'BEGINNER', 'Beginner'
    INTERMEDIATE = 'INTERMEDIATE', 'Intermediate'
    ADVANCED = 'ADVANCED', 'Advanced'


ACCESS_LEVEL_RANK = {AccessLevel.BEGINNER: 0, AccessLevel.INTERMEDIATE: 1, AccessLevel.ADVANCED: 2}


def outranks(level, other):
    """Is `level` strictly above `other`?"""
    return ACCESS_LEVEL_RANK.get(level, -1) > ACCESS_LEVEL_RANK.get(other, -1)


class MembershipStatus(models.TextChoices):
    FREE = 'FREE', 'Free'
    ACTIVE = 'ACTIVE', 'Active'
    EXPIRED = 'EXPIRED', 'Expired'
    CANCELED = 'CANCELED', 'Canceled'


class PaymentProvider(models.TextChoices):
    STRIPE = 'STRIPE', 'Stripe'
    PAYSTACK = 'PAYSTACK', 'Paystack'
    FLUTTERWAVE = 'FLUTTERWAVE', 'Flutterwave'
    CASH = 'CASH', 'Cash (office)'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    SUCCESS = 'SUCCESS', 'Success'
    FAILED = 'FAILED', 'Failed'
    REFUNDED = 'REFUNDED', 'Refunded'


class AccessRequestStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    APPROVED = 'APPROVED', 'Approved'
    DECLINED = 'DECLINED', 'Declined'
    CANCELED = 'CANCELED', 'Canceled'


def _when(value):
    return parse_datetime(value) if value else None


def _label(choices, value):
    try:
        return choices(value).label
    except ValueError:
        return value or ''


@dataclass
class Membership:
    status: str
    started_at: datetime | None
    expires_at: datetime | None
    provider: str | None
    provider_ref: str | None
    is_active: bool

    @classmethod
    def from_api(cls, data):
        if not data:
            return None
        return cls(status=data['status'], started_at=_when(data.get('startedAt')), expires_at=_when(data.get('expiresAt')),
                   provider=data.get('provider'), provider_ref=data.get('providerRef'), is_active=bool(data.get('isActive')))

    @property
    def is_lifetime(self):
        return self.status == MembershipStatus.ACTIVE and self.expires_at is None

    @property
    def days_remaining(self):
        return None if self.expires_at is None else (self.expires_at - timezone.now()).days

    def get_status_display(self):
        return _label(MembershipStatus, self.status)

    @property
    def state_display(self):
        """For a membership that no longer gives access: an ACTIVE row past its date reads Expired."""
        if self.status == MembershipStatus.ACTIVE and not self.is_active:
            return 'Expired'
        return self.get_status_display()

    def get_provider_display(self):
        return _label(PaymentProvider, self.provider) if self.provider else ''


@dataclass
class Student:
    pk: str
    email: str | None
    email_verified: datetime | None
    phone: str | None
    first_name: str | None
    last_name: str | None
    name: str | None
    access_level: str
    country: str | None
    has_completed_onboarding: bool
    created_at: datetime | None
    membership: Membership | None

    @classmethod
    def from_api(cls, data):
        return cls(pk=data['id'], email=data.get('email'), email_verified=_when(data.get('emailVerified')),
                   phone=data.get('phone'), first_name=data.get('firstName'), last_name=data.get('lastName'),
                   name=data.get('name'), access_level=data['accessLevel'], country=data.get('country'),
                   has_completed_onboarding=bool(data.get('hasCompletedOnboarding')),
                   created_at=_when(data.get('createdAt')), membership=Membership.from_api(data.get('membership')))

    @property
    def id(self):
        return self.pk

    @property
    def display_name(self):
        parts = [p for p in (self.first_name, self.last_name) if p]
        return ' '.join(parts) or (self.name or '')

    def get_access_level_display(self):
        return _label(AccessLevel, self.access_level)

    def __str__(self):
        return self.email or self.display_name or self.pk


@dataclass
class Payment:
    provider: str
    provider_ref: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime | None

    @classmethod
    def from_api(cls, data):
        return cls(provider=data['provider'], provider_ref=data['providerRef'], amount=Decimal(data['amount']),
                   currency=data['currency'], status=data['status'], created_at=_when(data.get('createdAt')))

    def get_provider_display(self):
        return _label(PaymentProvider, self.provider)

    def get_status_display(self):
        return _label(PaymentStatus, self.status)


@dataclass
class AccessRequest:
    pk: str
    requested_level: str
    current_level: str
    course_slug: str | None
    message: str | None
    status: str
    reviewed_at: datetime | None
    reviewed_by: str | None
    review_note: str | None
    created_at: datetime | None
    student: Student | None = field(default=None)

    @classmethod
    def from_api(cls, data, student=None):
        nested = data.get('student')
        return cls(pk=data['id'], requested_level=data['requestedLevel'], current_level=data['currentLevel'],
                   course_slug=data.get('courseSlug'), message=data.get('message'), status=data['status'],
                   reviewed_at=_when(data.get('reviewedAt')), reviewed_by=data.get('reviewedBy'),
                   review_note=data.get('reviewNote'), created_at=_when(data.get('createdAt')),
                   student=Student.from_api(nested) if nested else student)

    @property
    def is_pending(self):
        return self.status == AccessRequestStatus.PENDING

    @property
    def is_upgrade(self):
        """False if the student has since reached or passed the level asked for."""
        return outranks(self.requested_level, self.student.access_level) if self.student else True

    def get_requested_level_display(self):
        return _label(AccessLevel, self.requested_level)

    def get_current_level_display(self):
        return _label(AccessLevel, self.current_level)

    def get_status_display(self):
        return _label(AccessRequestStatus, self.status)
