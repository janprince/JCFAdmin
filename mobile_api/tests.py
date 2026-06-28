from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from causes.models import Cause, Donation
from members.models import Contact
from teachings.models import Teaching, TeachingSeries
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
        # Code is delivered by email.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['member@example.com'])
        self.assertIn(resp.data['dev_code'], mail.outbox[0].body)

    def test_phone_identifier_still_emails_the_code(self):
        resp = self._request_code('+233200000000')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('dev_code', resp.data)
        # Even when identifying by phone, the code goes to the email on file.
        self.assertEqual(mail.outbox[0].to, ['member@example.com'])

    def test_contact_without_email_gets_no_code(self):
        Contact.objects.create(
            full_name='No Email', phone='+233200000099', is_active=True, is_member=True,
        )
        resp = self._request_code('+233200000099')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('dev_code', resp.data)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(LoginCode.objects.count(), 0)

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


class ContentTierTests(APITestCase):
    def setUp(self):
        self.series = TeachingSeries.objects.create(title='Foundations')
        self.general = Teaching.objects.create(
            topic='Intro to Meditation',
            status=Teaching.Status.PUBLISHED,
            tier=Teaching.Tier.GENERAL,
            youtube_url='https://youtu.be/general',
            series=self.series,
        )
        self.premium = Teaching.objects.create(
            topic='Advanced InnerSpace',
            status=Teaching.Status.PUBLISHED,
            tier=Teaching.Tier.PREMIUM,
            youtube_url='https://youtu.be/premium',
            series=self.series,
        )
        self.draft = Teaching.objects.create(
            topic='Unpublished Draft', status=Teaching.Status.PENDING,
        )
        self.member = Contact.objects.create(
            full_name='Member', phone='+233200000001',
            email='m@example.com', is_active=True, is_member=True,
        )

    def _member_auth(self):
        token = MobileToken.issue(self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def test_guest_list_shows_premium_as_locked_and_hides_drafts(self):
        resp = self.client.get(reverse('mobile_api:teaching_list'))
        self.assertEqual(resp.status_code, 200)
        by_slug = {t['slug']: t for t in resp.data['results']}
        self.assertNotIn('unpublished-draft', by_slug)  # drafts excluded
        self.assertFalse(by_slug['intro-to-meditation']['is_locked'])
        self.assertTrue(by_slug['advanced-innerspace']['is_locked'])

    def test_guest_can_open_general_but_not_premium(self):
        ok = self.client.get(
            reverse('mobile_api:teaching_detail', args=['intro-to-meditation'])
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data['youtube_url'], 'https://youtu.be/general')

        denied = self.client.get(
            reverse('mobile_api:teaching_detail', args=['advanced-innerspace'])
        )
        self.assertEqual(denied.status_code, 403)

    def test_member_can_open_premium(self):
        resp = self.client.get(
            reverse('mobile_api:teaching_detail', args=['advanced-innerspace']),
            **self._member_auth(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['youtube_url'], 'https://youtu.be/premium')

    def test_member_list_unlocks_premium(self):
        resp = self.client.get(reverse('mobile_api:teaching_list'), **self._member_auth())
        by_slug = {t['slug']: t for t in resp.data['results']}
        self.assertFalse(by_slug['advanced-innerspace']['is_locked'])

    def test_series_detail_lists_published_teachings(self):
        resp = self.client.get(reverse('mobile_api:series_detail', args=['foundations']))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['teaching_count'], 2)
        self.assertEqual(len(resp.data['teachings']), 2)


_FAKE_TX = {
    'amount': 5000,  # pesewas -> GHS 50.00
    'currency': 'GHS',
    'customer': {'email': 'donor@example.com', 'first_name': 'Ama'},
    'paid_at': None,
}


class DonationTests(APITestCase):
    def setUp(self):
        self.cause = Cause.objects.create(
            title='Build a Centre', description='d', content='c',
            goal_amount=10000, is_active=True,
        )
        self.member = Contact.objects.create(
            full_name='Giver', phone='+233200000050',
            email='giver@example.com', is_active=True, is_member=True,
        )

    @override_settings(PAYSTACK_PUBLIC_KEY='pk_test_abc')
    def test_payment_config_returns_public_key(self):
        resp = self.client.get(reverse('mobile_api:payment_config'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['paystack_public_key'], 'pk_test_abc')
        self.assertEqual(resp.data['currency'], 'GHS')

    def test_cause_list(self):
        resp = self.client.get(reverse('mobile_api:cause_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'][0]['slug'], 'build-a-centre')

    @patch('mobile_api.payments.verify_transaction', return_value=_FAKE_TX)
    def test_guest_donation_verify_creates_donation(self, _mock):
        resp = self.client.post(
            reverse('mobile_api:donation_verify'),
            {'reference': 'JCF-REF-1', 'cause_id': self.cause.id},
        )
        self.assertEqual(resp.status_code, 201)
        d = Donation.objects.get(paystack_reference='JCF-REF-1')
        self.assertEqual(str(d.amount), '50.00')
        self.assertEqual(d.cause, self.cause)
        self.assertIsNone(d.contact)

    @patch('mobile_api.payments.verify_transaction', return_value=_FAKE_TX)
    def test_donation_verify_is_idempotent(self, _mock):
        url = reverse('mobile_api:donation_verify')
        self.client.post(url, {'reference': 'JCF-REF-2'})
        resp = self.client.post(url, {'reference': 'JCF-REF-2'})
        self.assertEqual(resp.data['status'], 'already_processed')
        self.assertEqual(Donation.objects.filter(paystack_reference='JCF-REF-2').count(), 1)

    @patch('mobile_api.payments.verify_transaction', return_value=None)
    def test_donation_verify_failure(self, _mock):
        resp = self.client.post(
            reverse('mobile_api:donation_verify'), {'reference': 'bad'}
        )
        self.assertEqual(resp.status_code, 400)

    @patch('mobile_api.payments.verify_transaction', return_value=_FAKE_TX)
    def test_member_donation_is_attributed_and_listed(self, _mock):
        token = MobileToken.issue(self.member)
        auth = {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}
        self.client.post(
            reverse('mobile_api:donation_verify'),
            {'reference': 'JCF-REF-3', 'cause_id': self.cause.id}, **auth,
        )
        d = Donation.objects.get(paystack_reference='JCF-REF-3')
        self.assertEqual(d.contact, self.member)
        self.assertEqual(d.donor_name, 'Giver')

        mine = self.client.get(reverse('mobile_api:my_donations'), **auth)
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(len(mine.data['results']), 1)

    def test_my_donations_requires_auth(self):
        self.assertEqual(
            self.client.get(reverse('mobile_api:my_donations')).status_code, 401
        )
