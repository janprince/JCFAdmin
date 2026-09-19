"""
Groups: admin-created member/student groups with an approval-gated join flow.

Staff create groups in the dashboard; members/students request to join from
the app; a request only becomes membership once staff approve it.
"""
from django.conf import settings
from django.db import models


class Group(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    centre = models.ForeignKey(
        'centres.Centre', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='groups', help_text='Optional home centre for the group.',
    )
    capacity = models.PositiveIntegerField(
        null=True, blank=True, help_text='Optional cap on approved members.',
    )
    is_active = models.BooleanField(
        default=True, help_text='Inactive groups are hidden from the app.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='groups_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.memberships.filter(status=GroupMembership.Status.APPROVED).count()

    @property
    def pending_count(self):
        return self.memberships.filter(status=GroupMembership.Status.PENDING).count()

    @property
    def is_full(self):
        return self.capacity is not None and self.member_count >= self.capacity


class GroupMembership(models.Model):
    """A Contact's relationship to a Group — a join request until approved."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending approval'
        APPROVED = 'approved', 'Approved'
        DECLINED = 'declined', 'Declined'

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE, related_name='group_memberships'
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    message = models.CharField(
        max_length=255, blank=True, help_text='Optional note from the requester.',
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='group_decisions',
    )

    class Meta:
        ordering = ['-requested_at']
        constraints = [
            models.UniqueConstraint(fields=['group', 'contact'], name='unique_group_contact'),
        ]

    def __str__(self):
        return f'{self.contact.full_name} -> {self.group.name} ({self.status})'
