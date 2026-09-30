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


from .live_models import (LiveChatMessage, LiveReaction,  # noqa: E402
                          LiveSession, LiveViewerSession)


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ['activity', 'access_tier', 'replay_status',
                    'chat_enabled', 'cancelled']
    list_filter = ['access_tier', 'replay_status', 'chat_enabled', 'cancelled']


@admin.register(LiveChatMessage)
class LiveChatMessageAdmin(admin.ModelAdmin):
    """Moderation queue: staff pin or remove messages here."""

    list_display = ['session', 'display_name', 'role', 'text', 'pinned',
                    'deleted', 'reported_count', 'created_at']
    list_filter = ['role', 'pinned', 'deleted']
    list_editable = ['pinned', 'deleted']
    raw_id_fields = ['contact']


@admin.register(LiveReaction)
class LiveReactionAdmin(admin.ModelAdmin):
    list_display = ['session', 'kind', 'created_at']


@admin.register(LiveViewerSession)
class LiveViewerSessionAdmin(admin.ModelAdmin):
    list_display = ['session', 'key', 'started_at', 'last_seen_at']
