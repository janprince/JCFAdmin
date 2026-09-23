import uuid
from django import forms
from django.contrib.auth.forms import SetPasswordForm, PasswordChangeForm
from django.contrib.auth.password_validation import validate_password, password_validators_help_text_html
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import User, Profile
from staff_mgmt.models import Worker


def style_fields(form):
    for field in form.fields.values():
        field.widget.attrs['class'] = ('form-check-input' if isinstance(field.widget, forms.CheckboxInput)
                                      else 'form-select' if isinstance(field.widget, forms.Select) else 'form-control')
        if isinstance(field.widget, forms.PasswordInput):
            field.widget.attrs['autocomplete'] = 'new-password'


class PortalUserForm(forms.ModelForm):
    role = forms.ChoiceField(choices=Profile.Role.choices, label='Portal role')
    worker = forms.ModelChoiceField(queryset=Worker.objects.none(), required=False, label='Staff record (optional)',
                                   help_text='Link an existing staff record. A job title does not grant portal permissions.')

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'role', 'worker']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['email'].help_text = 'They will use this email address to sign in.'
        workers = Worker.objects.select_related('contact')
        if self.instance.pk:
            profile = getattr(self.instance, 'profile', None)
            self.fields['role'].initial = profile.role if profile else ''
            self.fields['worker'].initial = profile.worker_id if profile else None
            workers = workers.filter(Q(portal_profile__isnull=True) | Q(portal_profile__user=self.instance))
        else:
            self.fields['role'].initial = Profile.Role.SECRETARY
            workers = workers.filter(portal_profile__isnull=True)
        self.fields['worker'].queryset = workers.order_by('contact__full_name')
        self.fields['worker'].empty_label = 'No linked staff record'
        style_fields(self)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('An account already uses this email address. Edit that account instead.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.pk:
            user.username = 'portal_' + uuid.uuid4().hex
        if commit:
            user.save()
            Profile.objects.update_or_create(user=user, defaults={'role': self.cleaned_data['role'], 'worker': self.cleaned_data['worker']})
        return user


class PortalUserCreateForm(PortalUserForm):
    password1 = forms.CharField(label='Initial password', strip=False, widget=forms.PasswordInput,
                               help_text=password_validators_help_text_html())
    password2 = forms.CharField(label='Confirm initial password', strip=False, widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get('password1') != data.get('password2'):
            self.add_error('password2', 'The passwords do not match.')
        return data

    def _post_clean(self):
        super()._post_clean()
        if self.cleaned_data.get('password1'):
            try:
                validate_password(self.cleaned_data['password1'], self.instance)
            except ValidationError as error:
                self.add_error('password1', error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.must_change_password = True
        if commit:
            user.save()
            Profile.objects.update_or_create(user=user, defaults={'role': self.cleaned_data['role'], 'worker': self.cleaned_data['worker']})
        return user


class InitialPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'New initial password'
        self.fields['new_password2'].label = 'Confirm initial password'
        style_fields(self)


class OwnPasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
        self.fields['old_password'].widget.attrs['autocomplete'] = 'current-password'

    def clean_new_password1(self):
        value = self.cleaned_data['new_password1']
        if self.user.check_password(value):
            raise forms.ValidationError('Choose a different password from your current password.')
        return value
