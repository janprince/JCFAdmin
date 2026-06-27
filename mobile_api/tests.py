from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from members.models import Contact
from .models import LoginCode, MobileToken


@override_settings(DEBUG=True)  # so request-code returns dev_code for the flow
class AuthFlowTests(APITestCase):
    def setUp(self):
        self.contact = Contact.objects.create(
            full_name='Test Member',
            phone='+233200000000',
            email='member@example.com',
            is_active=True,
            is_member=True,
        )

    def _request_code(self, identifier):
        return self.client.post(
            reverse('mobile_api:request_code'), {'identifier': identifier}
        )

    def test_request_code_for_known_email_sends_code(self):
        resp = self._request_code('member@example.com')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('dev_code', resp.data)
        self.assertEqual(LoginCode.objects.filter(contact=self.contact).count(), 1)

    def test_request_code_for_unknown_identifier_is_generic_and_silent(self):
        resp = self._request_code('nobody@example.com')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('dev_code', resp.data)
        self.assertEqual(LoginCode.objects.count(), 0)

    def test_full_login_flow(self):
        code = self._request_code('member@example.com').data['dev_code']
        verify = self.client.post(
            reverse('mobile_api:verify_code'),
            {'identifier': 'member@example.com', 'code': code},
        )
        self.assertEqual(verify.status_code, 200)
        self.assertIn('access', verify.data)
        self.assertIn('refresh', verify.data)
        self.assertEqual(verify.data['member']['full_name'], 'Test Member')

        access = verify.data['access']
        me = self.client.get(
            reverse('mobile_api:me'), HTTP_AUTHORIZATION=f'Bearer {access}'
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['email'], 'member@example.com')

    def test_wrong_code_is_rejected_and_counts_attempt(self):
        self._request_code('member@example.com')
        resp = self.client.post(
            reverse('mobile_api:verify_code'),
            {'identifier': 'member@example.com', 'code': '000000'},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LoginCode.objects.get().attempts, 1)

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get(reverse('mobile_api:me')).status_code, 401)

    def test_refresh_rotates_access(self):
        code = self._request_code('member@example.com').data['dev_code']
        tokens = self.client.post(
            reverse('mobile_api:verify_code'),
            {'identifier': 'member@example.com', 'code': code},
        ).data
        resp = self.client.post(
            reverse('mobile_api:refresh'), {'refresh': tokens['refresh']}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.data['access'], tokens['access'])

    def test_phone_login_matches_contact(self):
        resp = self._request_code('+233200000000')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('dev_code', resp.data)

    def test_logout_revokes_token(self):
        code = self._request_code('member@example.com').data['dev_code']
        access = self.client.post(
            reverse('mobile_api:verify_code'),
            {'identifier': 'member@example.com', 'code': code},
        ).data['access']
        auth = {'HTTP_AUTHORIZATION': f'Bearer {access}'}
        self.assertEqual(self.client.delete(reverse('mobile_api:me'), **auth).status_code, 204)
        # token now revoked -> 401
        self.assertEqual(self.client.get(reverse('mobile_api:me'), **auth).status_code, 401)
        self.assertTrue(MobileToken.objects.get().revoked)
