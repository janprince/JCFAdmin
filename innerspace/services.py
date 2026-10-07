"""
Every change this admin makes to an Inner Space student goes through here.

The change itself happens on drbaffourjan.com, through its office API
(client.py) — the platform owns the data and the rules: lifetime vs. dated
access, renewals counted from the current expiry, cash payments recorded,
level requests that may only raise a level.

What stays here is JCF's own audit trail. `AccessGrantLog` lives in JCF's
database and names the portal user who acted, which the platform cannot know.
Each entry is written from the before/after values the API returns, and only
after the platform has committed the change: a failed call leaves no entry,
and the reverse risk — an entry for a change that never happened — cannot
arise.
"""

from .client import InnerspaceClient
from .models import AccessGrantLog


def _log(student, action, actor, result, amount=None, currency='', receipt_ref='', note=''):
    membership = student.membership
    return AccessGrantLog.objects.create(
        student_id=student.pk,
        student_email=student.email or '',
        action=action,
        performed_by=actor,
        previous_status=result.get('previousStatus') or '',
        new_status=membership.status if membership and action not in _LEVEL_ACTIONS else '',
        expires_at=membership.expires_at if membership and action not in _LEVEL_ACTIONS else None,
        previous_level=result.get('previousLevel') or '',
        new_level=student.access_level,
        amount=amount,
        currency=currency if amount else '',
        receipt_ref=receipt_ref or '',
        note=note or '',
    )


_LEVEL_ACTIONS = {AccessGrantLog.Action.LEVEL_GRANT, AccessGrantLog.Action.LEVEL_DECLINE}


def _payment_fields(amount, currency, receipt_ref):
    return {'amount': str(amount) if amount else None, 'currency': currency or 'GHS', 'receiptRef': receipt_ref}


def grant_access(student_id, actor, months=None, expires_at=None, amount=None, currency='GHS',
                 receipt_ref='', note='', access_level=None, client=None):
    """Give active access now, or reactivate. No months and no expiry means lifetime."""
    client = client or InnerspaceClient()
    student, result = client.grant(student_id, actor, accessLevel=access_level, months=months,
                                   expiresAt=expires_at.isoformat() if expires_at else None,
                                   **_payment_fields(amount, currency, receipt_ref))
    action = AccessGrantLog.Action.REACTIVATE if result['action'] == 'reactivate' else AccessGrantLog.Action.GRANT
    entry = _log(student, action, actor, result, amount, currency, receipt_ref, note)
    return student, entry


def extend_access(student_id, actor, months=None, expires_at=None, amount=None, currency='GHS',
                  receipt_ref='', note='', access_level=None, client=None):
    """Push the expiry out. Months count from the current expiry while it is still running."""
    client = client or InnerspaceClient()
    student, result = client.extend(student_id, actor, accessLevel=access_level, months=months,
                                    expiresAt=expires_at.isoformat() if expires_at else None,
                                    **_payment_fields(amount, currency, receipt_ref))
    entry = _log(student, AccessGrantLog.Action.EXTEND, actor, result, amount, currency, receipt_ref, note)
    return student, entry


def revoke_access(student_id, actor, note='', client=None):
    """Cancel a membership. Takes effect at the student's next sign-in, not immediately."""
    client = client or InnerspaceClient()
    student, result = client.revoke(student_id, actor, note=note)
    return student, _log(student, AccessGrantLog.Action.REVOKE, actor, result, note=note)


def set_access_level(student_id, actor, access_level, note='', client=None):
    """Move a student to a level directly — the only way to lower one."""
    client = client or InnerspaceClient()
    student, result = client.set_level(student_id, actor, access_level, note=note)
    if result.get('previousLevel') == student.access_level:
        return student, None
    return student, _log(student, AccessGrantLog.Action.LEVEL_GRANT, actor, result, note=note)


def decide_access_request(request_id, actor, approve, note='', client=None):
    """Approve (raise their level) or decline a student's request."""
    client = client or InnerspaceClient()
    access_request, previous_level = client.decide(request_id, actor, approve, note=note)
    action = AccessGrantLog.Action.LEVEL_GRANT if approve else AccessGrantLog.Action.LEVEL_DECLINE
    _log(access_request.student, action, actor, {'previousLevel': previous_level}, note=note)
    return access_request
