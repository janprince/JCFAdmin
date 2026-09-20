"""Dashboard-authored practices power the app's Practice tab (design 27)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from members.models import Contact
from mobile_api.models import MobileToken

from .models import Practice, PracticeLog


class PracticeApiTests(APITestCase):
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

    def test_dashboard_practice_reaches_the_app(self):
        res = self.client.post(reverse('practices:practice_create'), {
            'title': 'Balanced-State Practice',
            'description': 'Center your mind.',
            'category': 'general', 'minutes': 20,
            'audience': 'members', 'order': 0, 'is_active': 'on',
            'audio_url': 'https://cdn.example.com/balanced.mp3',
        })
        self.assertEqual(res.status_code, 302)

        summary = self.client.get('/api/mobile/v1/practice/summary/', **self._auth())
        self.assertEqual(summary.data['todays_practice']['title'],
                         'Balanced-State Practice')
        self.assertEqual(summary.data['todays_practice']['minutes'], 20)

    def test_guest_sees_only_public_practices(self):
        Practice.objects.create(title='Free Intro', audience='public')
        Practice.objects.create(title='Members Only', audience='members')
        res = self.client.get('/api/mobile/v1/practices/')
        titles = [p['title'] for p in res.data['results']]
        self.assertEqual(titles, ['Free Intro'])

    def test_logging_builds_streak_and_week(self):
        practice = Practice.objects.create(title='Morning Stillness', minutes=10)
        auth = self._auth()
        today = timezone.localdate()
        # Two past consecutive days...
        for delta in (2, 1):
            PracticeLog.objects.create(
                contact=self.member, practice=practice,
                date=today - timedelta(days=delta), minutes=10)
        # ...then log today via the API.
        res = self.client.post('/api/mobile/v1/practice/log/',
                               {'practice_id': practice.pk},
                               format='json', **auth)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['streak_days'], 3)

        summary = self.client.get('/api/mobile/v1/practice/summary/', **auth)
        self.assertEqual(summary.data['streak_days'], 3)
        self.assertTrue(summary.data['done_today'])
        self.assertEqual(len(summary.data['week']), 7)
        self.assertGreaterEqual(summary.data['week_days_done'], 1)
        self.assertEqual(summary.data['weekly_goal'], 7)
        # Log minutes default to the practice's duration.
        self.assertEqual(PracticeLog.objects.filter(
            date=today).first().minutes, 10)

    def test_summary_requires_membership(self):
        res = self.client.get('/api/mobile/v1/practice/summary/')
        self.assertEqual(res.status_code, 401)
