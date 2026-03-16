from django import forms
from .models import (
    GalleryItem, VolunteerOpportunity, Testimonial, TeamMember, ImpactStat,
)


class GalleryItemForm(forms.ModelForm):
    class Meta:
        model = GalleryItem
        fields = ['title', 'description', 'image', 'thumbnail', 'video_url',
                  'type', 'category', 'date', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'thumbnail': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'video_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://youtube.com/...'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class VolunteerOpportunityForm(forms.ModelForm):
    skills_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 2,
            'placeholder': 'One skill per line',
        }),
        help_text='Enter one skill per line.',
    )

    class Meta:
        model = VolunteerOpportunity
        fields = ['title', 'description', 'location', 'commitment', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opportunity Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Location'}),
            'commitment': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2 hours per week'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.skills:
            self.fields['skills_text'].initial = '\n'.join(self.instance.skills)

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw = self.cleaned_data.get('skills_text', '')
        instance.skills = [s.strip() for s in raw.splitlines() if s.strip()]
        if commit:
            instance.save()
        return instance


class TestimonialForm(forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ['name', 'role', 'avatar', 'quote', 'is_published', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Community Member'}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'quote': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Testimonial quote'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        }


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ['name', 'role', 'bio', 'image', 'order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Role / Title'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Short biography'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ImpactStatForm(forms.ModelForm):
    class Meta:
        model = ImpactStat
        fields = ['label', 'value', 'prefix', 'suffix', 'order']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Lives Transformed'}),
            'value': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'prefix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. $'}),
            'suffix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. +'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        }
