from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from members.models import Contact
from .models import ServiceEntry, ServiceUnit, Worker

User = get_user_model()
PASSWORD = 'Cedar!River-93847'


class ServiceTeamTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in Profile.Role.values:
            user = User.objects.create_user(username=role, email=f'{role}@example.com', password=PASSWORD, first_name=role)
            user.profile.role = role
            user.profile.save()
            cls.users[role] = user
        # Seeded by the 0002 migration.
        cls.media = ServiceUnit.objects.get(name='Media & Communications')
        cls.office = ServiceUnit.objects.get(name='JCF Administration')
        cls.farms = ServiceUnit.objects.get(name='JCF Farms')

    def setUp(self):
        self.client.force_login(self.users['administrator'])

    def member(self, name, unit=None, **extra):
        contact = Contact.objects.create(full_name=name, phone=f'+2332400{Contact.objects.count():05d}')
        defaults = dict(unit=unit or self.media, service_type='volunteer', started_on=date(2022, 3, 1))
        defaults.update(extra)
        return Worker.objects.create(contact=contact, **defaults)

    def form_data(self, **overrides):
        data = dict(person='new', new_name='Ama Mensah', new_phone='0244000001', new_email='', service_type='volunteer',
                    status='active', unit=self.media.pk, title='Videographer', started_on='2024-01-15',
                    allowance_currency='GHS', allowance='')
        data.update(overrides)
        return data

    # Seeded units -------------------------------------------------------

    def test_migration_seeds_the_four_units_with_their_portal_roles(self):
        units = {u.name: u.portal_roles for u in ServiceUnit.objects.all()}
        self.assertEqual(units['Media & Communications'], ['media_operations'])
        self.assertEqual(units['JCF Farms'], [])
        self.assertIn('IT', units)

    # Adding and editing -------------------------------------------------

    def test_add_new_person_creates_contact_service_record_and_first_journey_entry(self):
        response = self.client.post(reverse('staff:staff_create'), self.form_data())
        worker = Worker.objects.get(contact__full_name='Ama Mensah')
        self.assertRedirects(response, reverse('staff:staff_detail', args=[worker.pk]))
        self.assertEqual(str(worker.contact.phone), '+233244000001')
        self.assertIsNone(worker.allowance)
        entry = worker.journey.get()
        self.assertEqual(entry.kind, ServiceEntry.Kind.CHANGE)
        self.assertEqual(entry.occurred_on, date(2024, 1, 15))
        self.assertIn('Media & Communications', entry.text)

    def test_add_existing_contact_and_refuse_a_duplicate(self):
        contact = Contact.objects.create(full_name='Kofi Owusu', phone='+233240000999')
        data = self.form_data(person='existing', contact=contact.pk, new_name='', new_phone='')
        self.client.post(reverse('staff:staff_create'), data)
        worker = Worker.objects.get(contact=contact)
        response = self.client.get(reverse('staff:staff_create'), {'contact': contact.pk})
        self.assertRedirects(response, reverse('staff:staff_detail', args=[worker.pk]))
        self.assertEqual(Contact.objects.filter(full_name='Kofi Owusu').count(), 1)

    def test_new_person_already_in_contacts_is_pointed_to_the_list(self):
        Contact.objects.create(full_name='Ama Mensah', phone='+233244000001')
        response = self.client.post(reverse('staff:staff_create'), self.form_data())
        self.assertIn('new_name', response.context['form'].errors)
        self.assertFalse(Worker.objects.exists())

    def test_allowance_requires_an_amount_and_is_cleared_when_switched_off(self):
        response = self.client.post(reverse('staff:staff_create'), self.form_data(receives_allowance='on'))
        self.assertIn('allowance', response.context['form'].errors)
        self.client.post(reverse('staff:staff_create'), self.form_data(allowance='500'))
        self.assertIsNone(Worker.objects.get().allowance)

    def test_future_start_and_end_before_start_are_rejected(self):
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(reverse('staff:staff_create'), self.form_data(started_on=tomorrow))
        self.assertIn('started_on', response.context['form'].errors)
        worker = self.member('Esi Badu')
        data = self.form_data(status='inactive', ended_on='2020-01-01', unit=self.media.pk)
        response = self.client.post(reverse('staff:staff_update', args=[worker.pk]), data)
        self.assertIn('ended_on', response.context['form'].errors)

    def test_edits_are_written_to_the_journey(self):
        worker = self.member('Yaw Boateng', service_type='part_time')
        data = self.form_data(service_type='full_time', receives_allowance='on', allowance='1200.00',
                              allowance_currency='GHS', other_units=[self.office.pk, self.media.pk], status='inactive')
        self.client.post(reverse('staff:staff_update', args=[worker.pk]), data)
        worker.refresh_from_db()
        self.assertEqual(worker.ended_on, timezone.localdate())
        self.assertEqual(list(worker.other_units.all()), [self.office])  # The main unit is not repeated.
        text = worker.journey.get().text
        for phrase in ('Service ended.', 'Part-time to Full-time', 'Began helping JCF Administration', 'Monthly allowance began: GHS 1,200.00'):
            self.assertIn(phrase, text)
        # Saving again without changes adds nothing.
        self.client.post(reverse('staff:staff_update', args=[worker.pk]), data | {'ended_on': worker.ended_on.isoformat()})
        self.assertEqual(worker.journey.count(), 1)

    def test_returning_to_service_clears_the_end_date(self):
        worker = self.member('Akosua Darko', status='inactive', ended_on=date(2025, 1, 1))
        self.client.post(reverse('staff:staff_update', args=[worker.pk]), self.form_data(status='active', ended_on='2025-01-01'))
        worker.refresh_from_db()
        self.assertIsNone(worker.ended_on)
        self.assertIn('Resumed service.', worker.journey.get().text)

    # Directory ----------------------------------------------------------

    def test_directory_opens_on_people_serving_and_filters_by_any_unit(self):
        active = self.member('Active One')
        leave = self.member('On Leave', status='on_leave')
        gone = self.member('Gone Before', status='inactive')
        helper = self.member('Farm Helper', unit=self.farms)
        helper.other_units.add(self.media)
        names = lambda r: {w.contact.full_name for w in r.context['staff']}
        self.assertEqual(names(self.client.get(reverse('staff:staff_list'))), {'Active One', 'On Leave', 'Farm Helper'})
        self.assertIn('Gone Before', names(self.client.get(reverse('staff:staff_list'), {'status': 'all'})))
        self.assertEqual(names(self.client.get(reverse('staff:staff_list'), {'unit': self.media.pk, 'status': 'all'})),
                         {'Active One', 'On Leave', 'Gone Before', 'Farm Helper'})
        self.assertEqual(names(self.client.get(reverse('staff:staff_list'), {'unit': self.farms.pk})), {'Farm Helper'})
        tabs = {tab['label']: tab for tab in self.client.get(reverse('staff:staff_list')).context['tabs']}
        self.assertTrue(tabs['Serving']['active'])
        self.assertEqual(tabs['All']['count'], 4)
        del active, leave, gone

    def test_allowance_totals_are_grouped_by_currency_and_skip_inactive(self):
        self.member('Paid Cedi', allowance=Decimal('800'))
        self.member('Paid Cedi Two', allowance=Decimal('700'))
        self.member('Paid Dollar', allowance=Decimal('100'), allowance_currency='USD')
        self.member('Former', allowance=Decimal('5000'), status='inactive')
        totals = {row['allowance_currency']: row['total'] for row in self.client.get(reverse('staff:staff_list')).context['allowances']}
        self.assertEqual(totals, {'GHS': Decimal('1500'), 'USD': Decimal('100')})

    def test_anniversaries_list_people_who_began_this_month_in_an_earlier_year(self):
        today = timezone.localdate()
        self.member('Five Years', started_on=today.replace(year=today.year - 5, day=1))
        self.member('Started Now', started_on=today.replace(day=1))
        anniversaries = self.client.get(reverse('staff:staff_list')).context['anniversaries']
        self.assertEqual([(w.contact.full_name, w.years) for w in anniversaries], [('Five Years', 5)])

    # Journey entries ----------------------------------------------------

    def test_journey_notes_can_be_added_and_removed_but_changes_cannot(self):
        worker = self.member('Kwame Asante')
        self.client.post(reverse('staff:entry_create', args=[worker.pk]), {'kind': 'appreciation', 'occurred_on': '2025-06-01', 'text': 'Thank you'})
        note = worker.journey.get()
        self.assertEqual(note.recorded_by, self.users['administrator'])
        change = ServiceEntry.objects.create(worker=worker, kind='change', text='Service ended.')
        self.assertEqual(self.client.post(reverse('staff:entry_delete', args=[change.pk])).status_code, 404)
        self.client.post(reverse('staff:entry_delete', args=[note.pk]))
        self.assertEqual(list(worker.journey.all()), [change])

    def test_invalid_journey_entry_reopens_the_modal_with_errors(self):
        worker = self.member('Kwame Asante')
        response = self.client.post(reverse('staff:entry_create', args=[worker.pk]), {'kind': 'change', 'text': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-jcf-open')
        self.assertFalse(worker.journey.exists())

    # Units --------------------------------------------------------------

    def test_only_account_managers_set_a_units_portal_roles(self):
        self.client.post(reverse('staff:unit_create'), {'name': 'Hospitality', 'icon': 'bowl-food', 'portal_roles': ['admin'], 'is_active': 'on'})
        self.assertEqual(ServiceUnit.objects.get(name='Hospitality').portal_roles, [])
        self.client.post(reverse('staff:unit_update', args=[self.farms.pk]), {'name': 'JCF Farms', 'icon': 'plant', 'portal_roles': ['admin'], 'is_active': 'on'})
        self.farms.refresh_from_db()
        self.assertEqual(self.farms.portal_roles, [])
        self.client.force_login(self.users['admin'])
        self.client.post(reverse('staff:unit_update', args=[self.farms.pk]), {'name': 'JCF Farms', 'icon': 'plant', 'portal_roles': ['secretary'], 'is_active': 'on'})
        self.farms.refresh_from_db()
        self.assertEqual(self.farms.portal_roles, ['secretary'])

    def test_archived_units_cannot_be_chosen_for_new_members(self):
        self.farms.is_active = False
        self.farms.save()
        response = self.client.post(reverse('staff:staff_create'), self.form_data(unit=self.farms.pk))
        self.assertIn('unit', response.context['form'].errors)

    def test_pages_render(self):
        worker = self.member('Render Me', allowance=Decimal('300'))
        for url in (reverse('staff:staff_list'), reverse('staff:staff_create'), reverse('staff:staff_detail', args=[worker.pk]),
                    reverse('staff:staff_update', args=[worker.pk]), reverse('staff:unit_list'),
                    reverse('staff:unit_update', args=[self.media.pk])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_roles_without_the_staff_area_are_refused(self):
        worker = self.member('Private Person')
        for role in ('secretary', 'media_operations'):
            self.client.force_login(self.users[role])
            for url in (reverse('staff:staff_detail', args=[worker.pk]), reverse('staff:unit_list')):
                self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(reverse('staff:entry_create', args=[worker.pk]), {'kind': 'note', 'occurred_on': '2025-01-01', 'text': 'x'}).status_code, 403)
        self.assertFalse(worker.journey.exists())


class UnitRoleGuardrailTests(TestCase):
    """Service units bound the portal roles a linked account can be given."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', email='admin@example.com', password=PASSWORD, first_name='Admin')
        cls.admin.profile.role = 'admin'
        cls.admin.profile.save()
        cls.media = ServiceUnit.objects.get(name='Media & Communications')
        cls.farms = ServiceUnit.objects.get(name='JCF Farms')

    def setUp(self):
        self.client.force_login(self.admin)

    def worker(self, name, unit, **extra):
        contact = Contact.objects.create(full_name=name, phone=f'+2332410{Contact.objects.count():05d}', email=f'{name.split()[0].lower()}@example.com')
        return Worker.objects.create(contact=contact, unit=unit, **extra)

    def account(self, worker, role, **overrides):
        data = dict(first_name='First', last_name='Last', email=worker.contact.email, role=role, worker=worker.pk,
                    password1=PASSWORD, password2=PASSWORD)
        data.update(overrides)
        return self.client.post(reverse('staff:user_create'), data)

    def test_media_member_can_only_be_given_media_operations(self):
        worker = self.worker('Media Person', self.media)
        response = self.account(worker, 'administrator')
        self.assertIn('role', response.context['form'].errors)
        self.assertFalse(User.objects.filter(email=worker.contact.email).exists())
        self.account(worker, 'media_operations')
        self.assertEqual(User.objects.get(email=worker.contact.email).profile.role, 'media_operations')

    def test_units_outside_the_portal_refuse_every_role_and_other_units_widen_the_choice(self):
        worker = self.worker('Farm Person', self.farms)
        response = self.account(worker, 'media_operations')
        self.assertIn('do not use the portal', str(response.context['form'].errors['role']))
        worker.other_units.add(self.media)
        self.account(worker, 'media_operations')
        self.assertTrue(User.objects.filter(email=worker.contact.email).exists())

    def test_records_without_units_are_not_constrained(self):
        worker = self.worker('Legacy Person', None)
        self.account(worker, 'administrator')
        self.assertTrue(User.objects.filter(email=worker.contact.email).exists())

    def test_set_up_access_suggests_the_least_privileged_allowed_role(self):
        worker = self.worker('Media Person', self.media)
        response = self.client.get(reverse('staff:user_create'), {'worker': worker.pk})
        self.assertEqual(response.context['form'].initial['role'], 'media_operations')
        self.assertContains(response, 'id="service-roles"')

    def test_people_whose_service_ended_cannot_be_given_an_account(self):
        worker = self.worker('Former Person', self.media, status='inactive')
        response = self.account(worker, 'media_operations')
        self.assertIn('worker', response.context['form'].errors)

    def test_unchanged_accounts_still_save_after_a_unit_tightens_and_are_flagged(self):
        worker = self.worker('Media Person', self.media)
        self.account(worker, 'media_operations')
        user = User.objects.get(email=worker.contact.email)
        self.media.portal_roles = []
        self.media.save()
        data = dict(first_name='Renamed', last_name='Last', email=user.email, role='media_operations', worker=worker.pk)
        response = self.client.post(reverse('staff:user_update', args=[user.pk]), data)
        self.assertRedirects(response, reverse('staff:user_update', args=[user.pk]))
        response = self.client.post(reverse('staff:user_update', args=[user.pk]), data | {'role': 'secretary'})
        self.assertIn('role', response.context['form'].errors)
        worker.refresh_from_db()
        self.assertEqual(len(worker.access_concerns()), 1)
        self.assertEqual(self.client.get(reverse('staff:staff_list')).context['needs_review'], [worker])

    def test_ended_service_with_live_account_is_flagged(self):
        worker = self.worker('Media Person', self.media)
        self.account(worker, 'media_operations')
        worker.status = Worker.Status.INACTIVE
        worker.save()
        worker.refresh_from_db()
        self.assertIn('Their service has ended but they can still sign in to the portal.', worker.access_concerns())
        self.assertContains(self.client.get(reverse('staff:staff_detail', args=[worker.pk])), 'Review their portal access')
