"""App bootstrap endpoint (owner spec, splash screen)."""
from django.test import TestCase, override_settings
from django.urls import reverse

from members.models import Contact
from mobile_api.bootstrap_api import parse_version
from mobile_api.models import MobileToken


def make_contact(phone, **flags):
    return Contact.objects.create(
        full_name=f'Test {phone}', phone=phone,
        email=f'{phone.strip("+")}@example.com', is_active=True, **flags)


class VersionParsingTests(TestCase):
    def test_a_normal_version(self):
        self.assertEqual(parse_version('1.2.3'), (1, 2, 3))

    def test_short_versions_are_padded(self):
        self.assertEqual(parse_version('2'), (2, 0, 0))
        self.assertEqual(parse_version('2.1'), (2, 1, 0))

    def test_build_suffixes_are_ignored(self):
        self.assertEqual(parse_version('1.4.2+87'), (1, 4, 2))

    def test_garbage_sorts_lowest_rather_than_highest(self):
        """An unreadable version must never read as new enough, or a
        malformed header becomes a way past the version gate."""
        for raw in ('', None, 'banana', '...'):
            with self.subTest(raw=raw):
                self.assertEqual(parse_version(raw), (0, 0, 0))

    def test_ordering(self):
        self.assertLess(parse_version('1.0.0'), parse_version('1.0.1'))
        self.assertLess(parse_version('1.9.9'), parse_version('2.0.0'))


class BootstrapTests(TestCase):
    def setUp(self):
        self.url = reverse('mobile_api:bootstrap')

    def auth(self, contact):
        token = MobileToken.issue(contact)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def test_a_guest_may_bootstrap(self):
        """A guest needs the version and maintenance answer as much as a
        member does, so this endpoint is public."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['session']['authenticated'])
        self.assertEqual(response.json()['session']['user_type'], 'guest')

    def test_the_payload_carries_every_section(self):
        body = self.client.get(self.url).json()
        for key in ('server_time', 'maintenance', 'version', 'session',
                    'initial_route'):
            self.assertIn(key, body)

    def test_a_contact_approved_by_the_member_flag_is_a_student(self):
        # There is no member tier any more. `is_member` is a CRM flag and
        # still means approved, so the app reports the one signed-in tier.
        contact = make_contact('+233700000001', is_member=True)
        body = self.client.get(self.url, **self.auth(contact)).json()
        self.assertTrue(body['session']['authenticated'])
        self.assertEqual(body['session']['user_type'], 'student')

    def test_a_student_is_reported_as_a_student(self):
        contact = make_contact('+233700000002', is_student=True)
        body = self.client.get(self.url, **self.auth(contact)).json()
        self.assertEqual(body['session']['user_type'], 'student')

    def test_an_invalid_token_is_a_guest_not_an_error(self):
        """Launching with a stale token must still boot the app."""
        response = self.client.get(
            self.url, HTTP_AUTHORIZATION='Bearer not-a-real-token')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['session']['authenticated'])

    # --- version gate ---------------------------------------------------

    def test_an_old_build_is_asked_to_update(self):
        body = self.client.get(self.url, HTTP_X_APP_VERSION='0.9.0').json()
        self.assertTrue(body['version']['update_required'])

    def test_the_current_build_is_not(self):
        body = self.client.get(self.url, HTTP_X_APP_VERSION='1.0.0').json()
        self.assertFalse(body['version']['update_required'])

    def test_a_newer_build_is_not(self):
        body = self.client.get(self.url, HTTP_X_APP_VERSION='2.4.0').json()
        self.assertFalse(body['version']['update_required'])

    def test_no_version_header_does_not_force_an_update(self):
        """An older client that never learned to send the header must not
        be locked out by a gate it cannot report against."""
        body = self.client.get(self.url).json()
        self.assertFalse(body['version']['update_required'])

    def test_the_store_url_follows_the_platform(self):
        ios = self.client.get(self.url, HTTP_X_PLATFORM='ios').json()
        android = self.client.get(self.url, HTTP_X_PLATFORM='android').json()
        self.assertIn('apple.com', ios['version']['store_url'])
        self.assertIn('play.google.com', android['version']['store_url'])

    def test_an_unknown_platform_gets_no_store_url(self):
        body = self.client.get(self.url, HTTP_X_PLATFORM='fridge').json()
        self.assertIsNone(body['version']['store_url'])

    # --- maintenance ----------------------------------------------------

    def test_maintenance_is_off_by_default(self):
        self.assertFalse(
            self.client.get(self.url).json()['maintenance']['enabled'])

    @override_settings(
        MOBILE_MAINTENANCE=True,
        MOBILE_MAINTENANCE_TITLE='Back shortly',
        MOBILE_MAINTENANCE_MESSAGE='We are making an improvement.',
        MOBILE_MAINTENANCE_ALLOW_OFFLINE=False)
    def test_maintenance_carries_its_own_words(self):
        body = self.client.get(self.url).json()['maintenance']
        self.assertTrue(body['enabled'])
        self.assertEqual(body['title'], 'Back shortly')
        self.assertEqual(body['message'], 'We are making an improvement.')
        self.assertFalse(body['allow_offline'])

    @override_settings(MOBILE_MAINTENANCE=True)
    def test_maintenance_without_words_sends_null_not_empty_strings(self):
        """The app falls back to its own localized copy when the server
        has nothing specific to say; an empty string would render as a
        blank message instead."""
        body = self.client.get(self.url).json()['maintenance']
        self.assertTrue(body['enabled'])
        self.assertIsNone(body['title'])
        self.assertIsNone(body['message'])
