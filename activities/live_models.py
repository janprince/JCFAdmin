"""
Live streaming for an Activity: the stream itself, its replay, moderated
chat, reactions and viewer sessions.

A LiveSession hangs off an existing Activity, so scheduling, audience and
reminders are the ones already built rather than a parallel calendar.

The playback URL is authored by staff and can come from any HLS source
(Mux, Cloudflare Stream, a YouTube Live HLS endpoint, …) — no streaming
vendor is baked in.
"""
from datetime import timedelta

from django.db import models
from django.utils import timezone

# How close to start time the join window opens.
JOIN_WINDOW = timedelta(minutes=15)
STARTING_SOON = timedelta(minutes=60)


class LiveSession(models.Model):
    class PlaybackType(models.TextChoices):
        HLS = 'hls', 'HLS'
        DASH = 'dash', 'DASH'
        PROGRESSIVE = 'progressive', 'Progressive MP4'

    class ReplayStatus(models.TextChoices):
        NONE = 'none', 'No replay'
        PROCESSING = 'processing', 'Processing'
        AVAILABLE = 'available', 'Available'

    class AccessTier(models.TextChoices):
        # Two tiers; the old MEMBERS value migrated to STUDENTS.
        PUBLIC = 'public', 'Public'
        STUDENTS = 'students', 'Signed-in students only'

    activity = models.OneToOneField(
        'activities.Activity', on_delete=models.CASCADE,
        related_name='live_session')

    facilitator = models.ForeignKey(
        'staff_mgmt.Worker', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='live_sessions')
    facilitator_name = models.CharField(
        max_length=255, blank=True,
        help_text='Used when the facilitator is not JCF staff.')
    facilitator_role = models.CharField(max_length=255, blank=True)
    facilitator_portrait = models.ImageField(
        upload_to='live/facilitators/', blank=True,
        help_text='An approved portrait. Without one the app shows initials.')

    poster = models.ImageField(upload_to='live/posters/', blank=True)
    full_description = models.TextField(blank=True)
    language = models.CharField(max_length=40, blank=True, default='English')
    category = models.CharField(max_length=80, blank=True)

    # --- stream ---
    playback_url = models.URLField(
        blank=True, help_text='HTTPS HLS (or DASH) playback URL.')
    playback_type = models.CharField(
        max_length=12, choices=PlaybackType.choices, default=PlaybackType.HLS)
    captions_url = models.URLField(blank=True, help_text='WebVTT track.')
    dvr_enabled = models.BooleanField(
        default=False, help_text='Allow rewinding within the live window.')
    low_latency = models.BooleanField(default=False)

    # --- replay ---
    replay_url = models.URLField(blank=True)
    replay_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    replay_status = models.CharField(
        max_length=12, choices=ReplayStatus.choices, default=ReplayStatus.NONE)
    replay_available_until = models.DateTimeField(null=True, blank=True)

    # --- chat ---
    chat_enabled = models.BooleanField(default=True)
    chat_visible_to_guests = models.BooleanField(default=True)
    chat_requires_auth_to_post = models.BooleanField(default=True)
    slow_mode_seconds = models.PositiveSmallIntegerField(default=0)
    max_message_length = models.PositiveSmallIntegerField(default=300)

    # --- access & state ---
    access_tier = models.CharField(
        max_length=10, choices=AccessTier.choices, default=AccessTier.PUBLIC)
    cancelled = models.BooleanField(default=False)
    rescheduled_note = models.CharField(max_length=255, blank=True)
    viewer_count_visible = models.BooleanField(default=True)
    sharing_allowed = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def ends_at(self):
        return self.activity.starts_at + timedelta(
            minutes=self.activity.duration_minutes)

    def status(self, now=None):
        """Server-authoritative state. The app may show a provisional value
        from timestamps but always reconciles with this."""
        now = now or timezone.now()
        if self.cancelled:
            return 'cancelled'
        if self.rescheduled_note:
            return 'rescheduled'
        starts = self.activity.starts_at
        if now < starts:
            if starts - now <= STARTING_SOON:
                return 'starting_soon'
            return 'scheduled'
        if now < self.ends_at:
            return 'live' if self.playback_url else 'unavailable'
        if self.replay_status == self.ReplayStatus.AVAILABLE and self.replay_url:
            if (self.replay_available_until is None
                    or self.replay_available_until > now):
                return 'replay_available'
        if self.replay_status == self.ReplayStatus.PROCESSING:
            return 'replay_processing'
        return 'ended'

    def join_allowed(self, now=None):
        """The stream URL is withheld until the window opens and while it
        is genuinely running."""
        now = now or timezone.now()
        if self.cancelled or not self.playback_url:
            return False
        return (self.activity.starts_at - now <= JOIN_WINDOW
                and now < self.ends_at)

    def allows(self, contact):
        if self.access_tier == self.AccessTier.PUBLIC:
            return True
        # Either flag means an approved contact; `is_member` is a CRM
        # marker, not an app tier. See mobile_api/tiers.py.
        return bool(contact is not None and contact.is_active
                    and (contact.is_student or contact.is_member))

    def live_viewer_count(self, now=None):
        now = now or timezone.now()
        return self.viewer_sessions.filter(
            last_seen_at__gte=now - timedelta(minutes=2)).count()

    def __str__(self):
        return f'Live: {self.activity.title}'


class LiveChatMessage(models.Model):
    """One chat message. Sanitised and rate-limited server-side; the app's
    display rules are presentation only, never enforcement."""

    class Role(models.TextChoices):
        PARTICIPANT = 'participant', 'Participant'
        FACILITATOR = 'facilitator', 'Facilitator'
        MODERATOR = 'moderator', 'Moderator'
        SYSTEM = 'system', 'System'

    session = models.ForeignKey(
        LiveSession, on_delete=models.CASCADE, related_name='chat_messages')
    contact = models.ForeignKey(
        'members.Contact', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='live_chat_messages')
    display_name = models.CharField(max_length=120)
    role = models.CharField(
        max_length=12, choices=Role.choices, default=Role.PARTICIPANT)
    text = models.TextField()
    pinned = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    reported_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [models.Index(fields=['session', 'id'])]

    def __str__(self):
        return f'{self.display_name}: {self.text[:30]}'


class LiveChatBlock(models.Model):
    """One member has blocked another's messages from their own view."""

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='live_chat_blocks')
    blocked = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='live_chat_blocked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'blocked'], name='uniq_live_chat_block'),
        ]


class LiveChatMute(models.Model):
    """A moderator has muted someone for a session."""

    session = models.ForeignKey(
        LiveSession, on_delete=models.CASCADE, related_name='mutes')
    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='live_chat_mutes')
    until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def active(self, now=None):
        now = now or timezone.now()
        return self.until is None or self.until > now


class LiveReaction(models.Model):
    """Aggregated appreciation, not a chat message."""

    class Kind(models.TextChoices):
        APPRECIATE = 'appreciate', 'Appreciation'
        THANKS = 'thanks', 'Thank you'
        INSIGHT = 'insight', 'Insightful'

    session = models.ForeignKey(
        LiveSession, on_delete=models.CASCADE, related_name='reactions')
    contact = models.ForeignKey(
        'members.Contact', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='live_reactions')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)


class LiveViewerSession(models.Model):
    """A heartbeat row, so concurrent viewers can be counted without
    exposing anyone's identity to other viewers."""

    session = models.ForeignKey(
        LiveSession, on_delete=models.CASCADE, related_name='viewer_sessions')
    key = models.CharField(max_length=64, db_index=True)
    contact = models.ForeignKey(
        'members.Contact', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='live_viewer_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'key'], name='uniq_live_viewer_session'),
        ]


class LiveSave(models.Model):
    """A member saved the session or its replay to their library."""

    session = models.ForeignKey(
        LiveSession, on_delete=models.CASCADE, related_name='saves')
    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='live_saves')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'contact'], name='uniq_live_save'),
        ]
