"""Dashboard -> mobile API, hand in hand: what staff publish here must be
exactly what the app receives."""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from members.models import Contact
from mobile_api.models import MobileToken

from .models import Announcement, Notification


class EngagementDashboardTests(APITestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='staff', email='staff@jcf.org', password='x')
        self.client.force_login(self.staff)
        self.member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000001',
            email='ama@example.com', is_active=True, is_member=True)
        self.student = Contact.objects.create(
            full_name='Kofi Student', phone='+233200000002',
            email='kofi@example.com', is_active=True, is_student=True)

    def _member_api(self, contact):
        token = MobileToken.issue(contact)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    # --- announcements ---

    def test_dashboard_announcement_reaches_the_app(self):
        res = self.client.post(reverse('engagement:announcement_create'), {
            'title': 'Sunday service moved',
            'body': 'We meet at 9am this week.',
            'audience': 'public',
            'is_published': 'on',
        })
        self.assertEqual(res.status_code, 302)

        api = self.client.get('/api/mobile/v1/announcements/')
        titles = [a['title'] for a in api.data['results']]
        self.assertIn('Sunday service moved', titles)

    def test_draft_announcement_hidden_from_the_app(self):
        self.client.post(reverse('engagement:announcement_create'), {
            'title': 'Draft only', 'body': 'x', 'audience': 'public',
        })  # is_published unchecked
        api = self.client.get('/api/mobile/v1/announcements/')
        self.assertEqual(api.data['results'], [])

    def test_students_announcement_gated_by_audience(self):
        self.client.post(reverse('engagement:announcement_create'), {
            'title': 'Students retreat briefing', 'body': 'x',
            'audience': 'students', 'is_published': 'on',
        })
        # A member does not see it; a student does.
        member_res = self.client.get(
            '/api/mobile/v1/announcements/', **self._member_api(self.member))
        self.assertEqual(member_res.data['results'], [])
        student_res = self.client.get(
            '/api/mobile/v1/announcements/', **self._member_api(self.student))
        self.assertEqual(student_res.data['results'][0]['title'],
                         'Students retreat briefing')

    def test_pin_toggle(self):
        a = Announcement.objects.create(title='T', body='b')
        self.client.post(reverse('engagement:announcement_pin', args=[a.pk]))
        a.refresh_from_db()
        self.assertTrue(a.pinned)

    # --- compose notification ---

    def test_compose_to_members_lands_in_member_inboxes(self):
        res = self.client.post(reverse('engagement:notification_compose'), {
            'audience': 'members',
            'title': 'Retreat photos are up',
            'body': 'See the gallery.',
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(Notification.objects.count(), 2)  # member + student

        inbox = self.client.get(
            '/api/mobile/v1/notifications/', **self._member_api(self.member))
        self.assertEqual(inbox.data['results'][0]['title'], 'Retreat photos are up')
        self.assertFalse(inbox.data['results'][0]['is_read'])

    def test_compose_to_single_contact(self):
        self.client.post(reverse('engagement:notification_compose'), {
            'audience': 'single',
            'recipient': 'kofi@example.com',
            'title': 'Your certificate is ready',
        })
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Notification.objects.get().contact, self.student)

    def test_compose_single_requires_valid_recipient(self):
        res = self.client.post(reverse('engagement:notification_compose'), {
            'audience': 'single', 'recipient': 'nobody@nowhere.com', 'title': 'x',
        })
        self.assertEqual(res.status_code, 200)  # re-rendered with error
        self.assertEqual(Notification.objects.count(), 0)

    def test_dashboard_requires_login(self):
        self.client.logout()
        res = self.client.get(reverse('engagement:announcement_list'))
        self.assertEqual(res.status_code, 302)


class DailyInspirationTests(APITestCase):
    """Dashboard-scheduled inspirations feed the app's Home hero."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='staff2', email='staff2@jcf.org', password='x')
        self.client.force_login(self.staff)

    def test_scheduled_inspiration_reaches_the_app(self):
        from django.urls import reverse as r
        from django.utils import timezone
        today = timezone.localdate()
        res = self.client.post(r('engagement:inspiration_create'), {
            'date': today.isoformat(),
            'quote': 'Freedom begins when awareness becomes your way of living.',
            'author': 'Dr. Baffour Jan',
            'reflection': 'Pause, observe, and let awareness guide your response today.',
            'is_published': 'on',
        })
        self.assertEqual(res.status_code, 302)

        api = self.client.get('/api/mobile/v1/inspiration/today/')
        self.assertEqual(api.status_code, 200)
        self.assertIn('Freedom begins', api.data['quote'])
        self.assertEqual(api.data['author'], 'Dr. Baffour Jan')

    def test_future_and_draft_entries_hidden_falls_back_to_latest_past(self):
        from datetime import timedelta
        from django.utils import timezone
        today = timezone.localdate()
        Announcement  # keep import satisfied
        from .models import DailyInspiration
        DailyInspiration.objects.create(
            date=today + timedelta(days=1), quote='Tomorrow quote')
        DailyInspiration.objects.create(
            date=today, quote='Draft today', is_published=False)
        DailyInspiration.objects.create(
            date=today - timedelta(days=2), quote='Two days ago')

        api = self.client.get('/api/mobile/v1/inspiration/today/')
        self.assertEqual(api.data['quote'], 'Two days ago')

    def test_no_entries_returns_204(self):
        api = self.client.get('/api/mobile/v1/inspiration/today/')
        self.assertEqual(api.status_code, 204)


class AnnouncementReadTests(APITestCase):
    """Unread dots (design 28): reads are tracked per member."""

    def setUp(self):
        self.member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000011',
            email='ama-read@example.com', is_active=True, is_member=True)
        self.announcement = Announcement.objects.create(
            title='September Gathering', body='Join us.', audience='public')

    def _auth(self):
        token = MobileToken.issue(self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def test_member_unread_then_read(self):
        auth = self._auth()
        api = self.client.get('/api/mobile/v1/announcements/', **auth)
        self.assertFalse(api.data['results'][0]['is_read'])

        res = self.client.post(
            f'/api/mobile/v1/announcements/{self.announcement.pk}/read/',
            **auth)
        self.assertEqual(res.status_code, 200)
        # Marking twice is fine (idempotent).
        self.client.post(
            f'/api/mobile/v1/announcements/{self.announcement.pk}/read/',
            **auth)

        api = self.client.get('/api/mobile/v1/announcements/', **auth)
        self.assertTrue(api.data['results'][0]['is_read'])

    def test_guest_sees_no_unread_dots_and_cannot_mark(self):
        api = self.client.get('/api/mobile/v1/announcements/')
        self.assertTrue(api.data['results'][0]['is_read'])

        res = self.client.post(
            f'/api/mobile/v1/announcements/{self.announcement.pk}/read/')
        self.assertEqual(res.status_code, 401)
