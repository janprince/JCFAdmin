from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import ListView, TemplateView

from accounts.access import areas_for, role_cards
from accounts.forms import PortalUserForm, PortalUserCreateForm, InitialPasswordForm
from accounts.models import User, Profile, PortalAccessEvent
from .models import Worker


@method_decorator(never_cache, name='dispatch')
@method_decorator(sensitive_post_parameters(), name='dispatch')
class AccountManagerMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and 'accounts' not in areas_for(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def locked_actor(request):
    # Serialize access changes, including concurrent administrator demotions.
    users = list(User.objects.select_for_update().order_by('pk'))
    actor = next((user for user in users if user.pk == request.user.pk), None)
    if not actor or 'accounts' not in areas_for(actor):
        raise PermissionDenied
    return actor


def editable_target(pk):
    user = get_object_or_404(User.objects.select_related('profile'), pk=pk)
    if user.is_superuser:
        raise PermissionDenied('System administrators are managed through Django admin.')
    return user


def record(actor, target, action, detail=''):
    PortalAccessEvent.objects.create(actor=actor, target=target, action=action, detail=detail)


class UserListView(AccountManagerMixin, ListView):
    template_name = 'staff/user_list.html'
    context_object_name = 'portal_users'
    paginate_by = 30

    def get_queryset(self):
        qs = User.objects.select_related('profile__worker__contact').order_by('-is_active', 'first_name', 'email')
        query = self.request.GET.get('q', '').strip()
        if query:
            qs = qs.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query))
        role = self.request.GET.get('role')
        if role in Profile.Role.values:
            qs = qs.filter(profile__role=role, is_superuser=False)
        status = self.request.GET.get('status')
        if status in {'active', 'inactive'}:
            qs = qs.filter(is_active=status == 'active')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(search_query=self.request.GET.get('q', ''), role_choices=Profile.Role.choices,
                       active_count=User.objects.filter(is_active=True).count(),
                       inactive_count=User.objects.filter(is_active=False).count())
        return context


class RoleGuideView(AccountManagerMixin, TemplateView):
    template_name = 'staff/role_guide.html'
    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'roles': role_cards()}


class UserCreateView(AccountManagerMixin, View):
    def get(self, request):
        initial = {}
        if request.GET.get('worker', '').isdigit():
            worker = get_object_or_404(Worker.objects.select_related('contact'), pk=request.GET['worker'])
            linked = Profile.objects.filter(worker=worker).first()
            if linked:
                return redirect('staff:user_update', pk=linked.user_id)
            names = worker.contact.full_name.strip().split(' ', 1)
            initial = {'worker': worker.pk, 'first_name': names[0], 'last_name': names[1] if len(names) > 1 else '', 'email': worker.contact.email}
        return self.display(request, PortalUserCreateForm(initial=initial))

    def display(self, request, form):
        return render(request, 'staff/user_form.html', {'form': form, 'roles': role_cards(), 'creating': True})

    def post(self, request):
        form = PortalUserCreateForm(request.POST)
        try:
            with transaction.atomic():
                actor = locked_actor(request)
                if form.is_valid():
                    user = form.save()
                    record(actor, user, 'Account created', f'Role: {user.profile.get_role_display()}')
                    messages.success(request, 'Account created. Share the sign-in email and initial password securely. No email has been sent; they will choose their own password at first sign-in.')
                    return redirect('staff:user_update', pk=user.pk)
        except IntegrityError:
            form.add_error(None, 'The email address or staff record was just assigned to another account. Please review your details.')
        return self.display(request, form)


class UserUpdateView(AccountManagerMixin, View):
    def display(self, request, user, form):
        return render(request, 'staff/user_form.html', {
            'form': form, 'account': user, 'roles': role_cards(),
            'events': user.access_events.select_related('actor')[:12],
            'sign_in_url': request.build_absolute_uri(reverse('login')),
        })

    def get(self, request, pk):
        user = editable_target(pk)
        return self.display(request, user, PortalUserForm(instance=user))

    def post(self, request, pk):
        try:
            with transaction.atomic():
                actor = locked_actor(request)
                user = editable_target(pk)
                old_role = getattr(getattr(user, 'profile', None), 'role', '')
                old_email = user.email
                form = PortalUserForm(request.POST, instance=user)
                if form.is_valid():
                    new_role = form.cleaned_data['role']
                    if actor.pk == user.pk and new_role != old_role:
                        form.add_error('role', 'Ask another Admin to change your role. You cannot remove your own account-management access.')
                    else:
                        if old_role != new_role or old_email != form.cleaned_data['email']:
                            user.access_version += 1
                        user = form.save()
                        record(actor, user, 'Account updated', f"Role: {dict(Profile.Role.choices).get(old_role, 'Unassigned')} → {user.profile.get_role_display()}")
                        messages.success(request, 'Account updated. Changes to role or sign-in email take effect immediately and require a new sign-in.')
                        return redirect('staff:user_update', pk=user.pk)
        except IntegrityError:
            form.add_error(None, 'That email address or staff record is already assigned. Please review your details.')
        return self.display(request, user, form)


class UserStatusView(AccountManagerMixin, View):
    def target(self, request, pk):
        user = editable_target(pk)
        if user.pk == request.user.pk:
            raise PermissionDenied('You cannot deactivate your own account.')
        return user

    def get(self, request, pk, action):
        user = self.target(request, pk)
        return render(request, 'staff/user_status.html', {'account': user, 'activating': action == 'activate'})

    def post(self, request, pk, action):
        with transaction.atomic():
            actor = locked_actor(request)
            user = self.target(request, pk)
            active = action == 'activate'
            if user.is_active != active:
                user.is_active = active
                user.access_version += 1
                user.save(update_fields=['is_active', 'access_version'])
                record(actor, user, 'Access activated' if active else 'Access deactivated')
        messages.success(request, 'Portal access activated.' if active else 'Portal access deactivated. Existing sessions can no longer open the portal.')
        return redirect('staff:user_update', pk=pk)


class UserPasswordView(AccountManagerMixin, View):
    def target(self, request, pk):
        user = editable_target(pk)
        if user.pk == request.user.pk:
            raise PermissionDenied('Use Change password in your account menu to change your own password.')
        return user

    def get(self, request, pk):
        user = self.target(request, pk)
        return render(request, 'staff/user_password.html', {'account': user, 'form': InitialPasswordForm(user)})

    def post(self, request, pk):
        with transaction.atomic():
            actor = locked_actor(request)
            user = self.target(request, pk)
            form = InitialPasswordForm(user, request.POST)
            if form.is_valid():
                user.must_change_password = True
                user.access_version += 1
                form.save()
                record(actor, user, 'Initial password reset')
                messages.success(request, 'Initial password reset. Share it securely; they must choose a new password when they sign in. Existing sessions have been signed out. No email has been sent.')
                return redirect('staff:user_update', pk=pk)
        return render(request, 'staff/user_password.html', {'account': user, 'form': form})
