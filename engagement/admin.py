from django.contrib import admin

from .models import Announcement, DeviceToken, Notification
from .push import broadcast_announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'audience', 'is_published', 'pinned', 'created_at')
    list_filter = ('audience', 'is_published', 'pinned')
    search_fields = ('title', 'body')
    actions = ['send_push_action']

    @admin.action(description='Broadcast push for selected announcements')
    def send_push_action(self, request, queryset):
        total = sum(broadcast_announcement(a) for a in queryset.filter(is_published=True))
        self.message_user(request, f'Push targeted {total} device(s).')


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ('platform', 'contact', 'is_active', 'last_seen_at')
    list_filter = ('platform', 'is_active')
    search_fields = ('token', 'contact__full_name')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'contact', 'read_at', 'created_at')
    list_filter = ('read_at',)
    search_fields = ('title', 'contact__full_name')
