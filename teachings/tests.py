"""Dashboard -> mobile API, hand in hand: content authored here is exactly
what the app's Lessons screens receive."""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from members.models import Contact
from mobile_api.models import MobileToken

from .models import Teaching, TeachingSeries


class TeachingsDashboardTests(APITestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='staff', email='staff@jcf.org', password='x')
        self.client.force_login(self.staff)
        self.member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000001',
            email='ama@example.com', is_active=True, is_member=True)

    def _member_headers(self):
        token = MobileToken.issue(self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def test_series_and_premium_teaching_reach_the_app(self):
        # Author a series, then a published premium lesson inside it.
        self.client.post(reverse('teachings:series_create'), {
            'title': 'InnerSpace Level 1', 'description': 'The first steps.',
            'order': 0, 'is_published': 'on',
        })
        series = TeachingSeries.objects.get()
        res = self.client.post(reverse('teachings:teaching_create'), {
            'topic': 'The Breath as Anchor',
            'format': 'lecture', 'language': 'english', 'status': 'published',
            'description': 'First practice talk.',
            'tier': 'premium', 'series': series.pk, 'order': 1,
            'media_kind': 'audio',
            'youtube_url': 'https://youtube.com/watch?v=abc123',
        })
        self.assertEqual(res.status_code, 302)
        teaching = Teaching.objects.get()
        self.assertEqual(teaching.tier, 'premium')
        self.assertEqual(teaching.series, series)

        # Guest: listed but locked, media withheld on detail.
        listing = self.client.get('/api/mobile/v1/teachings/')
        row = listing.data['results'][0]
        self.assertTrue(row['is_locked'])
        self.assertEqual(row['series'], series.slug)
        detail = self.client.get(f'/api/mobile/v1/teachings/{teaching.slug}/')
        self.assertEqual(detail.status_code, 403)

        # Member: unlocked with media.
        detail = self.client.get(
            f'/api/mobile/v1/teachings/{teaching.slug}/', **self._member_headers())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['youtube_url'],
                         'https://youtube.com/watch?v=abc123')

        # Series API carries it too.
        series_api = self.client.get(
            f'/api/mobile/v1/series/{series.slug}/', **self._member_headers())
        self.assertEqual(series_api.data['teaching_count'], 1)
        self.assertEqual(series_api.data['teachings'][0]['topic'],
                         'The Breath as Anchor')

    def test_quick_add_defaults_and_pending_hidden_from_app(self):
        # Quick-add posts only the basics (as the list page form does).
        res = self.client.post(reverse('teachings:teaching_create'), {
            'topic': 'Draft talk', 'format': 'lecture',
            'language': 'english', 'status': 'pending', 'description': '',
        })
        self.assertEqual(res.status_code, 302)
        teaching = Teaching.objects.get()
        self.assertEqual(teaching.tier, 'general')

        listing = self.client.get('/api/mobile/v1/teachings/')
        self.assertEqual(listing.data['results'], [])  # pending is invisible


class AcceptLanguageTests(APITestCase):
    """The API honours Accept-Language for server-generated text."""

    def test_builtin_error_translates(self):
        res = self.client.get('/api/mobile/v1/auth/me/',
                              HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(res.status_code, 401)
        self.assertIn('authentification', str(res.data['detail']).lower())

    def test_default_stays_english(self):
        res = self.client.get('/api/mobile/v1/auth/me/')
        self.assertEqual(res.status_code, 401)
        self.assertIn('Authentication', str(res.data['detail']))
