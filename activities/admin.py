from django.contrib import admin

from .models import (Activity, ActivityRegistration, ActivityReminder,
                     ActivitySave)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['title', 'activity_type', 'activity_format', 'starts_at',
                    'venue', 'audience', 'registration_required',
                    'is_featured', 'cancelled', 'is_active']
    list_filter = ['activity_type', 'activity_format', 'kind', 'audience',
                   'registration_required', 'is_featured', 'cancelled',
                   'is_active']
    search_fields = ['title', 'description', 'venue', 'city',
                     'facilitator_name']
    raw_id_fields = ['facilitator']
    date_hierarchy = 'starts_at'
    fieldsets = [
        (None, {'fields': [
            'title', 'description', 'kind', 'activity_type', 'audience',
            'is_active']}),
        ('When', {'fields': [
            'starts_at', 'duration_minutes', 'all_day']}),
        ('Where', {'fields': [
            'activity_format', 'venue', 'city', 'country',
            'online_platform']}),
        ('Who', {'fields': [
            'facilitator', 'facilitator_name', 'language']}),
        ('Artwork', {'fields': ['image', 'image_key']}),
        ('Registration', {'fields': [
            'registration_required', 'capacity', 'registration_opens_at',
            'registration_closes_at', 'waitlist_enabled', 'fee_amount',
            'fee_currency', 'external_registration_url']}),
        ('Feed', {'fields': [
            'is_featured', 'featured_blurb', 'cancelled',
            'rescheduled_note']}),
    ]


@admin.register(ActivityReminder)
class ActivityReminderAdmin(admin.ModelAdmin):
    list_display = ['contact', 'activity', 'program', 'created_at']
    raw_id_fields = ['contact']


@admin.register(ActivityRegistration)
class ActivityRegistrationAdmin(admin.ModelAdmin):
    list_display = ['contact', 'activity', 'status', 'created_at']
    list_filter = ['status']
    raw_id_fields = ['contact', 'activity']


@admin.register(ActivitySave)
class ActivitySaveAdmin(admin.ModelAdmin):
    list_display = ['contact', 'activity', 'created_at']
    raw_id_fields = ['contact', 'activity']


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
