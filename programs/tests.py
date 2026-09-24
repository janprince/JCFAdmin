"""Dashboard -> mobile API, hand in hand: programs authored here are what
members see and register for in the app."""
import json

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from members.models import Contact
from mobile_api.models import MobileToken

from .models import AccommodationTier, Program, Registration


class ProgramsDashboardTests(APITestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='staff', email='staff@jcf.org', password='x')
        self.client.force_login(self.staff)
        self.member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000001',
            email='ama@example.com', is_active=True, is_member=True)

    def _member_headers(self):
        token = MobileToken.issue(self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def _create_program(self, **overrides):
        data = {
            'title': 'Annual Retreat', 'year': 2027,
            'description': 'Ten days of silence.',
            'audience': 'members', 'currency': 'GHS',
            'is_published': 'on',
            'form_schema_text': json.dumps([
                {'name': 'emergency_contact', 'label': 'Emergency contact',
                 'type': 'text', 'required': True},
            ]),
        }
        data.update(overrides)
        return self.client.post(reverse('programs:program_create'), data)

    # --- authoring -> app ---

    def test_dashboard_program_reaches_the_app_with_schema_and_fees(self):
        res = self._create_program()
        self.assertEqual(res.status_code, 302)
        program = Program.objects.get()

        self.client.post(reverse('programs:cost_item_add', args=[program.pk]), {
            'label': 'Adult fee', 'amount': '400', 'unit': 'per_person', 'order': 0,
        })
        self.client.post(reverse('programs:tier_add', args=[program.pk]), {
            'name': 'Standard room', 'price_per_person': '150',
            'total_rooms': 10, 'order': 0,
        })

        api = self.client.get(
            f'/api/mobile/v1/programs/{program.slug}/', **self._member_headers())
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api.data['title'], 'Annual Retreat')
        self.assertEqual(api.data['form_schema'][0]['name'], 'emergency_contact')
        self.assertEqual(api.data['cost_line_items'][0]['label'], 'Adult fee')
        self.assertEqual(api.data['accommodation_tiers'][0]['name'], 'Standard room')

    def test_invalid_form_schema_json_rejected(self):
        res = self._create_program(form_schema_text='not json')
        self.assertEqual(res.status_code, 200)  # form re-rendered with error
        self.assertEqual(Program.objects.count(), 0)

    def test_draft_program_hidden_from_the_app(self):
        self._create_program(is_published='')
        api = self.client.get('/api/mobile/v1/programs/', **self._member_headers())
        self.assertEqual(api.data['results'], [])

    # --- registrations -> dashboard ---

    def test_app_registration_shows_in_dashboard_detail(self):
        self._create_program(requires_payment='')
        program = Program.objects.get()

        reg = self.client.post(
            f'/api/mobile/v1/programs/{program.slug}/register/',
            {'quantity': 2, 'answers': {'emergency_contact': 'Kwame 024'}},
            format='json', **self._member_headers())
        self.assertEqual(reg.status_code, 201, reg.data)

        page = self.client.get(reverse('programs:program_detail', args=[program.pk]))
        self.assertContains(page, 'Ama Member')
        self.assertContains(page, Registration.objects.get().reference)

    def test_cancel_confirmed_registration_frees_the_room(self):
        self._create_program(requires_payment='')
        program = Program.objects.get()
        tier = AccommodationTier.objects.create(
            program=program, name='Std', price_per_person=100,
            total_rooms=5, rooms_confirmed=1)
        registration = Registration.objects.create(
            program=program, contact=self.member, quantity=1,
            accommodation_tier=tier, status=Registration.Status.CONFIRMED)
        registration.assign_reference()

        self.client.post(
            reverse('programs:registration_cancel', args=[registration.pk]))
        registration.refresh_from_db()
        tier.refresh_from_db()
        self.assertEqual(registration.status, Registration.Status.CANCELLED)
        self.assertEqual(tier.rooms_confirmed, 0)

    def test_tier_with_registrations_deactivated_not_deleted(self):
        self._create_program()
        program = Program.objects.get()
        tier = AccommodationTier.objects.create(
            program=program, name='Std', price_per_person=100, total_rooms=5)
        Registration.objects.create(
            program=program, contact=self.member, accommodation_tier=tier)

        self.client.post(reverse('programs:tier_delete', args=[tier.pk]))
        tier.refresh_from_db()
        self.assertFalse(tier.is_active)
