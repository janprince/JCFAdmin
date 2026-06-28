from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from causes.models import Cause, Donation
from consultations.models import Consultation
from engagement.models import Announcement, DeviceToken, Notification
from members.models import Contact
from programs.models import AccommodationTier, CostLineItem, Program, Registration
from teachings.models import Teaching, TeachingSeries
from .models import LoginCode, MobileToken

# Keep media (QR codes) off R2/disk during tests.
_INMEM_STORAGE = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


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


@override_settings(STORAGES=_INMEM_STORAGE)
class ProgramTests(APITestCase):
    def setUp(self):
        self.member = Contact.objects.create(
            full_name='Member One', phone='+233200000060',
            email='member1@example.com', is_active=True, is_member=True,
        )
        self.nonmember = Contact.objects.create(
            full_name='Plain Contact', phone='+233200000061',
            email='plain@example.com', is_active=True,
        )

        self.public = Program.objects.create(
            title='Open Day', year=2026, audience=Program.Audience.PUBLIC,
            requires_payment=False, is_published=True,
        )
        self.retreat = Program.objects.create(
            title='Annual Retreat', year=2026, audience=Program.Audience.MEMBERS,
            requires_payment=True, is_published=True,
        )
        CostLineItem.objects.create(program=self.retreat, label='Registration', amount=400, unit=CostLineItem.Unit.FLAT)
        self.tier = AccommodationTier.objects.create(
            program=self.retreat, name='Windy Lodge', price_per_person=1000,
            total_rooms=1, rooms_confirmed=0,
        )

    def _auth(self, contact):
        token = MobileToken.issue(contact)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    # --- listing / eligibility ---
    def test_guest_sees_only_public_programs(self):
        resp = self.client.get(reverse('mobile_api:program_list'))
        slugs = [p['slug'] for p in resp.data['results']]
        self.assertIn('open-day-2026', slugs)
        self.assertNotIn('annual-retreat-2026', slugs)

    def test_member_sees_members_programs(self):
        resp = self.client.get(reverse('mobile_api:program_list'), **self._auth(self.member))
        slugs = [p['slug'] for p in resp.data['results']]
        self.assertIn('annual-retreat-2026', slugs)

    def test_guest_blocked_from_members_detail(self):
        resp = self.client.get(reverse('mobile_api:program_detail', args=['annual-retreat-2026']))
        self.assertEqual(resp.status_code, 403)

    def test_member_detail_includes_tiers_and_costs(self):
        resp = self.client.get(
            reverse('mobile_api:program_detail', args=['annual-retreat-2026']),
            **self._auth(self.member),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['accommodation_tiers']), 1)
        self.assertEqual(len(resp.data['cost_line_items']), 1)

    # --- registration ---
    def test_register_free_public_program_confirms_immediately(self):
        resp = self.client.post(
            reverse('mobile_api:program_register', args=['open-day-2026']),
            {'quantity': 1}, **self._auth(self.member), format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data['requires_payment'])
        reg = resp.data['registration']
        self.assertEqual(reg['status'], 'confirmed')
        self.assertTrue(reg['reference'].startswith('JCF-2026-'))
        self.assertTrue(reg['qr_url'])

    def test_register_paid_program_is_pending_with_computed_amount(self):
        resp = self.client.post(
            reverse('mobile_api:program_register', args=['annual-retreat-2026']),
            {'quantity': 2, 'accommodation_tier_id': self.tier.id},
            **self._auth(self.member), format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['requires_payment'])
        # flat 400 + tier 1000 * 2 = 2400
        self.assertEqual(resp.data['amount'], '2400.00')
        self.assertEqual(resp.data['registration']['status'], 'pending')

    def test_non_member_cannot_register_members_program(self):
        resp = self.client.post(
            reverse('mobile_api:program_register', args=['annual-retreat-2026']),
            {'quantity': 1}, **self._auth(self.nonmember), format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_register_requires_auth(self):
        resp = self.client.post(
            reverse('mobile_api:program_register', args=['open-day-2026']), {'quantity': 1}, format='json'
        )
        self.assertEqual(resp.status_code, 401)

    # --- verify + room allocation ---
    @patch('mobile_api.programs_api.verify_transaction',
           return_value={'amount': 240000, 'currency': 'GHS', 'customer': {}, 'paid_at': None})
    def test_verify_confirms_and_allocates_room(self, _mock):
        reg = Registration.objects.create(
            program=self.retreat, contact=self.member, quantity=2,
            accommodation_tier=self.tier, amount=2400, currency='GHS',
        )
        reg.assign_reference()
        resp = self.client.post(
            reverse('mobile_api:registration_verify', args=[reg.reference]),
            {'paystack_reference': 'PSK-1'}, **self._auth(self.member), format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'confirmed')
        self.tier.refresh_from_db()
        self.assertEqual(self.tier.rooms_confirmed, 1)

    @patch('mobile_api.programs_api.verify_transaction',
           return_value={'amount': 240000, 'currency': 'GHS', 'customer': {}, 'paid_at': None})
    def test_room_sold_out_returns_409(self, _mock):
        self.tier.rooms_confirmed = 1  # already full (total_rooms=1)
        self.tier.save()
        reg = Registration.objects.create(
            program=self.retreat, contact=self.member, quantity=1,
            accommodation_tier=self.tier, amount=1400, currency='GHS',
        )
        reg.assign_reference()
        resp = self.client.post(
            reverse('mobile_api:registration_verify', args=[reg.reference]),
            {'paystack_reference': 'PSK-2'}, **self._auth(self.member), format='json',
        )
        self.assertEqual(resp.status_code, 409)

    def test_my_registrations_lists_own(self):
        reg = Registration.objects.create(
            program=self.public, contact=self.member, amount=0, currency='GHS',
        )
        reg.assign_reference()
        resp = self.client.get(reverse('mobile_api:my_registrations'), **self._auth(self.member))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)


class EngagementTests(APITestCase):
    def setUp(self):
        self.member = Contact.objects.create(
            full_name='Eng Member', phone='+233200000070',
            email='eng@example.com', is_active=True, is_member=True,
        )
        self.pub = Announcement.objects.create(
            title='Public News', body='hi', audience=Announcement.Audience.PUBLIC,
        )
        self.mem = Announcement.objects.create(
            title='Members Only', body='secret', audience=Announcement.Audience.MEMBERS,
        )

    def _auth(self, contact=None):
        token = MobileToken.issue(contact or self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    # announcements
    def test_guest_sees_only_public_announcements(self):
        resp = self.client.get(reverse('mobile_api:announcement_list'))
        titles = [a['title'] for a in resp.data['results']]
        self.assertIn('Public News', titles)
        self.assertNotIn('Members Only', titles)

    def test_member_sees_members_announcements(self):
        resp = self.client.get(reverse('mobile_api:announcement_list'), **self._auth())
        titles = [a['title'] for a in resp.data['results']]
        self.assertIn('Members Only', titles)

    # device tokens
    def test_register_device_links_member(self):
        resp = self.client.post(
            reverse('mobile_api:device_register'),
            {'token': 'fcm-abc', 'platform': 'android'}, **self._auth(), format='json',
        )
        self.assertEqual(resp.status_code, 200)
        dt = DeviceToken.objects.get(token='fcm-abc')
        self.assertEqual(dt.contact, self.member)
        self.assertTrue(dt.is_active)

    def test_register_device_invalid_platform(self):
        resp = self.client.post(
            reverse('mobile_api:device_register'),
            {'token': 'x', 'platform': 'windows'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_unregister_device_deactivates(self):
        DeviceToken.objects.create(token='fcm-z', platform='ios', contact=self.member)
        resp = self.client.delete(reverse('mobile_api:device_unregister', args=['fcm-z']))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(DeviceToken.objects.get(token='fcm-z').is_active)

    # notifications
    def test_notifications_list_and_mark_read(self):
        n = Notification.objects.create(contact=self.member, title='Hello')
        listed = self.client.get(reverse('mobile_api:notification_list'), **self._auth())
        self.assertEqual(len(listed.data['results']), 1)
        self.assertFalse(listed.data['results'][0]['is_read'])

        read = self.client.post(reverse('mobile_api:notification_read', args=[n.id]), **self._auth())
        self.assertTrue(read.data['updated'])
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_notifications_require_auth(self):
        self.assertEqual(
            self.client.get(reverse('mobile_api:notification_list')).status_code, 401
        )

    # appointments
    def test_book_appointment_creates_requested_consultation(self):
        resp = self.client.post(
            reverse('mobile_api:appointment_book'),
            {'mode': 'Remote', 'scheduled_date': '2026-08-01', 'note': 'Guidance'},
            **self._auth(), format='json',
        )
        self.assertEqual(resp.status_code, 201)
        c = Consultation.objects.get(contact=self.member)
        self.assertEqual(c.status, Consultation.Status.REQUESTED)
        self.assertEqual(c.note, 'Guidance')

    def test_appointments_mine_lists_only_own(self):
        Consultation.objects.create(contact=self.member, mode='Onsite', scheduled_date='2026-08-02')
        resp = self.client.get(reverse('mobile_api:appointment_list'), **self._auth())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)

    def test_book_requires_auth(self):
        resp = self.client.post(
            reverse('mobile_api:appointment_book'),
            {'mode': 'Remote', 'scheduled_date': '2026-08-01'}, format='json',
        )
        self.assertEqual(resp.status_code, 401)
