from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from accounts.models import Profile
from dashboard.navigation import navigation_for
from .models import DigitalResource

User = get_user_model()


class DigitalResourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in Profile.Role.values:
            user = User.objects.create_user(username=role, email=f'{role}@example.com', password='x', first_name=role)
            user.profile.role = role
            user.profile.save()
            cls.users[role] = user
        cls.hidden = DigitalResource.objects.create(title='Old playlist', url='https://vimeo.com/showcase/1', is_active=False)

    def test_migration_seeds_the_two_main_platforms(self):
        urls = set(DigitalResource.objects.filter(is_active=True).values_list('url', flat=True))
        self.assertEqual(urls, {'https://www.drbaffourjan.com', 'https://www.jancosmicfoundation.org'})

    def test_every_role_can_open_and_copy_but_only_content_managers_edit(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            manages = role in ('admin', 'administrator', 'media_operations')
            with self.subTest(role=role):
                response = self.client.get(reverse('resources:resource_list'))
                self.assertContains(response, 'data-copy="https://www.drbaffourjan.com"')
                self.assertEqual(response.context['can_manage'], manages)
                self.assertEqual(self.hidden in response.context['archived'], manages)
                self.assertNotIn(self.hidden, [r for g in response.context['groups'] for r in g['items']])
                self.assertEqual(self.client.get(reverse('resources:resource_update', args=[self.hidden.pk])).status_code, 200 if manages else 403)
                self.assertEqual(self.client.post(reverse('resources:resource_delete', args=[self.hidden.pk])).status_code, 403 if not manages else 302)
                if manages:
                    self.hidden.save()  # Put it back for the next role.

    def test_add_link_accepts_www_addresses_and_shows_it(self):
        self.client.force_login(self.users['media_operations'])
        response = self.client.post(reverse('resources:resource_create'), {
            'title': 'Intermediate Lessons (Twi)', 'url': 'www.vimeo.com/showcase/123', 'category': 'lessons',
            'audience': 'students', 'language': 'Twi', 'share_privately': 'on'})
        self.assertRedirects(response, reverse('resources:resource_list'))
        link = DigitalResource.objects.get(title='Intermediate Lessons (Twi)')
        self.assertTrue(link.is_active)
        self.assertEqual(link.url, 'https://www.vimeo.com/showcase/123')
        self.assertEqual(link.display_url, 'www.vimeo.com/showcase/123')
        self.assertContains(self.client.get(reverse('resources:resource_list')), 'Share privately')

    def test_invalid_link_reopens_the_add_modal(self):
        self.client.force_login(self.users['administrator'])
        response = self.client.post(reverse('resources:resource_create'), {'title': '', 'url': 'not a link', 'category': 'other', 'audience': 'everyone'})
        self.assertContains(response, 'data-jcf-open')
        self.assertIn('url', response.context['form'].errors)

    def test_secretary_cannot_add_links(self):
        self.client.force_login(self.users['secretary'])
        response = self.client.post(reverse('resources:resource_create'), {'title': 'X', 'url': 'https://example.com', 'category': 'other', 'audience': 'everyone'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(DigitalResource.objects.filter(title='X').exists())

    def test_sidebar_offers_resources_to_every_role(self):
        for user in self.users.values():
            request = RequestFactory().get(reverse('resources:resource_list'))
            request.user = user
            request.resolver_match = resolve(request.path)
            groups = navigation_for(request)
            self.assertTrue(next(g for g in groups if g['label'] == 'Digital resources')['active'])
