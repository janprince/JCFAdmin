import json
from unittest.mock import patch

from django.test import TestCase

from .models import Donation


def charge(reference, amount=300000, **metadata):
    return {'reference': reference, 'amount': amount, 'currency': 'GHS', 'status': 'success',
            'paid_at': '2026-10-01T10:00:00Z', 'customer': {'email': 'payer@example.com', 'first_name': 'Payer'},
            'metadata': metadata}


@patch('causes.paystack.validate_webhook_signature', return_value=True)
class PaystackWebhookTests(TestCase):
    """The Paystack account is shared with drbaffourjan.com; only Foundation payments are donations."""

    def send(self, data):
        body = json.dumps({'event': 'charge.success', 'data': data})
        return self.client.post('/api/webhook/paystack/', body, content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE='sig')

    def test_inner_space_membership_is_not_recorded(self, _signature):
        response = self.send(charge('IS-MUPRO6AJ-JZER2B', custom_fields=[{'variable_name': 'product', 'value': 'Inner Space Lifetime Membership'}]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ignored')
        self.assertFalse(Donation.objects.exists())

    def test_personal_offering_to_dr_jan_is_not_recorded(self, _signature):
        self.send(charge('DON-5000-' + 'a' * 24 + '-' + 'b' * 32, purpose='personal_donation'))
        self.assertFalse(Donation.objects.exists())

    def test_unrecognised_reference_is_not_recorded(self, _signature):
        self.send(charge('T123456789'))
        self.assertFalse(Donation.objects.exists())

    def test_foundation_donation_is_recorded_once(self, _signature):
        data = charge('JCF-1759312800000-1a2b3c4d', amount=10000, custom_fields=[{'variable_name': 'cause', 'value': 'General'}])
        self.send(data)
        self.send(data)
        donation = Donation.objects.get()
        self.assertEqual((donation.amount, donation.cause), (100, None))


class DonationVerifyTests(TestCase):
    def test_a_student_platform_reference_cannot_be_turned_into_a_donation(self):
        with patch('causes.paystack.verify_transaction') as verify:
            response = self.client.post('/api/donations/verify/', {'reference': 'IS-MUPRO6AJ-JZER2B'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        verify.assert_not_called()
        self.assertFalse(Donation.objects.exists())

    def test_foundation_reference_is_verified_and_recorded(self):
        with patch('causes.paystack.verify_transaction', return_value=charge('JCF-1759312800000-1a2b3c4d', amount=5000)):
            response = self.client.post('/api/donations/verify/', {'reference': 'JCF-1759312800000-1a2b3c4d'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Donation.objects.get().amount, 50)
