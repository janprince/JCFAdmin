from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from members.models import Contact
from .models import Consultation, ConsultationRequest

User = get_user_model()


def answers(**overrides):
    data = dict(full_name='  Ama   Serwaa Mensah ', date_of_birth='1990-05-15', profession='Teacher',
                hometown='Kumasi, Ashanti Region', religion='Christian', phone='024 412 3456', email='',
                residence='East Legon, Accra', heard_from='youtube', heard_detail='', preferred_mode='Remote', note='')
    data.update(overrides)
    return data


class PublicBookingFormTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_form_is_public_and_has_no_portal_chrome(self):
        response = self.client.get(reverse('booking:form'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Book a consultation')
        self.assertNotContains(response, 'side-nav')

    def test_submission_creates_a_request_and_a_contact_with_the_answers(self):
        response = self.client.post(reverse('booking:form'), answers())
        self.assertRedirects(response, reverse('booking:thanks'))
        booking = ConsultationRequest.objects.get()
        contact = booking.contact
        self.assertTrue(booking.created_contact)
        self.assertEqual(contact.full_name, 'Ama Serwaa Mensah')
        self.assertEqual(str(contact.phone), '+233244123456')
        self.assertEqual(contact.date_of_birth, date(1990, 5, 15))
        self.assertEqual(contact.birth_weekday, 'Tuesday')
        self.assertEqual((contact.profession, contact.hometown, contact.religion, contact.residence),
                         ('Teacher', 'Kumasi, Ashanti Region', 'Christian', 'East Legon, Accra'))
        self.assertEqual(contact.referral, 'YouTube')
        thanks = self.client.get(reverse('booking:thanks'))
        self.assertContains(thanks, 'Thank you, Ama')
        self.assertContains(thanks, '+233 24 412 3456')

    def test_unknown_date_of_birth_needs_the_day_instead(self):
        response = self.client.post(reverse('booking:form'), answers(date_of_birth='', dob_unknown='on'))
        self.assertIn('day_of_birth', response.context['form'].errors)
        self.client.post(reverse('booking:form'), answers(date_of_birth='', dob_unknown='on', day_of_birth='Friday'))
        contact = ConsultationRequest.objects.get().contact
        self.assertIsNone(contact.date_of_birth)
        self.assertEqual(contact.birth_weekday, 'Friday')

    def test_required_answers_and_impossible_dates_are_refused(self):
        response = self.client.post(reverse('booking:form'), answers(profession='', date_of_birth='2999-01-01', phone='12'))
        errors = response.context['form'].errors
        for field in ('profession', 'date_of_birth', 'phone'):
            self.assertIn(field, errors)
        self.assertFalse(ConsultationRequest.objects.exists())

    def test_existing_contact_with_same_name_and_phone_is_linked_and_left_unchanged(self):
        kept = Contact.objects.create(full_name='Ama Serwaa Mensah', phone='+233244123456', profession='Nurse', residence='Tema')
        self.client.post(reverse('booking:form'), answers(full_name='ama serwaa mensah'))
        booking = ConsultationRequest.objects.get()
        self.assertEqual(booking.contact, kept)
        self.assertFalse(booking.created_contact)
        kept.refresh_from_db()
        self.assertEqual((kept.profession, kept.residence), ('Nurse', 'Tema'))
        self.assertEqual(Contact.objects.count(), 1)

    def test_a_family_member_sharing_the_phone_gets_their_own_contact(self):
        Contact.objects.create(full_name='Kofi Mensah', phone='+233244123456')
        self.client.post(reverse('booking:form'), answers())
        self.assertEqual(Contact.objects.filter(phone='+233244123456').count(), 2)

    def test_sending_twice_while_waiting_keeps_one_request(self):
        self.client.post(reverse('booking:form'), answers())
        self.client.post(reverse('booking:form'), answers(profession='Changed'))
        self.assertEqual(ConsultationRequest.objects.count(), 1)
        self.assertEqual(Contact.objects.count(), 1)

    def test_bots_filling_the_hidden_field_are_thanked_and_ignored(self):
        response = self.client.post(reverse('booking:form'), answers(website='http://spam.example'))
        self.assertRedirects(response, reverse('booking:thanks'))
        self.assertFalse(ConsultationRequest.objects.exists())
        self.assertFalse(Contact.objects.exists())

    @override_settings(CONSULTATION_REQUEST_RATE='2/hour')
    def test_submissions_are_rate_limited_per_address(self):
        for name in ('One Person', 'Two Person'):
            self.client.post(reverse('booking:form'), answers(full_name=name))
        response = self.client.post(reverse('booking:form'), answers(full_name='Three Person'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertEqual(ConsultationRequest.objects.count(), 2)


class BookingRequestOfficeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in Profile.Role.values:
            user = User.objects.create_user(username=role, email=f'{role}@example.com', password='x', first_name=role)
            user.profile.role = role
            user.profile.save()
            cls.users[role] = user

    def setUp(self):
        cache.clear()
        self.client.post(reverse('booking:form'), answers())
        self.booking = ConsultationRequest.objects.get()
        self.client.force_login(self.users['secretary'])

    def test_only_consultation_roles_see_requests(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            allowed = role != 'media_operations'
            with self.subTest(role=role):
                self.assertEqual(self.client.get(reverse('consultations:request_list')).status_code, 200 if allowed else 403)
                self.assertEqual(self.client.get(reverse('consultations:request_detail', args=[self.booking.pk])).status_code, 200 if allowed else 403)

    def test_booking_from_a_request_prefills_and_marks_it_booked(self):
        url = reverse('consultations:consultation_create') + f'?request={self.booking.pk}'
        response = self.client.get(url)
        self.assertEqual(response.context['form'].initial['contact'], self.booking.contact_id)
        self.assertEqual(response.context['form'].initial['mode'], 'Remote')
        self.client.post(url, {'contact': self.booking.contact_id, 'mode': 'Remote', 'scheduled_date': '2026-11-02'})
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'booked')
        self.assertEqual(self.booking.consultation, Consultation.objects.get())
        self.assertEqual(self.booking.handled_by, self.users['secretary'])

    def test_close_and_reopen(self):
        self.client.post(reverse('consultations:request_close', args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'closed')
        self.assertTrue(Contact.objects.filter(pk=self.booking.contact_id).exists())
        self.client.post(reverse('consultations:request_reopen', args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'new')

    def test_spam_removal_deletes_only_a_contact_the_form_created(self):
        contact_pk = self.booking.contact_id
        self.client.post(reverse('consultations:request_remove', args=[self.booking.pk]))
        self.assertFalse(ConsultationRequest.objects.exists())
        self.assertFalse(Contact.objects.filter(pk=contact_pk).exists())

        kept = Contact.objects.create(full_name='Kept Person', phone='+233200000001')
        self.client.post(reverse('booking:form'), answers(full_name='Kept Person', phone='0200000001'))
        matched = ConsultationRequest.objects.get()
        response = self.client.post(reverse('consultations:request_remove', args=[matched.pk]))
        self.assertRedirects(response, reverse('consultations:request_detail', args=[matched.pk]))
        self.assertTrue(Contact.objects.filter(pk=kept.pk).exists())
        self.assertTrue(ConsultationRequest.objects.filter(pk=matched.pk).exists())

    def test_waiting_requests_show_on_the_overview_and_sidebar(self):
        response = self.client.get(reverse('dashboard:analytics'))
        tasks = {task['title']: task['count'] for task in response.context['inbox_tasks']}
        self.assertEqual(tasks['Booking requests'], 1)
        self.assertContains(self.client.get(reverse('consultations:consultation_list')), 'waiting for a date')

    def test_share_menu_offers_the_public_link(self):
        response = self.client.get(reverse('consultations:request_list'))
        self.assertContains(response, 'https://testserver/book/')  # Upgraded outside DEBUG.
        self.assertContains(response, 'wa.me/?text=')
