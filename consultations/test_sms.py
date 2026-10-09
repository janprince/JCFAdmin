from datetime import timedelta
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from members.models import Contact
from website.notifications import arkesel_recipient
from .models import Consultation
from .sms import booking_message

User = get_user_model()


class Reply:
    def __init__(self, status=200, body=None):
        self.status_code, self.body, self.ok = status, body or {'status': 'success'}, status < 400

    def json(self):
        return self.body


@override_settings(ARKESEL_API_KEY='test-key', ARKESEL_SENDER_ID='JCF')
class BookingSmsTests(TestCase):
    """Arkesel is never called for real: requests.post is replaced in every test."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='sec', email='sec@jcf.org', password='x')
        cls.user.profile.role = 'secretary'
        cls.user.profile.save()
        cls.ghana = Contact.objects.create(full_name='AMA SERWAA MENSAH', phone='+233244123456')
        cls.abroad = Contact.objects.create(full_name='John Smith', phone='+447911123456')

    def setUp(self):
        self.client.force_login(self.user)
        patcher = patch('website.notifications.requests.post', return_value=Reply())
        self.post = patcher.start()
        self.addCleanup(patcher.stop)
        self.next_week = timezone.localdate() + timedelta(days=7)

    def book(self, contact, **extra):
        data = {'contact': contact.pk, 'mode': 'Onsite', 'scheduled_date': self.next_week.isoformat(), 'send_sms': 'on'}
        data.update(extra)
        return self.client.post(reverse('consultations:consultation_create'), data, follow=True)

    def test_booking_a_ghana_number_texts_the_date(self):
        response = self.book(self.ghana)
        payload = self.post.call_args.kwargs['json']
        self.assertEqual(payload['recipients'], ['233244123456'])
        self.assertEqual(payload['sender'], 'JCF')
        self.assertIn('Dear Ama, your consultation with Dr. Baffour Jan is on', payload['message'])
        self.assertIn(f"{self.next_week:%A}, {self.next_week.day} {self.next_week:%B %Y} (in person)", payload['message'])
        self.assertEqual(self.post.call_args.kwargs['headers'], {'api-key': 'test-key'})
        self.assertIsNotNone(Consultation.objects.get().sms_sent_at)
        self.assertContains(response, 'SMS sent to +233 24 412 3456')

    def test_international_numbers_are_not_texted(self):
        response = self.book(self.abroad)
        self.post.assert_not_called()
        self.assertIsNone(Consultation.objects.get().sms_sent_at)
        self.assertContains(response, 'is not a Ghana number')

    def test_unticking_the_box_sends_nothing(self):
        self.book(self.ghana, send_sms='')
        self.post.assert_not_called()

    def test_past_dates_are_not_texted(self):
        self.book(self.ghana, scheduled_date=(timezone.localdate() - timedelta(days=1)).isoformat())
        self.post.assert_not_called()

    def test_a_refused_or_failed_send_still_books_and_warns(self):
        self.post.return_value = Reply(200, {'status': 'error', 'message': 'Insufficient balance'})
        response = self.book(self.ghana)
        self.assertTrue(Consultation.objects.exists())
        self.assertIsNone(Consultation.objects.get().sms_sent_at)
        self.assertContains(response, 'Insufficient balance')

        self.post.side_effect = requests.ConnectionError('down')
        response = self.book(self.ghana)
        self.assertEqual(Consultation.objects.count(), 2)
        self.assertContains(response, 'Could not reach the SMS service')

    @override_settings(ARKESEL_API_KEY='')
    def test_without_an_api_key_staff_are_told_why(self):
        response = self.book(self.ghana)
        self.post.assert_not_called()
        self.assertContains(response, 'ARKESEL_API_KEY')

    def test_moving_the_date_says_so_and_editing_does_not_text_by_default(self):
        consultation = Consultation.objects.create(contact=self.ghana, mode='Remote', scheduled_date=self.next_week)
        url = reverse('consultations:consultation_update', args=[consultation.pk])
        self.assertFalse(self.client.get(url).context['form'].fields['send_sms'].initial)
        later = self.next_week + timedelta(days=3)
        self.client.post(url, {'contact': self.ghana.pk, 'mode': 'Remote', 'scheduled_date': later.isoformat()})
        self.post.assert_not_called()
        self.client.post(url, {'contact': self.ghana.pk, 'mode': 'Remote', 'scheduled_date': (later + timedelta(days=1)).isoformat(), 'send_sms': 'on'})
        message = self.post.call_args.kwargs['json']['message']
        self.assertIn('has been moved to', message)
        self.assertIn('(by phone or video)', message)

    def test_even_the_longest_message_is_one_plain_sms(self):
        from datetime import date
        # A Wednesday in September, by phone or video, rescheduled: the longest wording.
        consultation = Consultation(contact=self.ghana, mode='Remote', scheduled_date=date(2027, 9, 29))
        for message in (booking_message(consultation), booking_message(consultation, rescheduled=True)):
            self.assertTrue(all(ord(ch) < 128 for ch in message), message)
            self.assertLessEqual(len(message), 160, message)

    def test_recipient_format(self):
        self.assertEqual(arkesel_recipient('0244123456'), '233244123456')
        self.assertEqual(arkesel_recipient('+233 24 412 3456'), '233244123456')
