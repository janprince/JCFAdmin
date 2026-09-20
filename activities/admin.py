from django.contrib import admin

from .models import Activity, ActivityReminder


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['title', 'kind', 'starts_at', 'venue', 'audience', 'is_active']
    list_filter = ['kind', 'audience', 'is_active']


@admin.register(ActivityReminder)
class ActivityReminderAdmin(admin.ModelAdmin):
    list_display = ['contact', 'activity', 'program', 'created_at']
    raw_id_fields = ['contact']
