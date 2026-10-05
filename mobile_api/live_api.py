"""Live Now: event detail, viewer sessions, moderated chat and reactions.

Public sessions play without an account. The playback URL is withheld
until the join window opens and is never part of a share link.

Chat transport note: the platform has no WebSocket layer yet (no Channels,
ASGI or Redis), so the app polls `chat/` with a cursor. The contract is
deliberately transport-shaped — a client sends and reads messages by id —
so a Channels consumer can replace polling without changing the app's
chat UI.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.live_models import (LiveChatBlock, LiveChatMessage,
                                    LiveChatMute, LiveReaction, LiveSave,
                                    LiveSession, LiveViewerSession)
from activities.models import Activity, ActivityReminder

from .authentication import IsSignedIn, MobileTokenAuthentication

CHAT_PAGE = 50
# A floor on posting, independent of any per-session slow mode.
MIN_POST_INTERVAL = timedelta(seconds=2)
REACTION_INTERVAL = timedelta(seconds=3)


def _session(event_id):
    return (
        LiveSession.objects
        .select_related('activity', 'facilitator__contact')
        .filter(activity_id=event_id, activity__is_active=True)
        .first()
    )


def _contact(request):
    token = getattr(request, 'auth', None)
    return token.contact if token is not None else None


def _canonical_url(session):
    base = settings.PUBLIC_SITE_URL.rstrip('/')
    return f'{base}/live/{session.activity_id}'


def _facilitator_json(session):
    worker = session.facilitator
    name = session.facilitator_name or (
        worker.contact.full_name if worker else '')
    if not name:
        return None
    role = session.facilitator_role or (worker.role if worker else '')
    # Only an approved portrait is sent. Without one the app shows initials
    # rather than attaching a stock face to a real person's name.
    return {
        'id': worker.id if worker else None,
        'display_name': name,
        'role': role,
        'avatar_url': (session.facilitator_portrait.url
                       if session.facilitator_portrait else ''),
        'verified': worker is not None,
    }


def _access_json(session, contact, now):
    allowed = session.allows(contact)
    return {
        'allowed': allowed,
        'required_tier': session.access_tier,
        'sign_in_required': not allowed and contact is None,
        'restriction_reason': '' if allowed else 'tier',
        'join_window_starts_at': (
            session.activity.starts_at - timedelta(minutes=15)).isoformat(),
        'join_window_ends_at': session.ends_at.isoformat(),
    }


def _message_json(message):
    return {
        'id': message.id,
        'display_name': message.display_name,
        'role': message.role,
        # A deleted message keeps its slot so the list does not jump, but
        # carries no content.
        'text': '' if message.deleted else message.text,
        'deleted': message.deleted,
        'pinned': message.pinned,
        'created_at': message.created_at.isoformat(),
        'contact_id': message.contact_id,
    }


class LiveEventDetailView(APIView):
    """GET /events/<id>/live/ — everything the player needs."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, event_id):
        session = _session(event_id)
        if session is None:
            return Response({'detail': 'Event not found.'}, status=404)

        now = timezone.now()
        contact = _contact(request)
        status = session.status(now)
        access = _access_json(session, contact, now)
        activity = session.activity

        # The stream block is only populated once access is confirmed and
        # the join window is open — never sent early.
        stream = None
        if access['allowed'] and session.join_allowed(now):
            stream = {
                'playback_url': session.playback_url,
                'playback_type': session.playback_type,
                'dvr_enabled': session.dvr_enabled,
                'low_latency': session.low_latency,
                'captions_url': session.captions_url,
                'pip_allowed': True,
            }

        replay = None
        if (access['allowed']
                and status in ('replay_available', 'replay_processing')):
            replay = {
                'playback_url': (session.replay_url
                                 if status == 'replay_available' else ''),
                'duration_seconds': session.replay_duration_seconds,
                'processing_status': session.replay_status,
                'captions_url': session.captions_url,
                'thumbnail_url': (session.poster.url
                                  if session.poster else ''),
                'available_until': (
                    session.replay_available_until.isoformat()
                    if session.replay_available_until else None),
            }

        muted = False
        if contact is not None:
            muted = any(
                m.active(now) for m in
                LiveChatMute.objects.filter(session=session, contact=contact))

        return Response({
            'id': activity.id,
            'title': activity.title,
            'short_description': activity.description,
            'full_description': session.full_description
            or activity.description,
            'poster_url': session.poster.url if session.poster else '',
            'status': status,
            'starts_at': activity.starts_at.isoformat(),
            'ends_at': session.ends_at.isoformat(),
            'timezone': str(timezone.get_current_timezone()),
            'language': session.language,
            'category': session.category or activity.get_kind_display(),
            'venue': activity.venue,
            'viewer_count': session.live_viewer_count(now),
            'viewer_count_visible': session.viewer_count_visible,
            'facilitator': _facilitator_json(session),
            'stream': stream,
            'replay': replay,
            'chat': {
                'enabled': session.chat_enabled,
                'visible_to_guests': session.chat_visible_to_guests,
                'authentication_required_to_post':
                    session.chat_requires_auth_to_post,
                'slow_mode_seconds': session.slow_mode_seconds,
                'max_message_length': session.max_message_length,
                'read_only': muted,
            },
            'access': access,
            'reminder_enabled': contact is not None and
            ActivityReminder.objects.filter(
                contact=contact, activity=activity).exists(),
            'saved': contact is not None and LiveSave.objects.filter(
                session=session, contact=contact).exists(),
            'sharing_allowed': session.sharing_allowed,
            'cancellation_note': session.rescheduled_note,
            # Only ever the canonical page — never the playback URL.
            'canonical_url': _canonical_url(session),
            'updated_at': session.updated_at.isoformat(),
        })


class LiveViewerSessionView(APIView):
    """POST/DELETE /events/<id>/viewer-session/ — heartbeat for the
    concurrent-viewer count. A page open does not count; playback does."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, event_id):
        session = _session(event_id)
        if session is None:
            return Response({'detail': 'Event not found.'}, status=404)
        key = str(request.data.get('key') or '').strip()[:64]
        if not key:
            return Response({'detail': 'key is required.'}, status=400)
        viewer, _created = LiveViewerSession.objects.update_or_create(
            session=session, key=key,
            defaults={'contact': _contact(request)})
        viewer.save(update_fields=['last_seen_at'])
        return Response({'viewer_count': session.live_viewer_count()})

    def delete(self, request, event_id):
        session = _session(event_id)
        if session is None:
            return Response({'detail': 'Event not found.'}, status=404)
        key = str(request.query_params.get('key') or '').strip()[:64]
        LiveViewerSession.objects.filter(session=session, key=key).delete()
        return Response({'viewer_count': session.live_viewer_count()})


class LiveChatView(APIView):
    """GET  /events/<id>/chat/?after=<id> — messages since a cursor.
    POST /events/<id>/chat/ {text}  — post one, members only."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, event_id):
        session = _session(event_id)
        if session is None:
            return Response({'detail': 'Event not found.'}, status=404)
        contact = _contact(request)
        if not session.chat_enabled:
            return Response({'results': [], 'pinned': None, 'enabled': False})
        if contact is None and not session.chat_visible_to_guests:
            return Response(
                {'detail': 'Sign in to view the chat.'}, status=401)

        messages = LiveChatMessage.objects.filter(session=session)
        # A member never sees messages from someone they blocked.
        if contact is not None:
            blocked = LiveChatBlock.objects.filter(
                contact=contact).values_list('blocked_id', flat=True)
            if blocked:
                messages = messages.exclude(contact_id__in=list(blocked))

        after = request.query_params.get('after')
        if after and str(after).isdigit():
            messages = messages.filter(id__gt=int(after))
            rows = list(messages.order_by('id')[:CHAT_PAGE])
        else:
            rows = list(messages.order_by('-id')[:CHAT_PAGE])[::-1]

        pinned = (
            LiveChatMessage.objects
            .filter(session=session, pinned=True, deleted=False)
            .order_by('-id').first()
        )
        return Response({
            'enabled': True,
            'results': [_message_json(m) for m in rows],
            'pinned': _message_json(pinned) if pinned else None,
        })

    def post(self, request, event_id):
        session = _session(event_id)
        if session is None:
            return Response({'detail': 'Event not found.'}, status=404)
        contact = _contact(request)
        if not session.chat_enabled:
            return Response({'detail': 'Chat is closed.'}, status=403)
        if contact is None:
            return Response(
                {'detail': 'Sign in to join the conversation.'}, status=401)
        if not session.allows(contact):
            return Response({'detail': 'Access required.'}, status=403)

        now = timezone.now()
        if any(m.active(now) for m in LiveChatMute.objects.filter(
                session=session, contact=contact)):
            return Response({'detail': 'You are muted.'}, status=403)

        # Tags are stripped server-side; the client's limit is convenience,
        # this is the enforcement.
        text = strip_tags(str(request.data.get('text') or '')).strip()
        if not text:
            return Response({'detail': 'Message is empty.'}, status=400)
        if len(text) > session.max_message_length:
            return Response(
                {'detail': 'Message is too long.'}, status=400)

        interval = max(
            MIN_POST_INTERVAL,
            timedelta(seconds=session.slow_mode_seconds))
        last = (LiveChatMessage.objects
                .filter(session=session, contact=contact)
                .order_by('-id').first())
        if last is not None and now - last.created_at < interval:
            retry = int((interval - (now - last.created_at)).total_seconds())
            return Response(
                {'detail': 'Slow mode is on.', 'retry_after': max(1, retry)},
                status=429)
        # Identical text in a row is a double submission, not a message.
        if last is not None and last.text == text:
            return Response({'detail': 'Duplicate message.'}, status=400)

        role = LiveChatMessage.Role.PARTICIPANT
        if session.facilitator and session.facilitator.contact_id == contact.id:
            role = LiveChatMessage.Role.FACILITATOR
        elif hasattr(contact, 'worker'):
            role = LiveChatMessage.Role.MODERATOR

        message = LiveChatMessage.objects.create(
            session=session, contact=contact,
            display_name=(contact.full_name or '').split(' ')[0] or 'Member',
            role=role, text=text)
        return Response(_message_json(message), status=201)


class LiveChatReportView(APIView):
    """POST /events/<id>/chat/<message_id>/report/ — flag for moderation."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsSignedIn]

    def post(self, request, event_id, message_id):
        message = LiveChatMessage.objects.filter(
            pk=message_id, session__activity_id=event_id).first()
        if message is None:
            return Response({'detail': 'Not found.'}, status=404)
        message.reported_count += 1
        message.save(update_fields=['reported_count'])
        return Response({'reported': True})


class LiveChatBlockView(APIView):
    """POST /events/<id>/chat/block/ {contact_id} — hide someone's
    messages from this member's own view."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsSignedIn]

    def post(self, request, event_id, contact_id):
        if int(contact_id) == request.member.id:
            return Response(
                {'detail': 'You cannot block yourself.'}, status=400)
        LiveChatBlock.objects.get_or_create(
            contact=request.member, blocked_id=contact_id)
        return Response({'blocked': True}, status=201)


class LiveReactionView(APIView):
    """POST /events/<id>/reaction/ {kind} — aggregated, rate-limited."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsSignedIn]

    def post(self, request, event_id):
        session = _session(event_id)
        if session is None:
            return Response({'detail': 'Event not found.'}, status=404)
        kind = str(request.data.get('kind') or '')
        if kind not in LiveReaction.Kind.values:
            return Response({'detail': 'Unknown reaction.'}, status=400)

        now = timezone.now()
        last = (LiveReaction.objects
                .filter(session=session, contact=request.member)
                .order_by('-id').first())
        if last is not None and now - last.created_at < REACTION_INTERVAL:
            return Response({'detail': 'Too fast.'}, status=429)

        LiveReaction.objects.create(
            session=session, contact=request.member, kind=kind)
        counts = {}
        for value in LiveReaction.Kind.values:
            counts[value] = LiveReaction.objects.filter(
                session=session, kind=value).count()
        return Response({'counts': counts}, status=201)


class LiveSaveView(APIView):
    """POST/DELETE /events/<id>/save/ — members only."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsSignedIn]

    def post(self, request, event_id):
        session = _session(event_id)
        if session is None:
            return Response({'detail': 'Event not found.'}, status=404)
        LiveSave.objects.get_or_create(
            session=session, contact=request.member)
        return Response({'saved': True}, status=201)

    def delete(self, request, event_id):
        session = _session(event_id)
        if session is None:
            return Response({'detail': 'Event not found.'}, status=404)
        LiveSave.objects.filter(
            session=session, contact=request.member).delete()
        return Response({'saved': False})
