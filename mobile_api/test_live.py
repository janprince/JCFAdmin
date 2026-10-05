"""Live Now: state machine, access gating, viewer counts and moderation."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from activities.live_models import (LiveChatMessage, LiveChatMute,
                                    LiveReaction, LiveSession,
                                    LiveViewerSession)
from activities.models import Activity
from members.models import Contact
from staff_mgmt.models import Worker

from .models import MobileToken

STREAM = 'https://stream.example.com/live/playlist.m3u8'


def url(event_id, suffix=''):
    return f'/api/mobile/v1/events/{event_id}/{suffix}'


class LiveEventTests(APITestCase):
    def setUp(self):
        self.activity = Activity.objects.create(
            title='Sunday Satsang: Living with Awareness',
            kind='live', audience='public',
            starts_at=timezone.now() - timedelta(minutes=10),
            duration_minutes=90,
            description='A live teaching.')
        self.session = LiveSession.objects.create(
            activity=self.activity, playback_url=STREAM,
            full_description='The full description.',
            facilitator_name='Dr. Baffour Jan',
            facilitator_role='Founder')
        self.member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000071',
            email='ama-live@example.com', is_active=True, is_member=True)

    def _auth(self, contact=None):
        token = MobileToken.issue(contact or self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    # --- status machine ---

    def test_a_running_session_is_live_and_gives_the_stream(self):
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['status'], 'live')
        self.assertEqual(res.data['stream']['playback_url'], STREAM)
        self.assertEqual(res.data['stream']['playback_type'], 'hls')

    def test_a_scheduled_session_withholds_the_stream(self):
        self.activity.starts_at = timezone.now() + timedelta(days=2)
        self.activity.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['status'], 'scheduled')
        # The URL must not be handed out before the window opens.
        self.assertIsNone(res.data['stream'])

    def test_starting_soon_still_withholds_until_the_join_window(self):
        self.activity.starts_at = timezone.now() + timedelta(minutes=40)
        self.activity.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['status'], 'starting_soon')
        self.assertIsNone(res.data['stream'])

        # Inside the 15-minute window it is released.
        self.activity.starts_at = timezone.now() + timedelta(minutes=5)
        self.activity.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertIsNotNone(res.data['stream'])

    def test_an_ended_session_without_replay_is_ended(self):
        self.activity.starts_at = timezone.now() - timedelta(hours=5)
        self.activity.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['status'], 'ended')
        self.assertIsNone(res.data['stream'])
        self.assertIsNone(res.data['replay'])

    def test_replay_processing_then_available(self):
        self.activity.starts_at = timezone.now() - timedelta(hours=5)
        self.activity.save()
        self.session.replay_status = 'processing'
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['status'], 'replay_processing')
        self.assertEqual(res.data['replay']['playback_url'], '')

        self.session.replay_status = 'available'
        self.session.replay_url = 'https://cdn.example.com/replay.m3u8'
        self.session.replay_duration_seconds = 5400
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['status'], 'replay_available')
        self.assertEqual(res.data['replay']['duration_seconds'], 5400)

    def test_cancelled_and_rescheduled_states(self):
        self.session.cancelled = True
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['status'], 'cancelled')
        self.assertIsNone(res.data['stream'])

        self.session.cancelled = False
        self.session.rescheduled_note = 'Moved to Sunday 7pm.'
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['status'], 'rescheduled')

    def test_a_live_session_without_a_url_is_unavailable(self):
        self.session.playback_url = ''
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['status'], 'unavailable')

    # --- access ---

    def test_a_guest_may_watch_a_public_session(self):
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertTrue(res.data['access']['allowed'])
        self.assertIsNotNone(res.data['stream'])

    def test_a_members_only_session_hides_the_stream_from_guests(self):
        self.session.access_tier = 'students'
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertFalse(res.data['access']['allowed'])
        self.assertTrue(res.data['access']['sign_in_required'])
        self.assertIsNone(res.data['stream'])

        res = self.client.get(url(self.activity.id, 'live/'), **self._auth())
        self.assertTrue(res.data['access']['allowed'])
        self.assertIsNotNone(res.data['stream'])

    def test_a_gated_session_admits_a_contact_approved_by_either_flag(self):
        # Previously a members-flagged contact was refused a students-only
        # session. With one signed-in tier they are the same person.
        self.session.access_tier = 'students'
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'), **self._auth())
        self.assertTrue(res.data['access']['allowed'])

    def test_a_gated_session_still_excludes_a_guest(self):
        self.session.access_tier = 'students'
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertFalse(res.data['access']['allowed'])
        self.assertIsNone(res.data['stream'])

    def test_the_share_link_is_the_page_never_the_stream(self):
        res = self.client.get(url(self.activity.id, 'live/'))
        canonical = res.data['canonical_url']
        self.assertTrue(canonical.startswith('https://'))
        self.assertNotIn('m3u8', canonical)

    # --- facilitator ---

    def test_a_facilitator_without_a_portrait_sends_no_image(self):
        res = self.client.get(url(self.activity.id, 'live/'))
        facilitator = res.data['facilitator']
        self.assertEqual(facilitator['display_name'], 'Dr. Baffour Jan')
        # No stock face is attached to a real person's name.
        self.assertEqual(facilitator['avatar_url'], '')
        self.assertFalse(facilitator['verified'])

    def test_a_staff_facilitator_is_marked_verified(self):
        contact = Contact.objects.create(
            full_name='Kofi Guide', phone='+233200000072',
            email='kofi-live@example.com', is_active=True)
        worker = Worker.objects.create(contact=contact, role='Facilitator')
        self.session.facilitator = worker
        self.session.facilitator_name = ''
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['facilitator']['display_name'],
                         'Kofi Guide')
        self.assertTrue(res.data['facilitator']['verified'])

    # --- viewer sessions ---

    def test_viewer_count_follows_heartbeats_not_page_opens(self):
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['viewer_count'], 0)

        self.client.post(url(self.activity.id, 'viewer-session/'),
                         {'key': 'device-a'})
        self.client.post(url(self.activity.id, 'viewer-session/'),
                         {'key': 'device-b'})
        # The same device twice is still one viewer.
        self.client.post(url(self.activity.id, 'viewer-session/'),
                         {'key': 'device-a'})
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['viewer_count'], 2)
        self.assertEqual(LiveViewerSession.objects.count(), 2)

        self.client.delete(
            url(self.activity.id, 'viewer-session/') + '?key=device-a')
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['viewer_count'], 1)

    def test_a_stale_viewer_stops_counting(self):
        self.client.post(url(self.activity.id, 'viewer-session/'),
                         {'key': 'device-a'})
        LiveViewerSession.objects.update(
            last_seen_at=timezone.now() - timedelta(minutes=10))
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertEqual(res.data['viewer_count'], 0)

    def test_viewer_count_can_be_hidden(self):
        self.session.viewer_count_visible = False
        self.session.save()
        res = self.client.get(url(self.activity.id, 'live/'))
        self.assertFalse(res.data['viewer_count_visible'])

    # --- chat ---

    def test_a_guest_may_read_but_not_post(self):
        LiveChatMessage.objects.create(
            session=self.session, display_name='Ama', text='Hello everyone')
        res = self.client.get(url(self.activity.id, 'chat/'))
        self.assertEqual(len(res.data['results']), 1)

        res = self.client.post(url(self.activity.id, 'chat/'),
                               {'text': 'Hi'})
        self.assertEqual(res.status_code, 401)

    def test_guests_are_shut_out_when_chat_is_not_public(self):
        self.session.chat_visible_to_guests = False
        self.session.save()
        res = self.client.get(url(self.activity.id, 'chat/'))
        self.assertEqual(res.status_code, 401)

    def test_a_member_posts_and_the_cursor_returns_only_new_messages(self):
        res = self.client.post(url(self.activity.id, 'chat/'),
                               {'text': 'Grateful for this'}, **self._auth())
        self.assertEqual(res.status_code, 201)
        first_id = res.data['id']

        res = self.client.get(
            url(self.activity.id, 'chat/') + f'?after={first_id}')
        self.assertEqual(res.data['results'], [])

    def test_html_is_stripped_and_length_enforced(self):
        res = self.client.post(
            url(self.activity.id, 'chat/'),
            {'text': '<script>alert(1)</script>Peace'}, **self._auth())
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['text'], 'alert(1)Peace')

        res = self.client.post(url(self.activity.id, 'chat/'),
                               {'text': 'x' * 400}, **self._auth())
        self.assertEqual(res.status_code, 400)

    def test_empty_and_duplicate_messages_are_refused(self):
        auth = self._auth()
        self.assertEqual(
            self.client.post(url(self.activity.id, 'chat/'),
                             {'text': '   '}, **auth).status_code, 400)
        self.client.post(url(self.activity.id, 'chat/'),
                         {'text': 'Same text'}, **auth)
        LiveChatMessage.objects.update(
            created_at=timezone.now() - timedelta(minutes=1))
        res = self.client.post(url(self.activity.id, 'chat/'),
                               {'text': 'Same text'}, **auth)
        self.assertEqual(res.status_code, 400)

    def test_slow_mode_returns_retry_after(self):
        self.session.slow_mode_seconds = 30
        self.session.save()
        auth = self._auth()
        self.client.post(url(self.activity.id, 'chat/'),
                         {'text': 'First'}, **auth)
        res = self.client.post(url(self.activity.id, 'chat/'),
                               {'text': 'Second'}, **auth)
        self.assertEqual(res.status_code, 429)
        self.assertGreater(res.data['retry_after'], 0)

    def test_a_muted_member_is_refused_and_told_read_only(self):
        LiveChatMute.objects.create(session=self.session, contact=self.member)
        res = self.client.post(url(self.activity.id, 'chat/'),
                               {'text': 'Hello'}, **self._auth())
        self.assertEqual(res.status_code, 403)
        detail = self.client.get(url(self.activity.id, 'live/'),
                                 **self._auth())
        self.assertTrue(detail.data['chat']['read_only'])

    def test_a_deleted_message_keeps_its_slot_without_content(self):
        message = LiveChatMessage.objects.create(
            session=self.session, display_name='Ama', text='Removed me',
            deleted=True)
        res = self.client.get(url(self.activity.id, 'chat/'))
        row = res.data['results'][0]
        self.assertEqual(row['id'], message.id)
        self.assertTrue(row['deleted'])
        self.assertEqual(row['text'], '')

    def test_blocking_hides_that_member_from_my_view_only(self):
        other = Contact.objects.create(
            full_name='Noisy Person', phone='+233200000073',
            email='noisy@example.com', is_active=True, is_member=True)
        LiveChatMessage.objects.create(
            session=self.session, contact=other,
            display_name='Noisy', text='Spam spam')

        res = self.client.post(
            url(self.activity.id, f'chat/block/{other.id}/'), **self._auth())
        self.assertEqual(res.status_code, 201)

        mine = self.client.get(url(self.activity.id, 'chat/'), **self._auth())
        self.assertEqual(mine.data['results'], [])
        # Everyone else still sees it — blocking is personal, not moderation.
        theirs = self.client.get(url(self.activity.id, 'chat/'))
        self.assertEqual(len(theirs.data['results']), 1)

    def test_reporting_flags_for_moderation(self):
        message = LiveChatMessage.objects.create(
            session=self.session, display_name='Ama', text='Report me')
        res = self.client.post(
            url(self.activity.id, f'chat/{message.id}/report/'),
            **self._auth())
        self.assertEqual(res.status_code, 200)
        message.refresh_from_db()
        self.assertEqual(message.reported_count, 1)

    def test_a_pinned_message_is_returned_separately(self):
        LiveChatMessage.objects.create(
            session=self.session, display_name='Moderator',
            role='moderator', text='Welcome — please be kind.', pinned=True)
        res = self.client.get(url(self.activity.id, 'chat/'))
        self.assertEqual(res.data['pinned']['role'], 'moderator')

    # --- reactions & save ---

    def test_reactions_aggregate_and_are_rate_limited(self):
        auth = self._auth()
        res = self.client.post(url(self.activity.id, 'reaction/'),
                               {'kind': 'appreciate'}, **auth)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['counts']['appreciate'], 1)

        res = self.client.post(url(self.activity.id, 'reaction/'),
                               {'kind': 'appreciate'}, **auth)
        self.assertEqual(res.status_code, 429)

        LiveReaction.objects.update(
            created_at=timezone.now() - timedelta(minutes=1))
        res = self.client.post(url(self.activity.id, 'reaction/'),
                               {'kind': 'thanks'}, **auth)
        self.assertEqual(res.data['counts']['thanks'], 1)

    def test_an_unknown_reaction_is_refused(self):
        res = self.client.post(url(self.activity.id, 'reaction/'),
                               {'kind': 'fire'}, **self._auth())
        self.assertEqual(res.status_code, 400)

    def test_save_and_unsave(self):
        auth = self._auth()
        self.assertEqual(
            self.client.post(url(self.activity.id, 'save/'),
                             **auth).status_code, 201)
        detail = self.client.get(url(self.activity.id, 'live/'), **auth)
        self.assertTrue(detail.data['saved'])

        self.client.delete(url(self.activity.id, 'save/'), **auth)
        detail = self.client.get(url(self.activity.id, 'live/'), **auth)
        self.assertFalse(detail.data['saved'])

    def test_a_guest_cannot_save(self):
        self.assertEqual(
            self.client.post(url(self.activity.id, 'save/')).status_code, 401)

    def test_a_missing_event_returns_404(self):
        self.assertEqual(
            self.client.get(url(999999, 'live/')).status_code, 404)
