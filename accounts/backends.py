from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(email__iexact=(username or kwargs.get('email') or '').strip())
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


class PortalRoleBackend(ModelBackend):
    def has_perm(self, user_obj, perm, obj=None):
        from .access import areas_for
        return obj is None and perm == 'innerspace.manage_innerspace_access' and 'innerspace' in areas_for(user_obj)
