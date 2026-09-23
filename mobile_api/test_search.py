"""Global search (designs 30/31): one query across every domain."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from activities.models import Activity
from centres.models import Centre
from engagement.models import Announcement
from members.models import Contact
from practices.models import Practice
from programs.models import Program
from teachings.models import Teaching

from .models import MobileToken, SearchQuery

SEARCH = '/api/mobile/v1/search/'
POPULAR = '/api/mobile/v1/search/popular/'


class GlobalSearchTests(APITestCase):
    def setUp(self):
        self.student = Contact.objects.create(
            full_name='Kofi Student', phone='+233200000031',
            email='kofi-search@example.com', is_active=True, is_student=True)
        Teaching.objects.create(
            topic='Awareness in Everyday Life', author='Dr. Baffour Jan',
            description='Explore how awareness transforms ordinary moments.',
            status='published')
        Practice.objects.create(
            title='Morning Awareness Practice', audience='students',
            description='Center your awareness.', minutes=12)
        Program.objects.create(
            title='Awareness Retreat', year=2027, audience='public',
            is_published=True,
            description='A weekend of awareness.',
            starts_on=timezone.localdate() + timedelta(days=30))
        Activity.objects.create(
            title='Awareness Q&A', kind='live', audience='public',
            starts_at=timezone.now() + timedelta(days=2))
        Centre.objects.create(
            name='Accra Centre', slug='accra-centre', location='Accra',
            address='1 Cosmic Way', description='Awareness in the city.',
            leader_name='Ama', leader_title='Director',
            contact_email='accra@jcf.org')
        Announcement.objects.create(
            title='Awareness Week', body='Join awareness week.',
            audience='public')

    def _auth(self):
        token = MobileToken.issue(self.student)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def test_student_search_spans_all_domains(self):
        res = self.client.get(SEARCH, {'q': 'awareness'}, **self._auth())
        kinds = sorted(i['kind'] for i in res.data['results'])
        self.assertEqual(kinds, sorted([
            'video', 'practice', 'programme', 'event', 'centre',
            'announcement']))
        self.assertEqual(res.data['total'], 6)

    def test_guest_does_not_see_student_practice(self):
        res = self.client.get(SEARCH, {'q': 'awareness'})
        kinds = [i['kind'] for i in res.data['results']]
        self.assertNotIn('practice', kinds)

    def test_short_query_returns_nothing_and_is_not_logged(self):
        res = self.client.get(SEARCH, {'q': 'a'})
        self.assertEqual(res.data['results'], [])
        self.assertEqual(SearchQuery.objects.count(), 0)

    def test_popular_aggregates_logged_terms(self):
        for _ in range(3):
            self.client.get(SEARCH, {'q': 'Awareness'})
        self.client.get(SEARCH, {'q': 'innerspace'})
        res = self.client.get(POPULAR)
        self.assertEqual(res.data['results'][0], 'awareness')
        self.assertIn('innerspace', res.data['results'])
