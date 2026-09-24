from django import forms
from django.db.models import Q

from members.models import Contact

from .models import Announcement, DailyInspiration


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'body', 'audience', 'image', 'is_published', 'pinned']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'audience': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class NotificationComposeForm(forms.Form):
    """Compose an in-app notification for the mobile inbox."""

    AUDIENCE_CHOICES = [
        ('members', 'All members & students'),
        ('students', 'Students only'),
        ('single', 'One person (by email or phone)'),
    ]

    audience = forms.ChoiceField(
        choices=AUDIENCE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    recipient = forms.CharField(
        required=False,
        help_text='Email or phone — only for "One person".',
        widget=forms.TextInput(attrs={'class': 'form-control',
                                      'placeholder': 'member@example.com or +233…'}),
    )
    title = forms.CharField(
        max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    body = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('audience') == 'single':
            identifier = (cleaned.get('recipient') or '').strip()
            if not identifier:
                raise forms.ValidationError("Enter the recipient's email or phone.")
            contact = (Contact.objects.filter(email__iexact=identifier).first()
                       or Contact.objects.filter(phone=identifier).first())
            if contact is None:
                raise forms.ValidationError('No contact found with that email/phone.')
            cleaned['contact'] = contact
        return cleaned

    def recipients(self):
        """The Contacts this notification goes to."""
        audience = self.cleaned_data['audience']
        if audience == 'single':
            return [self.cleaned_data['contact']]
        qs = Contact.objects.filter(is_active=True)
        if audience == 'students':
            return list(qs.filter(is_student=True))
        return list(qs.filter(Q(is_member=True) | Q(is_student=True)))


class DailyInspirationForm(forms.ModelForm):
    class Meta:
        model = DailyInspiration
        fields = ['date', 'quote', 'author', 'reflection', 'related_teaching', 'is_published']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'quote': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'reflection': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'related_teaching': forms.Select(attrs={'class': 'form-select'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
