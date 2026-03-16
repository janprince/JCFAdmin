from django import forms
from .models import Event, EventCategory


class EventCategoryForm(forms.ModelForm):
    class Meta:
        model = EventCategory
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
        }


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'content', 'date', 'end_date',
            'time', 'location', 'address', 'image', 'category',
            'registration_url', 'is_published',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Short summary for listing cards'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Venue or city name'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full address'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'registration_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'content': forms.HiddenInput(),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
