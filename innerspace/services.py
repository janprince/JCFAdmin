"""
Every write to the Innerspace database goes through this module.

Views never touch the remote models directly. Keeping the writes in one place
means the rules that matter — always stamp `updatedAt`, always record a
payment for cash taken at the desk, always write an audit entry — are applied
the same way no matter which screen triggered them.

A note on atomicity: the membership/payment rows live in the Innerspace
database and the audit entry lives in JCF's, so a single transaction cannot
span both. The remote writes are committed as one unit first; if the audit
write then fails, the student still has correct access and the failure is
loud. The reverse order would risk logging a grant that never happened.
"""

import calendar
from datetime import datetime, time as dt_time

from django.db import transaction
from django.utils import timezone

from .models import (
    AccessGrantLog,
    Membership,
    MembershipStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
)

INNERSPACE_DB = 'innerspace'


def add_months(moment, months):
    """Return `moment` shifted forward by `months`, clamping the day.

    31 Jan + 1 month is 28 Feb (or 29 in a leap year), which is what someone
    at the desk means when they say "one month from today".
    """
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def end_of_day(date_value):
    """Treat an admin-entered expiry date as end of that day, not midnight."""
    naive = datetime.combine(date_value, dt_time.max)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _payment_reference(student, receipt_ref):
    """Payments need a providerRef; it is NOT NULL on the Innerspace side."""
    if receipt_ref:
        return f'CASH-{receipt_ref}'
    return f'CASH-{timezone.now():%Y%m%d%H%M%S}-{student.pk[-6:]}'


def _record_payment(student, amount, currency, receipt_ref):
    if not amount or amount <= 0:
        return None
    return Payment.objects.create(
        student=student,
        provider=PaymentProvider.CASH,
        provider_ref=_payment_reference(student, receipt_ref),
        amount=amount,
        currency=currency or 'GHS',
        status=PaymentStatus.SUCCESS,
        created_at=timezone.now(),
    )


def _log(student, action, actor, previous_status, membership, amount=None,
         currency='', receipt_ref='', note=''):
    return AccessGrantLog.objects.create(
        student_id=student.pk,
        student_email=student.email or '',
        action=action,
        performed_by=actor,
        previous_status=previous_status or '',
        new_status=membership.status if membership else '',
        expires_at=membership.expires_at if membership else None,
        amount=amount,
        currency=currency or '',
        receipt_ref=receipt_ref or '',
        note=note or '',
    )


def grant_access(student, actor, expires_at=None, amount=None, currency='GHS',
                 receipt_ref='', note=''):
    """Give a student active access, recording any cash taken for it.

    `expires_at=None` means lifetime access, matching how the website reads a
    null `expiresAt`. Used for a first grant and for reactivating a lapsed or
    revoked membership alike.
    """
    now = timezone.now()
    existing = Membership.objects.filter(student=student).first()
    previous_status = existing.status if existing else ''

    with transaction.atomic(using=INNERSPACE_DB):
        membership, _created = Membership.objects.update_or_create(
            student=student,
            defaults={
                'status': MembershipStatus.ACTIVE,
                # Preserve the original join date when reactivating — it is
                # when they first became a student, not when we last touched
                # the record.
                'started_at': existing.started_at if existing else now,
                'expires_at': expires_at,
                'provider': PaymentProvider.CASH,
                'provider_ref': _payment_reference(student, receipt_ref),
                'updated_at': now,
            },
        )
        _record_payment(student, amount, currency, receipt_ref)

    action = AccessGrantLog.Action.REACTIVATE if existing else AccessGrantLog.Action.GRANT
    _log(student, action, actor, previous_status, membership,
         amount=amount, currency=currency, receipt_ref=receipt_ref, note=note)
    return membership


def extend_access(student, actor, months=None, expires_at=None, amount=None,
                  currency='GHS', receipt_ref='', note=''):
    """Push an existing membership's expiry further out.

    Extending by months counts from the current expiry when the membership is
    still running, and from today when it has already lapsed — so a student
    who renews late gets a full period rather than losing the gap.
    """
    now = timezone.now()
    membership = Membership.objects.filter(student=student).first()
    if membership is None:
        raise Membership.DoesNotExist('This student has no membership to extend.')

    previous_status = membership.status

    if expires_at is None and months:
        base = membership.expires_at if (membership.expires_at and membership.expires_at > now) else now
        expires_at = add_months(base, months)

    with transaction.atomic(using=INNERSPACE_DB):
        membership.status = MembershipStatus.ACTIVE
        membership.expires_at = expires_at
        membership.provider = PaymentProvider.CASH
        membership.provider_ref = _payment_reference(student, receipt_ref)
        membership.updated_at = now
        membership.save(update_fields=[
            'status', 'expires_at', 'provider', 'provider_ref', 'updated_at',
        ])
        _record_payment(student, amount, currency, receipt_ref)

    _log(student, AccessGrantLog.Action.EXTEND, actor, previous_status, membership,
         amount=amount, currency=currency, receipt_ref=receipt_ref, note=note)
    return membership


def revoke_access(student, actor, note=''):
    """Cancel a membership.

    Takes effect on the student's next sign-in rather than immediately: the
    website carries `hasMembership` in a JWT and only re-reads the database
    when that flag is false (see src/lib/auth.ts in drbaffourjan). A student
    with a live session keeps access until their token refreshes.
    """
    now = timezone.now()
    membership = Membership.objects.filter(student=student).first()
    if membership is None:
        raise Membership.DoesNotExist('This student has no membership to revoke.')

    previous_status = membership.status

    with transaction.atomic(using=INNERSPACE_DB):
        membership.status = MembershipStatus.CANCELED
        membership.updated_at = now
        membership.save(update_fields=['status', 'updated_at'])

    _log(student, AccessGrantLog.Action.REVOKE, actor, previous_status, membership, note=note)
    return membership
