"""Write the automatic entries in a service member's journey.

Edits that change someone's place in the service team — commitment, units,
status, allowance — are recorded as they happen, so the record shows how a
person's service unfolded and when their support changed, without anyone
having to remember to write it down.
"""
from django.utils import timezone

from .models import ServiceEntry, Worker


def snapshot(worker):
    """The parts of a record whose changes belong in the journey."""
    if not worker.pk:
        return None
    return {
        'title': worker.title,
        'service_type': worker.service_type,
        'status': worker.status,
        'unit': worker.unit,
        'other_units': {u.pk: u for u in worker.other_units.all()},
        'allowance': (worker.allowance, worker.allowance_currency) if worker.allowance else None,
    }


def _money(value):
    amount, currency = value
    return f'{currency} {amount:,.2f}'


def describe(before, worker):
    """Sentences for what changed between `before` and the saved `worker`."""
    after = snapshot(worker)
    lines = []
    if before['status'] != after['status']:
        lines.append({
            Worker.Status.INACTIVE: 'Service ended.',
            Worker.Status.ON_LEAVE: 'Went on leave.',
            Worker.Status.ACTIVE: 'Returned to active service.' if before['status'] == Worker.Status.ON_LEAVE else 'Resumed service.',
        }[after['status']])
    if before['service_type'] != after['service_type']:
        lines.append(f"Commitment changed from {Worker.ServiceType(before['service_type']).label} to {worker.get_service_type_display()}.")
    if before['unit'] != after['unit'] and after['unit']:
        lines.append(f"Main unit changed to {after['unit']}." if before['unit'] else f"Joined {after['unit']}.")
    joined = [u.name for pk, u in after['other_units'].items() if pk not in before['other_units']]
    left = [u.name for pk, u in before['other_units'].items() if pk not in after['other_units']]
    if joined:
        lines.append(f"Began helping {', '.join(sorted(joined))}.")
    if left:
        lines.append(f"Stopped helping {', '.join(sorted(left))}.")
    if before['title'] != after['title'] and after['title']:
        lines.append(f"Service role is now {after['title']}.")
    if before['allowance'] != after['allowance']:
        if not after['allowance']:
            lines.append('Monthly allowance stopped.')
        elif not before['allowance']:
            lines.append(f"Monthly allowance began: {_money(after['allowance'])}.")
        else:
            lines.append(f"Monthly allowance changed from {_money(before['allowance'])} to {_money(after['allowance'])}.")
    return lines


def record_joined(worker, actor):
    parts = [f'Began service as {worker.get_service_type_display().lower()}']
    if worker.unit:
        parts.append(f'in {worker.unit}')
    text = ' '.join(parts) + '.'
    if worker.allowance:
        text += f' Monthly allowance: {_money((worker.allowance, worker.allowance_currency))}.'
    ServiceEntry.objects.create(worker=worker, kind=ServiceEntry.Kind.CHANGE, text=text, recorded_by=actor,
                                occurred_on=worker.started_on or timezone.localdate())


def record_changes(before, worker, actor):
    lines = describe(before, worker)
    if not lines:
        return
    ended = worker.status == Worker.Status.INACTIVE and before['status'] != Worker.Status.INACTIVE
    occurred = worker.ended_on if ended and worker.ended_on else timezone.localdate()
    ServiceEntry.objects.create(worker=worker, kind=ServiceEntry.Kind.CHANGE, text=' '.join(lines),
                                recorded_by=actor, occurred_on=min(occurred, timezone.localdate()))
