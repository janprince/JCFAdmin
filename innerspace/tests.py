"""Inner Space pages against a stand-in for drbaffourjan.com's office API."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .client import InnerspaceClient, InnerspaceUnavailable
from .models import AccessGrantLog

User = get_user_model()
API = 'https://platform.test'


def student(**overrides):
    data = {'id': 'cstudent1', 'email': 'esi@example.org', 'emailVerified': None, 'phone': None, 'firstName': 'Esi',
            'lastName': 'Mensah', 'name': None, 'accessLevel': 'BEGINNER', 'country': 'Ghana',
            'hasCompletedOnboarding': True, 'createdAt': '2026-10-01T10:00:00Z', 'membership': None}
    data.update(overrides)
    return data


def membership(**overrides):
    data = {'id': 'm1', 'status': 'ACTIVE', 'startedAt': '2026-10-07T12:00:00Z', 'expiresAt': '2027-01-07T12:00:00Z',
            'provider': 'CASH', 'providerRef': 'CASH-R-9', 'isActive': True}
    data.update(overrides)
    return data


# The student page, for tests that follow the redirect after a change.
DETAIL = {('GET', 'students/cstudent1'): (200, {'student': student(), 'payments': [], 'accessRequests': []})}


class Reply:
    def __init__(self, status, body, headers=None):
        self.status_code, self.body, self.headers = status, body, headers or {}
        self.ok = status < 400

    def json(self):
        return self.body


class FakePlatform:
    """Answers like the office API and remembers what it was sent."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, params=None, json=None, timeout=None, headers=None, allow_redirects=True):
        assert allow_redirects is False, 'the client must never follow redirects'
        path = url.split('/api/jcf/v1/', 1)[1]
        self.calls.append({'method': method, 'path': path, 'params': params, 'json': json, 'headers': headers})
        status, body, *headers = self.routes[(method, path)]
        if isinstance(body, Exception):
            raise body
        return Reply(status, body, *headers)


@override_settings(INNERSPACE_API_URL=API, INNERSPACE_API_KEY='office-key',
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class InnerspacePagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in ('admin', 'administrator', 'secretary', 'media_operations'):
            user = User.objects.create_user(username=role, email=f'{role}@jcf.org', password='x', first_name=role)
            user.profile.role = role
            user.profile.save()
            cls.users[role] = user

    def setUp(self):
        self.client.force_login(self.users['administrator'])

    def platform(self, routes):
        fake = FakePlatform(routes)
        patcher = patch('innerspace.client.requests.Session', return_value=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def test_pages_explain_when_the_platform_is_not_configured(self):
        with override_settings(INNERSPACE_API_KEY=''):
            response = self.client.get(reverse('innerspace:student_list'))
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'not configured', status_code=503)

    def test_list_sends_filters_and_pages_over_the_platform_total(self):
        fake = self.platform({('GET', 'students'): (200, {
            'results': [student()], 'count': 120, 'page': 2, 'pageSize': 50,
            'totals': {'students': 120, 'active': 70, 'lapsed': 20, 'none': 30, 'pendingRequests': 4}})})
        response = self.client.get(reverse('innerspace:student_list'), {'q': 'esi', 'access': 'active', 'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake.calls[0]['params'], {'q': 'esi', 'access': 'active', 'page': 2, 'pageSize': 50})
        self.assertEqual(fake.calls[0]['headers']['Authorization'], 'Bearer office-key')
        self.assertEqual(response.context['page_obj'].paginator.num_pages, 3)
        self.assertEqual(response.context['pending_requests'], 4)
        self.assertContains(response, 'esi@example.org')

    def test_unknown_student_is_a_404(self):
        self.platform({('GET', 'students/nope'): (404, {'error': {'code': 'NOT_FOUND', 'message': 'No student has that id.'}})})
        self.assertEqual(self.client.get(reverse('innerspace:student_detail', args=['nope'])).status_code, 404)

    def test_outage_shows_the_unavailable_page(self):
        import requests
        self.platform({('GET', 'students'): (0, requests.ConnectionError('down'))})
        response = self.client.get(reverse('innerspace:student_list'))
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'Could not reach drbaffourjan.com', status_code=503)

    def test_grant_sends_the_change_and_logs_who_did_it(self):
        after = student(accessLevel='INTERMEDIATE', membership=membership())
        fake = self.platform({('POST', 'students/cstudent1/grant'): (200, {
            'action': 'grant', 'student': after, 'previousStatus': '', 'previousLevel': 'BEGINNER'})})
        response = self.client.post(reverse('innerspace:grant_access', args=['cstudent1']), {
            'duration': '3', 'amount': '450', 'currency': 'GHS', 'receipt_ref': 'R-9', 'access_level': 'INTERMEDIATE', 'note': 'Paid at the desk'})
        self.assertRedirects(response, reverse('innerspace:student_detail', args=['cstudent1']), fetch_redirect_response=False)
        body = fake.calls[0]['json']
        self.assertEqual(body['actor']['email'], 'administrator@jcf.org')
        self.assertEqual((body['months'], body['amount'], body['currency'], body['receiptRef'], body['accessLevel']),
                         (3, '450', 'GHS', 'R-9', 'INTERMEDIATE'))
        self.assertNotIn('expiresAt', body)
        entry = AccessGrantLog.objects.get()
        self.assertEqual((entry.action, entry.performed_by, entry.previous_level, entry.new_level, entry.new_status, entry.receipt_ref),
                         ('grant', self.users['administrator'], 'BEGINNER', 'INTERMEDIATE', 'ACTIVE', 'R-9'))
        self.assertEqual(str(entry.amount), '450.00')

    def test_lifetime_grant_sends_no_duration(self):
        fake = self.platform({('POST', 'students/cstudent1/grant'): (200, {
            'action': 'reactivate', 'student': student(membership=membership(expiresAt=None)), 'previousStatus': 'CANCELED', 'previousLevel': 'BEGINNER'})})
        self.client.post(reverse('innerspace:grant_access', args=['cstudent1']), {'duration': 'lifetime', 'currency': 'GHS'})
        body = fake.calls[0]['json']
        self.assertNotIn('months', body)
        self.assertNotIn('expiresAt', body)
        self.assertNotIn('amount', body)
        self.assertEqual(AccessGrantLog.objects.get().action, 'reactivate')

    def test_a_failed_change_leaves_no_audit_entry(self):
        import requests
        self.platform({('POST', 'students/cstudent1/revoke'): (0, requests.Timeout('slow')), **DETAIL})
        response = self.client.post(reverse('innerspace:revoke_access', args=['cstudent1']), {'note': 'x'}, follow=True)
        self.assertContains(response, 'Nothing was changed')
        self.assertFalse(AccessGrantLog.objects.exists())

    def test_refusals_are_shown_in_the_platforms_words(self):
        self.platform({('POST', 'students/cstudent1/extend'): (409, {'error': {'code': 'NO_MEMBERSHIP', 'message': 'This student has no membership to extend.'}}), **DETAIL})
        response = self.client.post(reverse('innerspace:extend_access', args=['cstudent1']), {'duration': '12', 'currency': 'GHS'}, follow=True)
        self.assertContains(response, 'This student has no membership to extend.')
        self.assertFalse(AccessGrantLog.objects.exists())

    def test_approving_logs_the_level_and_emails_the_student(self):
        decided = {'id': 'req1', 'requestedLevel': 'INTERMEDIATE', 'currentLevel': 'BEGINNER', 'courseId': None, 'courseSlug': 'the-map',
                   'message': 'Ready', 'status': 'APPROVED', 'reviewedAt': '2026-10-07T12:00:00Z', 'reviewedBy': 'administrator@jcf.org',
                   'reviewNote': 'Welcome', 'createdAt': '2026-10-05T12:00:00Z', 'student': student(accessLevel='INTERMEDIATE')}
        fake = self.platform({('POST', 'access-requests/req1/approve'): (200, {'request': decided, 'previousLevel': 'BEGINNER'})})
        response = self.client.post(reverse('innerspace:approve_request', args=['req1']), {'note': 'Welcome', 'next': 'https://evil.example/'})
        self.assertRedirects(response, reverse('innerspace:request_list'), fetch_redirect_response=False)
        self.assertEqual(fake.calls[0]['json']['note'], 'Welcome')
        entry = AccessGrantLog.objects.get()
        self.assertEqual((entry.action, entry.previous_level, entry.new_level), ('level_grant', 'BEGINNER', 'INTERMEDIATE'))
        self.assertEqual(mail.outbox[0].to, ['esi@example.org'])
        self.assertIn('/student/courses/the-map', mail.outbox[0].body)

    def test_roles_without_inner_space_cannot_change_anything(self):
        fake = self.platform({})
        for role in ('secretary', 'media_operations'):
            self.client.force_login(self.users[role])
            self.assertEqual(self.client.post(reverse('innerspace:revoke_access', args=['cstudent1'])).status_code, 403)
        self.assertEqual(fake.calls, [])


@override_settings(INNERSPACE_API_URL=API, INNERSPACE_API_KEY='wrong')
class ClientTests(TestCase):
    def test_a_rejected_key_is_reported_as_configuration(self):
        fake = FakePlatform({('GET', 'students'): (401, {'error': {'code': 'UNAUTHORISED', 'message': 'Missing or wrong office API key.'}})})
        with self.assertRaisesMessage(InnerspaceUnavailable, 'INNERSPACE_API_KEY'):
            InnerspaceClient(session=fake).students()

    def test_a_redirect_names_the_address_to_configure_instead_of_following_it(self):
        fake = FakePlatform({('GET', 'students'): (307, {}, {'Location': 'https://www.platform.test/api/jcf/v1/students'})})
        with self.assertRaisesMessage(InnerspaceUnavailable, 'Set INNERSPACE_API_URL to https://www.platform.test'):
            InnerspaceClient(session=fake).students()
        self.assertEqual(len(fake.calls), 1)
