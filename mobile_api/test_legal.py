"""Legal document endpoint (owner spec, welcome screen)."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from engagement.models import LegalDocument


def publish(kind='terms', language='en', version='1.0', **kwargs):
    kwargs.setdefault('title', 'Terms of Use')
    kwargs.setdefault('body', 'Authored by the foundation.')
    kwargs.setdefault('is_published', True)
    kwargs.setdefault('effective_from', timezone.now() - timedelta(days=1))
    return LegalDocument.objects.create(
        kind=kind, language=language, version=version, **kwargs)


class LegalDocumentTests(TestCase):
    def url(self, kind='terms'):
        return f'/api/mobile/v1/legal/{kind}/'

    def test_a_guest_may_read_the_terms(self):
        """Someone has to be able to read what they are agreeing to
        before they have agreed to anything."""
        publish()
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['published'])

    def test_the_payload_carries_the_version(self):
        publish(version='2026-09')
        body = self.client.get(self.url()).json()
        self.assertEqual(body['version'], '2026-09')
        self.assertEqual(body['body'], 'Authored by the foundation.')

    def test_privacy_is_a_separate_document(self):
        publish(kind='privacy', title='Privacy Policy', body='Ours.')
        body = self.client.get(self.url('privacy')).json()
        self.assertEqual(body['kind'], 'privacy')
        self.assertEqual(body['title'], 'Privacy Policy')

    def test_an_unknown_kind_is_404(self):
        self.assertEqual(self.client.get(self.url('cookies')).status_code,
                         404)

    def test_nothing_published_says_so_rather_than_inventing_text(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['published'])

    def test_a_draft_is_not_served(self):
        publish(is_published=False)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_a_future_document_is_not_yet_in_force(self):
        publish(effective_from=timezone.now() + timedelta(days=7))
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_the_newest_effective_version_wins(self):
        publish(version='1.0',
                effective_from=timezone.now() - timedelta(days=30))
        publish(version='2.0',
                effective_from=timezone.now() - timedelta(days=1))
        self.assertEqual(
            self.client.get(self.url()).json()['version'], '2.0')

    def test_a_translation_is_served_when_it_exists(self):
        publish(language='en', version='1.0')
        publish(language='fr', version='1.0', title='Conditions')
        body = self.client.get(
            self.url(), HTTP_ACCEPT_LANGUAGE='fr').json()
        self.assertEqual(body['language'], 'fr')
        self.assertFalse(body['language_fallback'])

    def test_an_unauthored_translation_falls_back_to_english(self):
        """The English text is still the agreement; showing nothing would
        be worse than showing it in the wrong language."""
        publish(language='en', version='1.0')
        body = self.client.get(
            self.url(), HTTP_ACCEPT_LANGUAGE='de-DE,de').json()
        self.assertEqual(body['language'], 'en')
        self.assertTrue(body['language_fallback'])
