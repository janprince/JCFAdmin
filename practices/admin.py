from django.contrib import admin

from .models import Practice, PracticeLog


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'minutes', 'audience', 'is_active']
    list_filter = ['category', 'audience', 'is_active']


@admin.register(PracticeLog)
class PracticeLogAdmin(admin.ModelAdmin):
    list_display = ['contact', 'practice', 'date', 'minutes']
    list_filter = ['date']
    raw_id_fields = ['contact']
