"""
The one Inner Space table JCF owns: its audit trail.

Students, memberships, payments and access requests belong to drbaffourjan.com
and are read and changed through its office API (client.py). They are no
longer modelled here, and JCF has no connection to that database.

`AccessGrantLog` is a plain model in JCF's own database. Its table is called
`innerspace_accessgrantlog` because Django prefixes tables with the app label —
it does not live in the student platform.
"""

from django.conf import settings
from django.db import models


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
