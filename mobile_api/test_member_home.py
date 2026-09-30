"""Member Home aggregate: one call, every section, audience-correct."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from activities.models import Activity
from engagement.models import Announcement, DailyInspiration
from members.models import Contact
from practices.models import Practice, PracticeLog
from teachings.models import Teaching, TeachingProgress, TeachingSeries

from .models import MobileToken

HOME = '/api/mobile/v1/home/member/'


class MemberHomeTests(APITestCase):
    def setUp(self):
        self.member = Contact.objects.create(
            full_name='Ama Mensah', phone='+233200000041',
            email='ama-home@example.com', is_active=True, is_member=True)

    def _auth(self, contact=None):
        token = MobileToken.issue(contact or self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def test_guest_cannot_load_member_home(self):
        self.assertEqual(self.client.get(HOME).status_code, 401)

    def test_summary_and_welcome_use_the_members_first_name(self):
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(res.data['member_summary']['preferred_name'], 'Ama')
        self.assertEqual(res.data['member_summary']['membership_status'], 'member')
        self.assertIn('{name}', res.data['welcome']['title_template'])
        self.assertEqual(res.data['welcome']['destination_id'], 'journey')

    def test_sections_are_empty_not_missing_for_a_new_member(self):
        res = self.client.get(HOME, **self._auth())
        for key in ('continue_learning', 'continue_practice', 'announcements',
                    'daily_inspirations', 'quick_actions'):
            self.assertIn(key, res.data)
        self.assertEqual(res.data['continue_learning'], [])
        self.assertEqual(res.data['continue_practice'], [])
        self.assertIsNone(res.data['featured_member_content'])

    def test_continue_learning_reports_progress_and_resume_point(self):
        series = TeachingSeries.objects.create(
            title='Foundations', slug='foundations', is_published=True)
        lessons = [
            Teaching.objects.create(
                topic=f'Lesson {i}', slug=f'lesson-{i}', series=series,
                order=i, status='published', duration_seconds=600)
            for i in range(1, 4)
        ]
        TeachingProgress.objects.create(
            contact=self.member, teaching=lessons[0], completed=True)
        TeachingProgress.objects.create(
            contact=self.member, teaching=lessons[1], completed=False)

        res = self.client.get(HOME, **self._auth())
        card = res.data['continue_learning'][0]
        self.assertEqual(card['content_id'], 'foundations')
        self.assertEqual(card['total_units'], 3)
        self.assertEqual(card['completed_units'], 1)
        self.assertEqual(card['progress_percentage'], 33)
        self.assertEqual(card['current_unit_id'], 'lesson-2')
        self.assertEqual(card['destination_id'], 'lesson')

    def test_finished_series_is_not_resumable(self):
        series = TeachingSeries.objects.create(
            title='Done', slug='done', is_published=True)
        lesson = Teaching.objects.create(
            topic='Only', slug='only', series=series, status='published')
        TeachingProgress.objects.create(
            contact=self.member, teaching=lesson, completed=True)
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(res.data['continue_learning'], [])

    def test_continue_practice_carries_the_streak(self):
        practice = Practice.objects.create(
            title='Morning Stillness', audience='members', minutes=15)
        today = timezone.localdate()
        for delta in (1, 0):
            PracticeLog.objects.create(
                contact=self.member, practice=practice,
                date=today - timedelta(days=delta), minutes=15)

        res = self.client.get(HOME, **self._auth())
        card = res.data['continue_practice'][0]
        self.assertEqual(card['title'], 'Morning Stillness')
        self.assertEqual(card['current_streak'], 2)
        self.assertEqual(card['duration_seconds'], 900)
        self.assertIsNone(card['progress_percentage'])

    def test_practice_the_member_may_no_longer_see_is_dropped(self):
        practice = Practice.objects.create(
            title='Students Only', audience='students', minutes=20)
        PracticeLog.objects.create(
            contact=self.member, practice=practice,
            date=timezone.localdate(), minutes=20)
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(res.data['continue_practice'], [])

    def test_featured_member_content_is_premium_and_access_is_server_decided(self):
        Teaching.objects.create(
            topic='Public One', slug='public-one', status='published',
            tier='general')
        Teaching.objects.create(
            topic='Members Only', slug='members-only', status='published',
            tier='premium', author='Dr. Baffour Jan', media_kind='audio')

        res = self.client.get(HOME, **self._auth())
        featured = res.data['featured_member_content']
        self.assertEqual(featured['title'], 'Members Only')
        self.assertEqual(featured['content_type'], 'audio')
        self.assertTrue(featured['access_granted'])
        self.assertEqual(featured['access_level'], 'members')

        inactive = Contact.objects.create(
            full_name='Lapsed', phone='+233200000042',
            email='lapsed@example.com', is_active=False, is_member=True)
        token = MobileToken.issue(inactive)
        res = self.client.get(
            HOME, HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.assertEqual(res.status_code, 403)

    def test_featured_event_carries_end_time_for_live_validation(self):
        Activity.objects.create(
            title='Community Circle', kind='live', audience='public',
            starts_at=timezone.now() + timedelta(hours=1),
            duration_minutes=90)
        res = self.client.get(HOME, **self._auth())
        event = res.data['featured_event']
        self.assertEqual(event['title'], 'Community Circle')
        self.assertIsNotNone(event['ends_at'])
        self.assertIn('timezone', event)
        self.assertEqual(event['destination_id'], 'event')

    def test_announcements_carry_read_state_and_category(self):
        Announcement.objects.create(
            title='September Gathering', body='Join us for an evening.',
            audience='members')
        res = self.client.get(HOME, **self._auth())
        row = res.data['announcements'][0]
        self.assertEqual(row['title'], 'September Gathering')
        self.assertFalse(row['read'])
        self.assertTrue(row['category'])

    def test_downloads_is_not_offered_until_offline_ships(self):
        res = self.client.get(HOME, **self._auth())
        ids = [a['id'] for a in res.data['quick_actions']]
        self.assertNotIn('downloads', ids)
        self.assertIn('my_library', ids)

    def test_inspirations_and_unread_count_are_included(self):
        DailyInspiration.objects.create(
            date=timezone.localdate(), quote='Awareness is freedom.')
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(
            res.data['daily_inspirations'][0]['quote'], 'Awareness is freedom.')
        self.assertEqual(res.data['unread_notification_count'], 0)
        self.assertIn('fetched_at', res.data)
