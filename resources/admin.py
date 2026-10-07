from django.contrib import admin
from .models import DigitalResource


@admin.register(DigitalResource)
class DigitalResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'url', 'category', 'audience', 'language', 'is_active')
    list_filter = ('category', 'audience', 'is_active')
    search_fields = ('title', 'url', 'description')
