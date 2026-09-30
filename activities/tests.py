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

    def test_feed_lists_activities_only(self):
        """Programmes left the browse feed when it gained keyset paging.

        A programme is a multi-week course, not a dated card with a seat
        and a format, and merging two tables cannot be paged by a cursor.
        Programmes keep their own screen; reminders on them still work.
        """
        Activity.objects.create(
            title='Community Circle Live', kind='live',
            starts_at=timezone.now() + timedelta(days=3))
        Program.objects.create(
            title='Open Day', year=2026, audience='public', is_published=True,
            starts_on=timezone.localdate() + timedelta(days=1))
        res = self.client.get(FEED)
        titles = [i['title'] for i in res.data['results']]
        self.assertEqual(titles, ['Community Circle Live'])

    def test_guest_sees_members_items_but_cannot_open_them(self):
        """The browse feed shows the tier above the caller, locked.

        Hiding members-only sittings from a guest makes the schedule look
        empty; showing them locked is what gives signing in a point.
        """
        Activity.objects.create(
            title='Public Sitting', audience='public',
            starts_at=timezone.now() + timedelta(days=1))
        Activity.objects.create(
            title='Members Sitting', audience='members',
            starts_at=timezone.now() + timedelta(days=1))
        res = self.client.get(FEED)
        access = {i['title']: i['access']['allowed']
                  for i in res.data['results']}
        self.assertTrue(access['Public Sitting'])
        self.assertFalse(access['Members Sitting'])

        member_res = self.client.get(FEED, **self._auth())
        member_access = {i['title']: i['access']['allowed']
                         for i in member_res.data['results']}
        self.assertTrue(member_access['Members Sitting'])

    def test_starting_soon_flag(self):
        Activity.objects.create(
            title='Starting Now', kind='live',
            starts_at=timezone.now() + timedelta(minutes=30))
        Activity.objects.create(
            title='Next Week', kind='live',
            starts_at=timezone.now() + timedelta(days=6))
        res = self.client.get(FEED)
        flags = {i['title']: i['starting_soon'] for i in res.data['results']}
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
