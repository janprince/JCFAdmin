"""
Models mirroring the Innerspace (drbaffourjan.com) Prisma schema.

Every model here is `managed = False` and lives in a different database. The
Prisma schema at drbaffourjan/prisma/schema.prisma is the source of truth — if
it changes, these mappings must be updated by hand. `manage.py innerspace_check`
compares the two and reports drift.

Mapping notes, all of which are load-bearing:

* Table names are case-sensitive. Prisma only `@@map`ped User -> `users`;
  Membership and Payment are literally `"Membership"` and `"Payment"`.
* Column naming is inconsistent between tables: `users` is snake_case
  (`first_name`) apart from `accessLevel`, while Membership and Payment are
  camelCase throughout. Every field therefore names its column explicitly.
* `id` columns are TEXT with no database default — Prisma generates cuids in
  the application layer, so we do too (see innerspace/cuid.py).
* `updatedAt` is NOT NULL with no database default. Prisma sets it on every
  write; so must we, or the insert is rejected.
* Status/provider columns are native Postgres enum types. They work as
  CharFields because Django's psycopg3 backend uses client-side parameter
  binding by default, which sends them as untyped literals that Postgres
  coerces to the enum. Do not set OPTIONS['server_side_binding'] = True on the
  innerspace alias — it would send them as `text` and every comparison would
  fail with "operator does not exist".
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from .cuid import cuid
from .fields import PrismaDateTimeField


class InnerspaceModel(models.Model):
    """Marker base class. The router sends these to the Innerspace database."""

    class Meta:
        abstract = True
        managed = False


class MembershipStatus(models.TextChoices):
    FREE = 'FREE', 'Free'
    ACTIVE = 'ACTIVE', 'Active'
    EXPIRED = 'EXPIRED', 'Expired'
    CANCELED = 'CANCELED', 'Canceled'


class PaymentProvider(models.TextChoices):
    STRIPE = 'STRIPE', 'Stripe'
    PAYSTACK = 'PAYSTACK', 'Paystack'
    FLUTTERWAVE = 'FLUTTERWAVE', 'Flutterwave'
    CASH = 'CASH', 'Cash (in person)'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    SUCCESS = 'SUCCESS', 'Success'
    FAILED = 'FAILED', 'Failed'
    REFUNDED = 'REFUNDED', 'Refunded'


class AccessLevel(models.TextChoices):
    BEGINNER = 'BEGINNER', 'Beginner'
    INTERMEDIATE = 'INTERMEDIATE', 'Intermediate'
    ADVANCED = 'ADVANCED', 'Advanced'


class AccessRequestStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    APPROVED = 'APPROVED', 'Approved'
    DECLINED = 'DECLINED', 'Declined'
    CANCELED = 'CANCELED', 'Canceled'


# Higher rank unlocks everything at or below it. Mirrors ACCESS_LEVEL_RANK in
# drbaffourjan/src/lib/access-levels.ts — keep the two in step.
ACCESS_LEVEL_RANK = {
    AccessLevel.BEGINNER: 0,
    AccessLevel.INTERMEDIATE: 1,
    AccessLevel.ADVANCED: 2,
}


def outranks(level, other):
    """Is `level` strictly above `other`?"""
    return ACCESS_LEVEL_RANK.get(level, -1) > ACCESS_LEVEL_RANK.get(other, -1)


class Student(InnerspaceModel):
    """A registered account on drbaffourjan.com (Prisma model `User`)."""

    id = models.CharField(primary_key=True, max_length=32, default=cuid, editable=False)
    email = models.EmailField(db_column='email', null=True, blank=True, unique=True)
    email_verified = PrismaDateTimeField(db_column='email_verified', null=True, blank=True)
    phone = models.CharField(db_column='phone', max_length=32, null=True, blank=True, unique=True)
    phone_verified = PrismaDateTimeField(db_column='phone_verified', null=True, blank=True)

    first_name = models.CharField(db_column='first_name', max_length=255, null=True, blank=True)
    last_name = models.CharField(db_column='last_name', max_length=255, null=True, blank=True)
    name = models.CharField(db_column='name', max_length=255, null=True, blank=True)
    image = models.TextField(db_column='image', null=True, blank=True)
    access_level = models.CharField(
        db_column='accessLevel', max_length=20, choices=AccessLevel.choices,
        default=AccessLevel.INTERMEDIATE,
    )

    country_code = models.CharField(db_column='country_code', max_length=8, null=True, blank=True)
    country = models.CharField(db_column='country', max_length=255, null=True, blank=True)
    has_completed_onboarding = models.BooleanField(
        db_column='has_completed_onboarding', default=False,
    )

    created_at = PrismaDateTimeField(db_column='created_at', default=timezone.now)
    updated_at = PrismaDateTimeField(db_column='updated_at', default=timezone.now)

    class Meta(InnerspaceModel.Meta):
        db_table = 'users'
        ordering = ['-created_at']
        verbose_name = 'Innerspace student'

    def __str__(self):
        return self.email or self.display_name or self.pk

    @property
    def display_name(self):
        parts = [p for p in (self.first_name, self.last_name) if p]
        return ' '.join(parts) or (self.name or '')

    @property
    def initial(self):
        source = self.display_name or self.email or '?'
        return source[0].upper()


class Membership(InnerspaceModel):
    """Paid access to the Innerspace programme. At most one row per student."""

    id = models.CharField(primary_key=True, max_length=32, default=cuid, editable=False)
    student = models.OneToOneField(
        Student, db_column='userId', on_delete=models.DO_NOTHING,
        related_name='membership',
    )

    status = models.CharField(db_column='status', max_length=20, choices=MembershipStatus.choices)
    started_at = PrismaDateTimeField(db_column='startedAt')
    expires_at = PrismaDateTimeField(db_column='expiresAt', null=True, blank=True)

    provider = models.CharField(
        db_column='provider', max_length=20, choices=PaymentProvider.choices,
        null=True, blank=True,
    )
    provider_ref = models.CharField(db_column='providerRef', max_length=255, null=True, blank=True)

    created_at = PrismaDateTimeField(db_column='createdAt', default=timezone.now)
    updated_at = PrismaDateTimeField(db_column='updatedAt', default=timezone.now)

    class Meta(InnerspaceModel.Meta):
        db_table = 'Membership'

    def __str__(self):
        return f'{self.student_id}: {self.status}'

    @property
    def is_active(self):
        """Mirrors the website's own gate — see src/lib/auth.ts in drbaffourjan.

        Keep this in step with that check; if they disagree, the admin will
        show one thing and the student will experience another.
        """
        if self.status != MembershipStatus.ACTIVE:
            return False
        return self.expires_at is None or self.expires_at > timezone.now()

    @property
    def is_lifetime(self):
        return self.status == MembershipStatus.ACTIVE and self.expires_at is None

    @property
    def days_remaining(self):
        if self.expires_at is None:
            return None
        return (self.expires_at - timezone.now()).days


class Payment(InnerspaceModel):
    """A payment recorded against a student, online or taken at the office."""

    id = models.CharField(primary_key=True, max_length=32, default=cuid, editable=False)
    student = models.ForeignKey(
        Student, db_column='userId', on_delete=models.DO_NOTHING, related_name='payments',
    )

    provider = models.CharField(db_column='provider', max_length=20, choices=PaymentProvider.choices)
    provider_ref = models.CharField(db_column='providerRef', max_length=255)

    amount = models.DecimalField(db_column='amount', max_digits=65, decimal_places=30)
    currency = models.CharField(db_column='currency', max_length=8)
    status = models.CharField(db_column='status', max_length=20, choices=PaymentStatus.choices)

    created_at = PrismaDateTimeField(db_column='createdAt', default=timezone.now)

    class Meta(InnerspaceModel.Meta):
        db_table = 'Payment'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.currency} {self.amount} ({self.provider})'


class AccessRequest(InnerspaceModel):
    """A student asking to be moved up to a higher access level.

    Created by the website when someone opens a course above their level;
    resolved here. Approving writes both this row and `users.accessLevel`.

    Unlike a membership change, a level change takes effect on the student's
    very next page load — the website reads `accessLevel` from the database on
    every render rather than caching it in their session token.
    """

    id = models.CharField(primary_key=True, max_length=32, default=cuid, editable=False)
    student = models.ForeignKey(
        Student, db_column='user_id', on_delete=models.DO_NOTHING,
        related_name='access_requests',
    )

    requested_level = models.CharField(
        db_column='requested_level', max_length=20, choices=AccessLevel.choices,
    )
    current_level = models.CharField(
        db_column='current_level', max_length=20, choices=AccessLevel.choices,
        help_text='The level the student held when they asked.',
    )

    course_id = models.CharField(db_column='course_id', max_length=32, null=True, blank=True)
    course_slug = models.CharField(db_column='course_slug', max_length=255, null=True, blank=True)
    message = models.TextField(db_column='message', null=True, blank=True)

    status = models.CharField(
        db_column='status', max_length=20, choices=AccessRequestStatus.choices,
        default=AccessRequestStatus.PENDING,
    )

    reviewed_at = PrismaDateTimeField(db_column='reviewed_at', null=True, blank=True)
    reviewed_by = models.CharField(db_column='reviewed_by', max_length=255, null=True, blank=True)
    review_note = models.TextField(db_column='review_note', null=True, blank=True)

    created_at = PrismaDateTimeField(db_column='created_at', default=timezone.now)
    updated_at = PrismaDateTimeField(db_column='updated_at', default=timezone.now)

    class Meta(InnerspaceModel.Meta):
        db_table = 'access_requests'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.student_id}: {self.current_level} -> {self.requested_level}'

    @property
    def is_pending(self):
        return self.status == AccessRequestStatus.PENDING

    @property
    def is_upgrade(self):
        """False if the student has since reached or passed the level asked for."""
        return outranks(self.requested_level, self.student.access_level)


# ---------------------------------------------------------------------------
# JCF-side models. These live in the default database and migrate normally.
# ---------------------------------------------------------------------------

class AccessGrantLog(models.Model):
    """Audit trail for every membership change made from this admin.

    Deliberately stored in JCF's own database rather than the Innerspace one:
    it keeps the Prisma schema untouched, and it means the record of who gave
    whom access survives independently of the student platform.
    """

    class Action(models.TextChoices):
        GRANT = 'grant', 'Granted access'
        EXTEND = 'extend', 'Extended access'
        REVOKE = 'revoke', 'Revoked access'
        REACTIVATE = 'reactivate', 'Reactivated access'
        LEVEL_GRANT = 'level_grant', 'Raised access level'
        LEVEL_DECLINE = 'level_decline', 'Declined level request'

    # Not a ForeignKey — the student lives in another database. The email is
    # denormalised so the log stays readable even if the account is deleted.
    student_id = models.CharField(max_length=32, db_index=True)
    student_email = models.EmailField(blank=True)

    action = models.CharField(max_length=20, choices=Action.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='innerspace_grants',
    )

    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)

    # Only set for the level actions.
    previous_level = models.CharField(max_length=20, blank=True)
    new_level = models.CharField(max_length=20, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, blank=True)
    receipt_ref = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'access grant log entry'
        verbose_name_plural = 'access grant log'
        permissions = [
            ('manage_innerspace_access', 'Can grant, extend and revoke Innerspace access'),
        ]

    def __str__(self):
        return f'{self.get_action_display()} — {self.student_email}'
