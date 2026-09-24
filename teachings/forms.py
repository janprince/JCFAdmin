from django import forms

from .models import Teaching, TeachingSeries


class TeachingForm(forms.ModelForm):
    class Meta:
        model = Teaching
        fields = [
            'topic', 'author', 'format', 'language', 'status', 'description',
            'tier', 'series', 'order',
            'media_kind', 'youtube_url', 'media_file', 'thumbnail',
            'duration_seconds',
        ]
        widgets = {
            'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Topic Title'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'format': forms.Select(attrs={'class': 'form-select'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'tier': forms.Select(attrs={'class': 'form-select'}),
            'series': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'media_kind': forms.Select(attrs={'class': 'form-select'}),
            'youtube_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://youtube.com/…'}),
            'media_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'thumbnail': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'duration_seconds': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g. 1800'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Quick-add on the list page posts only the basics; everything else
        # falls back to model defaults here.
        for name in ('tier', 'order', 'media_kind', 'duration_seconds', 'series',
                     'author'):
            self.fields[name].required = False

    def clean_author(self):
        return self.cleaned_data.get('author') or 'Dr. Baffour Jan'

    def clean_tier(self):
        return self.cleaned_data.get('tier') or Teaching.Tier.GENERAL

    def clean_media_kind(self):
        return self.cleaned_data.get('media_kind') or Teaching.MediaKind.VIDEO

    def clean_order(self):
        value = self.cleaned_data.get('order')
        return 0 if value in (None, '') else value



class SeriesForm(forms.ModelForm):
    class Meta:
        model = TeachingSeries
        fields = ['title', 'description', 'cover', 'order', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cover': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
