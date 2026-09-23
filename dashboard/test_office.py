from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.urls import reverse, resolve
from django.utils import timezone

from causes.models import Cause, Donation
from consultations.models import Consultation
from events.models import Event
from members.models import Contact
from website.models import ContactSubmission, VolunteerApplication
from .navigation import navigation_for


class OfficeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='office-test', email='office@example.com', password='test-password')
        cls.user.profile.role = 'administrator'
        cls.user.profile.save()
        cls.person = Contact.objects.create(full_name='Test Member', phone='+233240000010', is_member=True)
        cls.cause = Cause.objects.create(title='Test initiative', slug='test-initiative')

    def setUp(self):
        self.client.force_login(self.user)

    def gift(self, amount, currency='GHS', **extra):
        defaults = dict(donor_name='Test donor', amount=amount, currency=currency, status='completed', method='online', donated_at=timezone.now())
        defaults.update(extra)
        return Donation.objects.create(**defaults)

    def event(self, slug, **extra):
        defaults = dict(title=slug, slug=slug, date=timezone.localdate(), time=time(10), location='Accra', is_published=True)
        defaults.update(extra)
        return Event.objects.create(**defaults)

    def test_overview_is_authenticated(self):
        self.client.logout()
        response = self.client.get(reverse('dashboard:analytics'))
        self.assertRedirects(response, '/login/?next=/dashboard/', fetch_redirect_response=False)

    def test_overview_groups_completed_gifts_by_currency_and_current_month(self):
        self.gift('100.00')
        self.gift('50.00', 'USD')
        self.gift('999.00', status='pending')
        self.gift('888.00', donated_at=timezone.now().replace(day=1) - timedelta(days=1))
        response = self.client.get(reverse('dashboard:analytics'))
        totals = {row['currency']: row['total'] for row in response.context['giving_by_currency']}
        self.assertEqual(totals, {'GHS': Decimal('100'), 'USD': Decimal('50')})
        self.assertEqual(response.context['monthly_donation_count'], 2)
        self.assertEqual(response.context['pending_donation_count'], 1)
        self.assertEqual(response.context['general_donation_count'], 2)

    def test_overview_inbox_counts_only_unprocessed_records(self):
        ContactSubmission.objects.create(name='Unread', email='unread@example.com', subject='Visit', message='Hello')
        ContactSubmission.objects.create(name='Read', email='read@example.com', subject='Visit', message='Hello', is_read=True)
        VolunteerApplication.objects.create(name='Volunteer', email='volunteer@example.com', phone='+233240000011', availability='Weekends')
        response = self.client.get(reverse('dashboard:analytics'))
        self.assertEqual(response.context['inbox_count'], 2)
        self.assertEqual([task['count'] for task in response.context['inbox_tasks']], [1, 0, 1])
        self.assertEqual(len(response.context['contact_trend']), 6)

    def test_general_giving_filter_and_payment_reference_search(self):
        general = self.gift('100.00', paystack_reference='JCF-TEST-REF')
        self.gift('250.00', cause=self.cause)
        response = self.client.get(reverse('causes:donation_list'), {'cause': 'general'})
        self.assertEqual(list(response.context['donations']), [general])
        response = self.client.get(reverse('causes:donation_list'), {'q': 'JCF-TEST-REF'})
        self.assertEqual(list(response.context['donations']), [general])
        response = self.client.get(reverse('causes:donation_list'), {'cause': 'not-an-id'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['donations']), [])

    def test_donation_list_never_adds_different_currencies(self):
        self.gift('100.00'); self.gift('20.00', 'USD'); self.gift('500.00', status='failed')
        response = self.client.get(reverse('causes:donation_list'))
        self.assertEqual({r['currency']: r['total'] for r in response.context['totals_by_currency']}, {'GHS': Decimal('100'), 'USD': Decimal('20')})

    def test_ongoing_events_stay_upcoming_and_drafts_have_a_real_filter(self):
        today = timezone.localdate()
        ongoing = self.event('ongoing', date=today-timedelta(days=2), end_date=today+timedelta(days=1))
        ended = self.event('ended', date=today-timedelta(days=4), end_date=today-timedelta(days=1))
        draft = self.event('draft', is_published=False)
        self.assertFalse(ongoing.is_past); self.assertTrue(ended.is_past)
        response = self.client.get(reverse('events:event_list'), {'filter': 'upcoming'})
        self.assertEqual(list(response.context['events']), [ongoing])
        response = self.client.get(reverse('events:event_list'), {'filter': 'draft'})
        self.assertEqual(list(response.context['events']), [draft])
        response = self.client.get(reverse('dashboard:analytics'))
        self.assertEqual(response.context['upcoming_event_count'], 1)

    def test_past_unfinished_consultations_have_their_own_queue(self):
        today = timezone.localdate()
        past = Consultation.objects.create(contact=self.person, mode='Onsite', scheduled_date=today-timedelta(days=1))
        current = Consultation.objects.create(contact=self.person, mode='Remote', scheduled_date=today)
        Consultation.objects.create(contact=self.person, mode='Remote', scheduled_date=today, done=True)
        response = self.client.get(reverse('consultations:consultation_list'))
        self.assertEqual(list(response.context['consultations']), [current])
        response = self.client.get(reverse('consultations:consultation_list'), {'show': 'overdue'})
        self.assertEqual(list(response.context['consultations']), [past])
        response = self.client.get(reverse('consultations:consultation_list'), {'show': 'today'})
        self.assertEqual(list(response.context['consultations']), [current])

    def test_navigation_selects_specific_destination_and_respects_staff_permission(self):
        self.user.profile.role = 'admin'
        self.user.profile.save()
        request = RequestFactory().get(reverse('causes:donation_create'))
        request.user = self.user; request.resolver_match = resolve(request.path)
        groups = navigation_for(request)
        active = [link['label'] for group in groups for link in group['links'] if link['active']]
        self.assertEqual(active, ['Donations'])
        self.assertIn('Staff', [group['label'] for group in groups])
        self.assertTrue(next(g for g in groups if g['label'] == 'Giving')['active'])

    def test_sign_out_control_uses_post_and_works(self):
        response = self.client.get(reverse('dashboard:analytics'))
        self.assertContains(response, 'method="post" action="/logout/"')
        response = self.client.post(reverse('logout'))
        self.assertLess(response.status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)
