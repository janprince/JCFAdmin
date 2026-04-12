from django import forms
from .models import Author, Category, Tag, Post


class PostForm(forms.ModelForm):
    slug = forms.SlugField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'auto-generated-from-title'}))

    class Meta:
        model = Post
        fields = [
            'title', 'slug', 'excerpt', 'content', 'image', 'video_link',
            'author', 'category', 'tags', 'status', 'published_date',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Post title'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Short summary for listing cards'}),
            'content': forms.HiddenInput(),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'video_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://youtube.com/watch?v=...'}),
            'author': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.CheckboxSelectMultiple(),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'published_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['name', 'role', 'avatar', 'bio']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Author name'}),
            'role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Founder & Spiritual Director'}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Short bio'}),
        }


class CategoryForm(forms.ModelForm):
    slug = forms.SlugField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'auto-generated'}))

    class Meta:
        model = Category
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
        }


class TagForm(forms.ModelForm):
    slug = forms.SlugField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'auto-generated'}))

    class Meta:
        model = Tag
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tag name'}),
        }
