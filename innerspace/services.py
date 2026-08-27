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
    AccessLevel,
    AccessRequest,
    AccessRequestStatus,
    Membership,
    MembershipStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    outranks,
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


def _apply_level(student, access_level, now):
    """Move a student to `access_level`, if one was chosen.

    Honours the choice in both directions. Staff pick a level explicitly from a
    dropdown that shows the current one, so a lower selection is a correction,
    not an accident — and silently ignoring it (as this used to) is worse than
    applying it, because nothing on screen would say it had been refused.

    Returns the level held before the call, so the caller can log the change.
    """
    previous_level = student.access_level
    if access_level and access_level != previous_level:
        student.access_level = access_level
        student.updated_at = now
        student.save(update_fields=['access_level', 'updated_at'])
    return previous_level


def _log_level_change(entry, previous_level, student):
    """Fold a level change into an existing audit entry."""
    if student.access_level != previous_level:
        entry.previous_level = previous_level
        entry.new_level = student.access_level
        entry.save(update_fields=['previous_level', 'new_level'])
    return entry


def grant_access(student, actor, expires_at=None, amount=None, currency='GHS',
                 receipt_ref='', note='', access_level=None):
    """Give a student active access, recording any cash taken for it.

    `expires_at=None` means lifetime access, matching how the website reads a
    null `expiresAt`. Used for a first grant and for reactivating a lapsed or
    revoked membership alike.

    `access_level` places the student on the path — which courses they can
    open. This is the main way levels are ever set: students who buy through
    the website are given ADVANCED outright, so tiering exists for the people
    the office enrols by hand. Passing None leaves their current level alone.
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

    previous_level = _apply_level(student, access_level, now)

    action = AccessGrantLog.Action.REACTIVATE if existing else AccessGrantLog.Action.GRANT
    entry = _log(student, action, actor, previous_status, membership,
                 amount=amount, currency=currency, receipt_ref=receipt_ref, note=note)
    _log_level_change(entry, previous_level, student)
    return membership


def extend_access(student, actor, months=None, expires_at=None, amount=None,
                  currency='GHS', receipt_ref='', note='', access_level=None):
    """Push an existing membership's expiry further out.

    Extending by months counts from the current expiry when the membership is
    still running, and from today when it has already lapsed — so a student
    who renews late gets a full period rather than losing the gap.

    `access_level` works exactly as it does in `grant_access` — a renewal is a
    natural moment to move someone further along the path.
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

    previous_level = _apply_level(student, access_level, now)

    entry = _log(student, AccessGrantLog.Action.EXTEND, actor, previous_status, membership,
                 amount=amount, currency=currency, receipt_ref=receipt_ref, note=note)
    _log_level_change(entry, previous_level, student)
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


# ---------------------------------------------------------------------------
# Access level requests
# ---------------------------------------------------------------------------

def approve_access_request(access_request, actor, note=''):
    """Grant the level a student asked for.

    Takes effect immediately — unlike `revoke_access`, there is no session to
    wait on. The website reads `accessLevel` from the database on every render,
    so the student sees the newly opened courses on their next navigation
    without signing out.
    """
    now = timezone.now()
    student = access_request.student
    previous_level = student.access_level

    if not outranks(access_request.requested_level, previous_level):
        raise ValueError(
            f'{student.email or student.pk} is already on the '
            f'{student.get_access_level_display()} path — approving this would '
            f'not raise their access.'
        )

    with transaction.atomic(using=INNERSPACE_DB):
        student.access_level = access_request.requested_level
        student.updated_at = now
        student.save(update_fields=['access_level', 'updated_at'])

        access_request.status = AccessRequestStatus.APPROVED
        access_request.reviewed_at = now
        access_request.reviewed_by = _actor_name(actor)
        access_request.review_note = note or ''
        access_request.updated_at = now
        access_request.save(update_fields=[
            'status', 'reviewed_at', 'reviewed_by', 'review_note', 'updated_at',
        ])

    entry = _log(student, AccessGrantLog.Action.LEVEL_GRANT, actor, '', None, note=note)
    entry.previous_level = previous_level
    entry.new_level = student.access_level
    entry.save(update_fields=['previous_level', 'new_level'])
    return access_request


def decline_access_request(access_request, actor, note=''):
    """Turn a request down. Never touches the student's level."""
    now = timezone.now()
    student = access_request.student

    with transaction.atomic(using=INNERSPACE_DB):
        access_request.status = AccessRequestStatus.DECLINED
        access_request.reviewed_at = now
        access_request.reviewed_by = _actor_name(actor)
        access_request.review_note = note or ''
        access_request.updated_at = now
        access_request.save(update_fields=[
            'status', 'reviewed_at', 'reviewed_by', 'review_note', 'updated_at',
        ])

    entry = _log(student, AccessGrantLog.Action.LEVEL_DECLINE, actor, '', None, note=note)
    entry.previous_level = student.access_level
    entry.new_level = student.access_level
    entry.save(update_fields=['previous_level', 'new_level'])
    return access_request


def set_access_level(student, actor, access_level, note=''):
    """Move a student to a level directly, without a request.

    Allows lowering, which the request flow deliberately does not.
    """
    now = timezone.now()
    previous_level = student.access_level
    if access_level == previous_level:
        return student

    with transaction.atomic(using=INNERSPACE_DB):
        student.access_level = access_level
        student.updated_at = now
        student.save(update_fields=['access_level', 'updated_at'])

    entry = _log(student, AccessGrantLog.Action.LEVEL_GRANT, actor, '', None, note=note)
    entry.previous_level = previous_level
    entry.new_level = access_level
    entry.save(update_fields=['previous_level', 'new_level'])
    return student


def _actor_name(actor):
    if actor is None:
        return ''
    return getattr(actor, 'email', '') or actor.get_username()
