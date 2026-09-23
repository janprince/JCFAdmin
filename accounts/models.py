from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class User(AbstractUser):
    email = models.EmailField(unique=True)
    must_change_password = models.BooleanField(default=False)
    access_version = models.PositiveIntegerField(default=0)

    def _get_session_auth_hash(self, secret=None):
        # Preserve existing session hashes until an access change requires revocation.
        base_hash = super()._get_session_auth_hash(secret=secret)
        if not self.access_version:
            return base_hash
        from django.utils.crypto import salted_hmac
        return salted_hmac('accounts.User.access_version',
                           f'{base_hash}:{self.access_version}', secret=secret,
                           algorithm='sha256').hexdigest()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email


class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        ADMINISTRATOR = 'administrator', 'Administrator'
        SECRETARY = 'secretary', 'Secretary'
        MEDIA_OPS = 'media_operations', 'Media Operations'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    worker = models.OneToOneField('staff_mgmt.Worker', null=True, blank=True, on_delete=models.SET_NULL, related_name='portal_profile')
    avatar = models.ImageField(upload_to='profile_pics/', blank=True)
    phone = PhoneNumberField(blank=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}"


class PortalAccessEvent(models.Model):
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='portal_actions')
    target = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='access_events')
    action = models.CharField(max_length=40)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
