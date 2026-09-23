from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, RequestFactory
from django.urls import reverse, resolve, get_resolver, URLResolver

from accounts.access import areas_for, area_for_route
from accounts.models import Profile, PortalAccessEvent
from dashboard.navigation import navigation_for
from members.models import Contact
from staff_mgmt.models import Worker
from website.models import ContactSubmission

User = get_user_model()
PASSWORD = 'Cedar!River-93847'
NEW_PASSWORD = 'Meadow!Stone-57283'


class PortalAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in Profile.Role.values:
            user = User.objects.create_user(username=role, email=f'{role}@example.com', password=PASSWORD, first_name=role)
            user.profile.role = role
            user.profile.save()
            cls.users[role] = user
        cls.root = User.objects.create_superuser(username='root', email='root@example.com', password=PASSWORD)
        cls.target = User.objects.create_user(username='target', email='target@example.com', password=PASSWORD, first_name='Target')
        cls.contact = Contact.objects.create(full_name='Sample Worker', email='worker@example.com')
        cls.worker = Worker.objects.create(contact=cls.contact, role='Coordinator', salary=100)
        cls.message = ContactSubmission.objects.create(name='Private Sender', email='private@example.com', subject='Private enquiry', message='Private body')

    def setUp(self):
        self.client.force_login(self.users['admin'])

    def data(self, **overrides):
        data = dict(first_name='New', last_name='Person', email='new@example.com', role='secretary', worker='', password1=PASSWORD, password2=PASSWORD)
        data.update(overrides)
        return data

    def test_only_admin_can_manage_accounts_for_get_and_post(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            allowed = role == 'admin'
            self.assertEqual(self.client.get(reverse('staff:user_list')).status_code, 200 if allowed else 403)
            if not allowed:
                self.assertEqual(self.client.post(reverse('staff:user_create'), self.data()).status_code, 403)
                self.assertEqual(self.client.post(reverse('staff:user_password', args=[self.target.pk]), {}).status_code, 403)
        self.assertFalse(User.objects.filter(email='new@example.com').exists())

    def test_create_links_worker_sets_role_hash_and_first_login_without_superuser_flags(self):
        response = self.client.post(reverse('staff:user_create'), self.data(worker=self.worker.pk, is_superuser='on', is_staff='on', is_active='off'))
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='new@example.com')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.profile.worker_id, self.worker.pk)
        self.assertEqual(user.profile.role, 'secretary')
        self.assertEqual(user.access_events.get().action, 'Account created')
        self.assertNotIn(PASSWORD, str(list(user.access_events.values())))

    def test_password_validation_duplicate_email_and_duplicate_staff_link(self):
        response = self.client.post(reverse('staff:user_create'), self.data(password1='password', password2='password'))
        self.assertContains(response, 'too common')
        self.assertFalse(User.objects.filter(email='new@example.com').exists())
        response = self.client.post(reverse('staff:user_create'), self.data(email='TARGET@EXAMPLE.COM'))
        self.assertContains(response, 'already uses this email')
        self.target.profile.worker = self.worker
        self.target.profile.save()
        response = self.client.post(reverse('staff:user_create'), self.data(worker=self.worker.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn('worker', response.context['form'].errors)
        self.assertFalse(User.objects.filter(email='new@example.com').exists())

    def test_initial_password_cannot_bypass_setup_and_new_password_keeps_session(self):
        self.target.must_change_password = True
        self.target.save()
        browser = Client()
        self.assertTrue(browser.login(username='TARGET@EXAMPLE.COM', password=PASSWORD))
        for url in ['/dashboard/', '/contacts/', '/staff/access/', '/admin/']:
            self.assertRedirects(browser.get(url), reverse('accounts:password_change'), fetch_redirect_response=False)
        response = browser.post(reverse('accounts:password_change'), {'old_password':PASSWORD, 'new_password1':PASSWORD, 'new_password2':PASSWORD})
        self.assertContains(response, 'Choose a different password')
        response = browser.post(reverse('accounts:password_change'), {'old_password':PASSWORD, 'new_password1':NEW_PASSWORD, 'new_password2':NEW_PASSWORD})
        self.assertRedirects(response, '/dashboard/')
        self.target.refresh_from_db()
        self.assertFalse(self.target.must_change_password)
        self.assertTrue(self.target.check_password(NEW_PASSWORD))
        self.assertEqual(browser.get('/contacts/').status_code, 200)
        self.assertFalse(Client().login(username='target@example.com', password=PASSWORD))

    def test_role_matrix_protects_direct_links_and_legacy_write_actions(self):
        routes = {'community':'members:contact_list', 'consultations':'consultations:consultation_list',
                  'staff':'staff:staff_list', 'accounts':'staff:user_list', 'giving':'causes:donation_list',
                  'publishing':'blog:post_list', 'content':'website:gallery_list', 'inbox':'website:contact_list'}
        for role, user in self.users.items():
            self.client.force_login(user)
            for area, route in routes.items():
                with self.subTest(role=role, area=area):
                    self.assertEqual(self.client.get(reverse(route)).status_code, 200 if area in areas_for(user) else 403)
        self.client.force_login(self.users['media_operations'])
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(reverse('website:contact_mark_read', args=[self.message.pk])).status_code, 403)
        self.message.refresh_from_db()
        self.assertFalse(self.message.is_read)

    def test_dashboard_and_navigation_do_not_expose_restricted_data(self):
        for role in ['secretary', 'media_operations']:
            user = self.users[role]
            self.client.force_login(user)
            response = self.client.get('/dashboard/')
            self.assertNotContains(response, 'Giving this month')
            self.assertNotIn('giving_by_currency', response.context)
            if role == 'media_operations':
                self.assertNotIn('recent_contacts', response.context)
                self.assertNotContains(response, 'Recently welcomed')
                self.assertNotContains(response, 'Private Sender')
            request = RequestFactory().get('/dashboard/')
            request.user = user; request.resolver_match = resolve(request.path)
            links = [link['url'] for group in navigation_for(request) for link in group['links']]
            self.assertNotIn('/staff/access/', links)
            self.assertNotIn('/causes/donations/', links)

    def test_role_change_revokes_sessions_and_cannot_be_overridden_by_django_permissions(self):
        browser = Client(); browser.force_login(self.target)
        response = self.client.post(reverse('staff:user_update', args=[self.target.pk]), self.data(email=self.target.email, role='media_operations'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(browser.get('/contacts/').status_code, 302)
        self.target.refresh_from_db()
        self.target.user_permissions.add(Permission.objects.get(codename='view_worker'))
        browser.force_login(self.target)
        self.assertEqual(browser.get('/staff/').status_code, 403)
        self.assertEqual(browser.get('/contacts/').status_code, 403)
        self.assertEqual(browser.get('/events/').status_code, 200)

    def test_deactivate_and_reactivate_never_revives_an_old_session(self):
        browser = Client(); browser.force_login(self.target)
        old_cookies = browser.cookies.copy()
        url = reverse('staff:user_deactivate', args=[self.target.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.target.refresh_from_db(); self.assertTrue(self.target.is_active)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Client().login(username=self.target.email, password=PASSWORD))
        self.client.post(reverse('staff:user_activate', args=[self.target.pk]))
        browser.cookies = old_cookies
        self.assertEqual(browser.get('/contacts/').status_code, 302)
        self.assertTrue(Client().login(username=self.target.email, password=PASSWORD))

    def test_admin_cannot_lock_themselves_out_or_modify_system_admin(self):
        admin = self.users['admin']
        response = self.client.post(reverse('staff:user_update', args=[admin.pk]), self.data(email=admin.email, role='secretary'))
        self.assertContains(response, 'Ask another Admin')
        for route in ['staff:user_deactivate', 'staff:user_password']:
            self.assertEqual(self.client.post(reverse(route, args=[admin.pk]), {}).status_code, 403)
        for route in ['staff:user_update', 'staff:user_deactivate', 'staff:user_password']:
            self.assertEqual(self.client.post(reverse(route, args=[self.root.pk]), {}).status_code, 403)
        admin.profile.refresh_from_db(); self.assertEqual(admin.profile.role, 'admin')

    def test_reset_initial_password_revokes_sessions_and_forces_setup(self):
        browser = Client(); browser.force_login(self.target)
        response = self.client.post(reverse('staff:user_password', args=[self.target.pk]), {'new_password1':NEW_PASSWORD, 'new_password2':NEW_PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(browser.get('/dashboard/').status_code, 302)
        self.target.refresh_from_db(); self.assertTrue(self.target.must_change_password)
        self.assertTrue(self.target.check_password(NEW_PASSWORD))
        self.assertEqual(self.target.access_events.first().action, 'Initial password reset')
        self.assertTrue(browser.login(username=self.target.email, password=NEW_PASSWORD))
        self.assertRedirects(browser.get('/dashboard/'), reverse('accounts:password_change'))

    def test_unknown_role_denied_and_django_admin_is_separate(self):
        self.target.profile.role = 'unknown'; self.target.profile.save()
        self.client.force_login(self.target)
        self.assertEqual(self.client.get('/dashboard/').status_code, 403)
        for role, user in self.users.items():
            self.client.force_login(user)
            self.assertEqual(self.client.get('/admin/').status_code, 403)
        self.client.force_login(self.root)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_inner_space_permission_follows_roles(self):
        for role, user in self.users.items():
            self.assertEqual(user.has_perm('innerspace.manage_innerspace_access'), role in {'admin','administrator'})
        self.client.force_login(self.users['secretary'])
        self.assertEqual(self.client.get('/innerspace/students/').status_code, 403)

    def test_every_existing_portal_route_has_a_policy(self):
        def walk(patterns, namespace=''):
            for pattern in patterns:
                if isinstance(pattern, URLResolver):
                    yield from walk(pattern.url_patterns, pattern.namespace or namespace)
                else:
                    yield namespace, pattern.name
        for namespace, name in walk(get_resolver().url_patterns):
            if namespace in {'members','centres','consultations','staff','website','teachings','events','blog','causes','innerspace'}:
                self.assertIsNotNone(area_for_route(namespace, name or ''), (namespace,name))

    def test_public_api_stays_public_and_csrf_protects_account_actions(self):
        self.assertEqual(Client().get('/api/events/').status_code, 200)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.users['admin'])
        self.assertEqual(csrf.post(reverse('staff:user_deactivate', args=[self.target.pk])).status_code, 403)
        self.assertEqual(csrf.post(reverse('staff:user_create'), self.data()).status_code, 403)

    def test_staff_setup_prefills_person_and_account_pages_are_not_cached(self):
        response = self.client.get(reverse('staff:user_create'), {'worker':self.worker.pk})
        self.assertEqual(response.context['form'].initial['email'], self.contact.email)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertContains(self.client.get(reverse('staff:staff_list')), 'Set up access')
