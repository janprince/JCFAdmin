"""Daily Inspiration detail: public to read, members-only to save/reflect."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from engagement.models import (DailyInspiration, InspirationBlock,
                               InspirationReflection, InspirationSave)
from members.models import Contact

from .models import MobileToken


def url(identifier, suffix=''):
    return f'/api/mobile/v1/inspirations/{identifier}/{suffix}'


class InspirationDetailTests(APITestCase):
    def setUp(self):
        today = timezone.localdate()
        self.inspiration = DailyInspiration.objects.create(
            date=today,
            title='Freedom begins with awareness',
            quote='Freedom begins when awareness becomes your way of living.',
            author='Dr. Baffour Jan',
            category='Awareness',
            prompt_question='Where are you reacting automatically?',
            prompt_guidance='Sit with this for a moment.',
        )
        InspirationBlock.objects.create(
            inspiration=self.inspiration, block_type='paragraph',
            text='Awareness is not a technique. ' * 30, order=1)
        InspirationBlock.objects.create(
            inspiration=self.inspiration, block_type='pull_quote',
            text='Notice, and you are already free.', source='Dr. Baffour Jan',
            order=2)
        self.older = DailyInspiration.objects.create(
            date=today - timedelta(days=1), quote='Stillness speaks.')
        self.member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000061',
            email='ama-insp@example.com', is_active=True, is_member=True)

    def _auth(self):
        token = MobileToken.issue(self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    # --- reading is public ---

    def test_guest_can_read_a_shared_link(self):
        res = self.client.get(url(self.inspiration.slug))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['title'], 'Freedom begins with awareness')
        self.assertEqual(res.data['category'], 'Awareness')
        self.assertFalse(res.data['saved'])
        self.assertFalse(res.data['reflected'])

    def test_lookup_works_by_id_and_by_slug(self):
        by_id = self.client.get(url(self.inspiration.id))
        by_slug = self.client.get(url(self.inspiration.slug))
        self.assertEqual(by_id.data['slug'], by_slug.data['slug'])

    def test_removed_content_returns_404(self):
        self.assertEqual(self.client.get(url('no-such-slug')).status_code, 404)

    def test_unpublished_and_future_entries_are_hidden(self):
        future = DailyInspiration.objects.create(
            date=timezone.localdate() + timedelta(days=3), quote='Tomorrow.')
        draft = DailyInspiration.objects.create(
            date=timezone.localdate() - timedelta(days=9), quote='Draft.',
            is_published=False)
        self.assertEqual(self.client.get(url(future.slug)).status_code, 404)
        self.assertEqual(self.client.get(url(draft.slug)).status_code, 404)

    # --- content shape ---

    def test_body_blocks_are_structured_and_ordered(self):
        res = self.client.get(url(self.inspiration.slug))
        kinds = [b['type'] for b in res.data['body_blocks']]
        self.assertEqual(kinds, ['paragraph', 'pull_quote'])
        self.assertEqual(res.data['body_blocks'][1]['source'],
                         'Dr. Baffour Jan')

    def test_reading_time_is_computed_and_never_zero(self):
        res = self.client.get(url(self.inspiration.slug))
        self.assertGreaterEqual(res.data['reading_time_minutes'], 1)
        bare = self.client.get(url(self.older.slug))
        self.assertEqual(bare.data['reading_time_minutes'], 1)

    def test_share_excerpt_falls_back_to_the_quote(self):
        res = self.client.get(url(self.older.slug))
        self.assertEqual(res.data['share_excerpt'], 'Stillness speaks.')

    def test_canonical_url_is_https_and_slug_based(self):
        res = self.client.get(url(self.inspiration.slug))
        canonical = res.data['canonical_url']
        self.assertTrue(canonical.startswith('https://'))
        self.assertTrue(canonical.endswith(self.inspiration.slug))

    def test_prompt_is_absent_when_nothing_was_authored(self):
        res = self.client.get(url(self.older.slug))
        self.assertIsNone(res.data['reflection_prompt'])

    def test_audio_is_absent_unless_a_source_exists(self):
        res = self.client.get(url(self.inspiration.slug))
        self.assertIsNone(res.data['audio'])
        self.inspiration.audio_url = 'https://cdn.example.com/a.mp3'
        self.inspiration.save()
        res = self.client.get(url(self.inspiration.slug))
        self.assertEqual(res.data['audio']['url'],
                         'https://cdn.example.com/a.mp3')

    # --- related / neighbours ---

    def test_related_excludes_the_current_entry(self):
        res = self.client.get(url(self.inspiration.slug))
        slugs = [r['slug'] for r in res.data['related_inspirations']]
        self.assertNotIn(self.inspiration.slug, slugs)
        self.assertIn(self.older.slug, slugs)

    def test_previous_and_next_come_from_the_server(self):
        res = self.client.get(url(self.inspiration.slug))
        self.assertEqual(res.data['previous_inspiration']['slug'],
                         self.older.slug)
        self.assertIsNone(res.data['next_inspiration'])

        res = self.client.get(url(self.older.slug))
        self.assertEqual(res.data['next_inspiration']['slug'],
                         self.inspiration.slug)
        self.assertIsNone(res.data['previous_inspiration'])

    # --- member actions ---

    def test_guest_cannot_save_or_reflect(self):
        self.assertEqual(
            self.client.post(url(self.inspiration.slug, 'save/')).status_code,
            401)
        self.assertEqual(
            self.client.post(
                url(self.inspiration.slug, 'reflection/')).status_code, 401)

    def test_member_save_and_unsave(self):
        auth = self._auth()
        res = self.client.post(url(self.inspiration.slug, 'save/'), **auth)
        self.assertEqual(res.status_code, 201)
        # Saving twice stays saved rather than erroring.
        self.client.post(url(self.inspiration.slug, 'save/'), **auth)
        self.assertEqual(InspirationSave.objects.count(), 1)

        detail = self.client.get(url(self.inspiration.slug), **auth)
        self.assertTrue(detail.data['saved'])

        res = self.client.delete(url(self.inspiration.slug, 'save/'), **auth)
        self.assertFalse(res.data['saved'])
        self.assertEqual(InspirationSave.objects.count(), 0)

    def test_member_reflect_and_undo(self):
        auth = self._auth()
        res = self.client.post(
            url(self.inspiration.slug, 'reflection/'), **auth)
        self.assertEqual(res.status_code, 201)
        self.assertIsNotNone(res.data['reflected_at'])

        detail = self.client.get(url(self.inspiration.slug), **auth)
        self.assertTrue(detail.data['reflected'])
        self.assertEqual(detail.data['reflection_prompt']['status'],
                         'reflected')

        self.client.delete(url(self.inspiration.slug, 'reflection/'), **auth)
        self.assertEqual(InspirationReflection.objects.count(), 0)

    def test_saved_state_shows_on_related_cards(self):
        auth = self._auth()
        self.client.post(url(self.older.slug, 'save/'), **auth)
        res = self.client.get(url(self.inspiration.slug), **auth)
        related = {r['slug']: r['saved']
                   for r in res.data['related_inspirations']}
        self.assertTrue(related[self.older.slug])


class InspirationShareDataTests(APITestCase):
    def setUp(self):
        self.inspiration = DailyInspiration.objects.create(
            date=timezone.localdate(),
            title='Freedom begins with awareness',
            quote='Freedom begins when awareness becomes your way of living.',
            category='Awareness',
        )

    def test_guest_can_fetch_share_data(self):
        res = self.client.get(url(self.inspiration.slug, 'share-data/'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['default_template_id'], 'cosmic')
        self.assertTrue(res.data['sharing_allowed'])
        self.assertTrue(res.data['canonical_url'].startswith('https://'))

    def test_only_cosmic_offers_the_story_format(self):
        res = self.client.get(url(self.inspiration.slug, 'share-data/'))
        story = [t['id'] for t in res.data['templates']
                 if 'story' in t['formats']]
        self.assertEqual(story, ['cosmic'])

    def test_a_long_excerpt_is_trimmed_on_a_word_boundary(self):
        self.inspiration.share_excerpt = 'Awareness is the doorway. ' * 20
        self.inspiration.save()
        res = self.client.get(url(self.inspiration.slug, 'share-data/'))
        excerpt = res.data['share_excerpt']
        self.assertLessEqual(len(excerpt), 221)
        self.assertTrue(excerpt.endswith('…'))
        self.assertNotIn('  ', excerpt)

    def test_sharing_can_be_prohibited(self):
        self.inspiration.sharing_allowed = False
        self.inspiration.save()
        res = self.client.get(url(self.inspiration.slug, 'share-data/'))
        self.assertFalse(res.data['sharing_allowed'])

    def test_removed_inspiration_returns_404(self):
        res = self.client.get(url('gone', 'share-data/'))
        self.assertEqual(res.status_code, 404)
