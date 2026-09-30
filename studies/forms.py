from django import forms

from .models import Enrolment, Mentorship, Milestone, PracticeAssignment

_dt = {'class': 'form-control', 'type': 'datetime-local'}


class EnrolmentForm(forms.ModelForm):
    class Meta:
        model = Enrolment
        fields = ['contact', 'program', 'series', 'cohort', 'status',
                  'is_primary', 'access_expires_at']
        widgets = {
            'contact': forms.Select(attrs={'class': 'form-select'}),
            'program': forms.Select(attrs={'class': 'form-select'}),
            'series': forms.Select(attrs={'class': 'form-select'}),
            'cohort': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'access_expires_at': forms.DateTimeInput(
                attrs=_dt, format='%Y-%m-%dT%H:%M'),
        }


class PracticeAssignmentForm(forms.ModelForm):
    class Meta:
        model = PracticeAssignment
        fields = ['contact', 'practice', 'enrolment', 'due_at', 'required',
                  'excused']
        widgets = {
            'contact': forms.Select(attrs={'class': 'form-select'}),
            'practice': forms.Select(attrs={'class': 'form-select'}),
            'enrolment': forms.Select(attrs={'class': 'form-select'}),
            'due_at': forms.DateTimeInput(attrs=_dt, format='%Y-%m-%dT%H:%M'),
            'required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'excused': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ['program', 'title', 'description', 'required_progress',
                  'order', 'is_active']
        widgets = {
            'program': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'required_progress': forms.NumberInput(
                attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MentorshipForm(forms.ModelForm):
    class Meta:
        model = Mentorship
        fields = ['student', 'mentor', 'availability', 'next_check_in_at',
                  'messaging_enabled', 'booking_enabled', 'is_active']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'mentor': forms.Select(attrs={'class': 'form-select'}),
            'availability': forms.TextInput(attrs={'class': 'form-control'}),
            'next_check_in_at': forms.DateTimeInput(
                attrs=_dt, format='%Y-%m-%dT%H:%M'),
            'messaging_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'booking_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
