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


class ContinueLearningTests(APITestCase):
    """Progress reporting + the Continue Learning summary (design 26)."""

    def setUp(self):
        from .models import Teaching, TeachingSeries
        self.member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000001',
            email='ama@example.com', is_active=True, is_member=True)
        self.series = TeachingSeries.objects.create(title='Understanding the Mind')
        self.lessons = [
            Teaching.objects.create(
                topic=f'Lesson {i}', status='published',
                series=self.series, order=i)
            for i in range(1, 4)
        ]

    def _auth(self):
        token = MobileToken.issue(self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def test_opening_a_lesson_counts_view_and_records_history(self):
        slug = self.lessons[0].slug
        self.client.get(f'/api/mobile/v1/teachings/{slug}/', **self._auth())
        self.lessons[0].refresh_from_db()
        self.assertEqual(self.lessons[0].view_count, 1)

        summary = self.client.get(
            '/api/mobile/v1/learning/continue/', **self._auth())
        self.assertEqual(
            summary.data['recently_viewed'][0]['topic'], 'Lesson 1')

    def test_completion_drives_series_progress(self):
        auth = self._auth()
        for lesson in self.lessons[:1]:
            self.client.post(
                f'/api/mobile/v1/teachings/{lesson.slug}/progress/',
                {'completed': True}, format='json', **auth)
        # A second lesson merely viewed.
        self.client.get(
            f'/api/mobile/v1/teachings/{self.lessons[1].slug}/', **auth)

        summary = self.client.get('/api/mobile/v1/learning/continue/', **auth)
        self.assertEqual(summary.data['active_series'], 1)
        self.assertEqual(summary.data['lessons_completed'], 1)
        card = summary.data['series'][0]
        self.assertEqual(card['title'], 'Understanding the Mind')
        self.assertEqual(card['percent'], 33)
        self.assertEqual(card['lessons_total'], 3)
        self.assertEqual(card['current_lesson'], 2)
        # Resume points at the viewed-but-not-completed lesson.
        self.assertEqual(card['resume_slug'], self.lessons[1].slug)

    def test_progress_requires_membership(self):
        res = self.client.post(
            f'/api/mobile/v1/teachings/{self.lessons[0].slug}/progress/',
            {'completed': True}, format='json')
        self.assertEqual(res.status_code, 401)

    def test_author_served_in_listing(self):
        api = self.client.get('/api/mobile/v1/teachings/')
        self.assertEqual(api.data['results'][0]['author'], 'Dr. Baffour Jan')
