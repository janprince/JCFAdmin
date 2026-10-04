from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.timesince import timesince
from phonenumber_field.modelfields import PhoneNumberField

from members.models import Contact

# Least privileged first: when a unit allows several portal roles, the first
# one it allows is the one suggested for a new account.
ROLE_ORDER = ['media_operations', 'secretary', 'administrator', 'admin']


class ServiceUnit(models.Model):
    """A team within the Foundation Service Team, e.g. Media & Communications.

    `portal_roles` lists the portal roles a member of this unit may be given.
    It is a guardrail on account management, not a grant: permissions still
    come from the role alone (accounts/access.py). An empty list means the
    unit's work happens outside the portal.
    """
    class Icon(models.TextChoices):
        MEGAPHONE = 'megaphone', 'Megaphone'
        DESKTOP = 'desktop', 'Computer'
        BRIEFCASE = 'briefcase', 'Briefcase'
        PLANT = 'plant', 'Plant'
        HAND_HEART = 'hand-heart', 'Hand and heart'
        BOWL = 'bowl-food', 'Kitchen'
        MUSIC = 'music-notes', 'Music'
        BROOM = 'broom', 'Upkeep'
        CAR = 'car', 'Transport'
        FIRST_AID = 'first-aid', 'Care'
        BOOK = 'book-open-text', 'Teaching'
        USERS = 'users-three', 'People'

    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=255, blank=True, help_text='One line on what this unit looks after.')
    icon = models.CharField(max_length=30, choices=Icon.choices, default=Icon.USERS)
    lead = models.ForeignKey('Worker', null=True, blank=True, on_delete=models.SET_NULL, related_name='units_led')
    portal_roles = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def portal_role_labels(self):
        from accounts.models import Profile
        labels = dict(Profile.Role.choices)
        return [labels[role] for role in ROLE_ORDER if role in self.portal_roles]


class Worker(models.Model):
    """A member of the Foundation Service Team. Kept as `Worker` for the portal account link."""
    class ServiceType(models.TextChoices):
        FULL_TIME = 'full_time', 'Full-time'
        PART_TIME = 'part_time', 'Part-time'
        VOLUNTEER = 'volunteer', 'Volunteer'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ON_LEAVE = 'on_leave', 'On leave'
        INACTIVE = 'inactive', 'Inactive'

    contact = models.OneToOneField(Contact, on_delete=models.CASCADE, related_name='worker')
    title = models.CharField('Service role', max_length=255, blank=True)
    service_type = models.CharField(max_length=20, choices=ServiceType.choices, default=ServiceType.VOLUNTEER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    unit = models.ForeignKey(ServiceUnit, null=True, blank=True, on_delete=models.PROTECT, related_name='members')
    other_units = models.ManyToManyField(ServiceUnit, blank=True, related_name='supporting_members')
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    duties = models.TextField(blank=True)
    availability = models.CharField(max_length=255, blank=True)
    skills = models.CharField(max_length=255, blank=True)
    allowance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    allowance_currency = models.CharField(max_length=3, default='GHS')
    emergency_name = models.CharField(max_length=255, blank=True)
    emergency_phone = PhoneNumberField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'service member'

    def __str__(self):
        return self.contact.full_name

    @property
    def is_serving(self):
        return self.status != self.Status.INACTIVE

    @property
    def receives_allowance(self):
        return bool(self.allowance)

    def all_units(self):
        """Main unit first, then the others by name. Uses prefetched data when present."""
        others = sorted((u for u in self.other_units.all() if u.pk != self.unit_id), key=lambda u: u.name)
        return ([self.unit] if self.unit else []) + others

    def length_of_service(self):
        if not self.started_on:
            return ''
        end = self.ended_on if self.status == self.Status.INACTIVE and self.ended_on else timezone.localdate()
        if end <= self.started_on:
            return 'Just started'
        return timesince(self.started_on, end, depth=2)

    def allowed_portal_roles(self):
        """Roles this person's service units allow, least privileged first.

        None when they belong to no unit: older records predate units, and
        there is nothing to check them against.
        """
        units = self.all_units()
        if not units:
            return None
        allowed = {role for unit in units for role in unit.portal_roles}
        return [role for role in ROLE_ORDER if role in allowed]

    def access_concerns(self):
        """Why this person's portal account needs a second look, if it does."""
        profile = getattr(self, 'portal_profile', None)
        if not profile or not profile.user.is_active or profile.user.is_superuser:
            return []
        concerns = []
        if self.status == self.Status.INACTIVE:
            concerns.append('Their service has ended but they can still sign in to the portal.')
        allowed = self.allowed_portal_roles()
        if allowed is not None and profile.role not in allowed:
            concerns.append(f'Their portal role ({profile.get_role_display()}) is not one their service units allow.')
        return concerns


class ServiceEntry(models.Model):
    """One moment in a service member's journey: a change, a milestone, a word of thanks."""
    class Kind(models.TextChoices):
        CHANGE = 'change', 'Change'
        MILESTONE = 'milestone', 'Milestone'
        APPRECIATION = 'appreciation', 'Appreciation'
        CHECK_IN = 'check_in', 'Check-in'
        TRAINING = 'training', 'Training or retreat'
        NOTE = 'note', 'Note'

    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='journey')
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.NOTE)
    occurred_on = models.DateField(default=timezone.localdate)
    text = models.TextField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_on', '-created_at', '-pk']
        verbose_name_plural = 'service entries'

    def __str__(self):
        return f'{self.get_kind_display()} for {self.worker}'

    @property
    def is_automatic(self):
        return self.kind == self.Kind.CHANGE


class Representative(models.Model):
    contact = models.OneToOneField(Contact, on_delete=models.CASCADE, related_name='representative')
    country = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.contact.full_name}"
