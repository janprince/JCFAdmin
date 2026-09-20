"""Dashboard-scheduled activities power the app's Upcoming feed (design 25)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from members.models import Contact
from mobile_api.models import MobileToken
from programs.models import Program

from .models import Activity, ActivityReminder

FEED = '/api/mobile/v1/activities/upcoming/'
REMIND = '/api/mobile/v1/activities/reminder/'


class ActivitiesApiTests(APITestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='staff', email='staff@jcf.org', password='x')
        self.client.force_login(self.staff)
        self.member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000001',
            email='ama@example.com', is_active=True, is_member=True)

    def _auth(self):
        token = MobileToken.issue(self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def test_dashboard_activity_reaches_the_feed(self):
        starts = timezone.now() + timedelta(days=1)
        res = self.client.post(reverse('activities:activity_create'), {
            'title': 'Morning Practice',
            'description': 'Start your day with stillness.',
            'kind': 'practice',
            'starts_at': starts.strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 45, 'venue': '',
            'audience': 'public', 'is_active': 'on',
        })
        self.assertEqual(res.status_code, 302)

        feed = self.client.get(FEED)
        titles = [i['title'] for i in feed.data['results']]
        self.assertIn('Morning Practice', titles)

    def test_feed_merges_programmes_sorted_by_start(self):
        Activity.objects.create(
            title='Community Circle Live', kind='live',
            starts_at=timezone.now() + timedelta(days=3))
        Program.objects.create(
            title='Open Day', year=2026, audience='public', is_published=True,
            starts_on=timezone.localdate() + timedelta(days=1))
        res = self.client.get(FEED)
        kinds = [i['kind'] for i in res.data['results']]
        self.assertEqual(kinds, ['programme', 'live'])
        self.assertTrue(res.data['results'][0]['all_day'])

    def test_guest_sees_only_public_items(self):
        Activity.objects.create(
            title='Public Sitting', audience='public',
            starts_at=timezone.now() + timedelta(days=1))
        Activity.objects.create(
            title='Members Sitting', audience='members',
            starts_at=timezone.now() + timedelta(days=1))
        res = self.client.get(FEED)
        titles = [i['title'] for i in res.data['results']]
        self.assertEqual(titles, ['Public Sitting'])

        member_res = self.client.get(FEED, **self._auth())
        member_titles = [i['title'] for i in member_res.data['results']]
        self.assertIn('Members Sitting', member_titles)

    def test_live_soon_flag(self):
        Activity.objects.create(
            title='Starting Now', kind='live',
            starts_at=timezone.now() + timedelta(minutes=30))
        Activity.objects.create(
            title='Next Week', kind='live',
            starts_at=timezone.now() + timedelta(days=6))
        res = self.client.get(FEED)
        flags = {i['title']: i['live_soon'] for i in res.data['results']}
        self.assertTrue(flags['Starting Now'])
        self.assertFalse(flags['Next Week'])

    def test_past_activity_leaves_the_feed(self):
        Activity.objects.create(
            title='Yesterday', starts_at=timezone.now() - timedelta(days=1))
        res = self.client.get(FEED)
        self.assertEqual(res.data['results'], [])

    def test_reminder_toggle_on_activity_and_programme(self):
        activity = Activity.objects.create(
            title='Q&A', kind='live',
            starts_at=timezone.now() + timedelta(days=2))
        program = Program.objects.create(
            title='Retreat', year=2027, audience='public', is_published=True,
            starts_on=timezone.localdate() + timedelta(days=10))
        auth = self._auth()

        res = self.client.post(REMIND, {'activity_id': activity.id}, **auth)
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data['reminder_set'])

        res = self.client.post(REMIND, {'program_slug': program.slug}, **auth)
        self.assertTrue(res.data['reminder_set'])

        feed = self.client.get(FEED, **auth)
        self.assertTrue(all(i['reminder_set'] for i in feed.data['results']))

        # Toggle the activity reminder off again.
        res = self.client.post(REMIND, {'activity_id': activity.id}, **auth)
        self.assertFalse(res.data['reminder_set'])
        self.assertEqual(ActivityReminder.objects.count(), 1)

    def test_reminder_requires_auth(self):
        activity = Activity.objects.create(
            title='Q&A', starts_at=timezone.now() + timedelta(days=2))
        res = self.client.post(REMIND, {'activity_id': activity.id})
        self.assertEqual(res.status_code, 401)
