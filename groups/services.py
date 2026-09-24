"""Decision logic for group join requests, shared by dashboard views (and tests)."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from engagement.models import Notification

from .models import GroupMembership


@transaction.atomic
def approve_request(membership, staff_user):
    if membership.status == GroupMembership.Status.APPROVED:
        return membership
    group = membership.group
    if group.is_full:
        raise ValidationError(f'"{group.name}" is full ({group.capacity} members).')

    membership.status = GroupMembership.Status.APPROVED
    membership.decided_at = timezone.now()
    membership.decided_by = staff_user
    membership.save(update_fields=['status', 'decided_at', 'decided_by'])

    Notification.objects.create(
        contact=membership.contact,
        title='Group request approved',
        body=f'You are now a member of "{group.name}".',
        data={'type': 'group', 'group_id': group.id},
    )
    return membership


@transaction.atomic
def decline_request(membership, staff_user):
    if membership.status == GroupMembership.Status.DECLINED:
        return membership
    membership.status = GroupMembership.Status.DECLINED
    membership.decided_at = timezone.now()
    membership.decided_by = staff_user
    membership.save(update_fields=['status', 'decided_at', 'decided_by'])

    Notification.objects.create(
        contact=membership.contact,
        title='Group request declined',
        body=f'Your request to join "{membership.group.name}" was not approved.',
        data={'type': 'group', 'group_id': membership.group_id},
    )
    return membership
