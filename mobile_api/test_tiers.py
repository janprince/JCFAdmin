"""The two-tier rules, and the promise that nobody lost access."""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from engagement.models import DailyInspiration
from members.models import Contact
from programs.models import Program
from studies.models import Enrolment
from mobile_api import tiers
from mobile_api.models import MobileToken


def contact(phone, **flags):
    return Contact.objects.create(
        full_name=f'Test {phone}', phone=phone,
        email=f'{phone.strip("+")}@example.com', **flags)


class TierRuleTests(TestCase):
    def test_is_member_is_the_flag(self):
        # The only flag the web writes: the website sets it on join-centre
        # approval, and enrolling sets it too.
        self.assertTrue(tiers.is_approved(
            contact('+233500000020', is_active=True, is_member=True)))

    def test_is_student_is_still_honoured_as_a_bridge(self):
        # Nothing sets this automatically; it exists on contacts a member
        # of staff ticked by hand. Until those are reconciled, refusing
        # them would lock out people who can use the app today.
        self.assertTrue(tiers.is_approved(
            contact('+233500000021', is_active=True, is_student=True)))

    def test_either_approval_flag_counts(self):
        member = contact('+233500000001', is_active=True, is_member=True)
        student = contact('+233500000002', is_active=True, is_student=True)
        both = contact('+233500000003', is_active=True,
                       is_member=True, is_student=True)
        for person in (member, student, both):
            self.assertTrue(tiers.is_approved(person), person.phone)

    def test_a_guest_is_not_approved(self):
        self.assertFalse(tiers.is_approved(None))

    def test_an_unflagged_contact_is_not_approved(self):
        # Signing in is not the same as being approved: a Contact row can
        # exist for someone the foundation has not admitted.
        self.assertFalse(tiers.is_approved(
            contact('+233500000004', is_active=True)))

    def test_an_inactive_contact_is_not_approved(self):
        self.assertFalse(tiers.is_approved(
            contact('+233500000005', is_active=False, is_member=True)))

    def test_a_guest_sees_only_public(self):
        self.assertEqual(tiers.visible_audiences(None), [tiers.PUBLIC])
        self.assertEqual(tiers.attendable_audiences(None), [tiers.PUBLIC])

    def test_an_approved_contact_sees_everything(self):
        person = contact('+233500000006', is_active=True, is_member=True)
        self.assertEqual(tiers.visible_audiences(person),
                         [tiers.PUBLIC, tiers.STUDENTS])

    def test_visible_never_exceeds_attendable(self):
        # The old feed advertised a tier the caller could not open. It no
        # longer does, and nothing should quietly reintroduce that.
        for person in (None,
                       contact('+233500000007', is_active=True),
                       contact('+233500000008', is_active=True,
                               is_student=True)):
            self.assertEqual(tiers.visible_audiences(person),
                             tiers.attendable_audiences(person))

    def test_public_opens_for_anyone(self):
        self.assertTrue(tiers.may_open(tiers.PUBLIC, None))

    def test_gated_needs_approval(self):
        self.assertFalse(tiers.may_open(tiers.STUDENTS, None))
        self.assertTrue(tiers.may_open(
            tiers.STUDENTS,
            contact('+233500000009', is_active=True, is_member=True)))


class SignedInHomeTests(TestCase):
    """The student home is the home for everyone signed in."""

    def setUp(self):
        self.url = reverse('mobile_api:student_home')

    def auth(self, person):
        return {'HTTP_AUTHORIZATION':
                f'Bearer {MobileToken.issue(person).access_token}'}

    def test_daily_inspiration_survived_the_merge(self):
        # The one section the member home had that this one did not. It
        # matters most for a signed-in person with no course, who would
        # otherwise see an empty page.
        DailyInspiration.objects.create(
            quote='Freedom begins with awareness.', author='Dr. Baffour Jan',
            date=timezone.localdate(), is_published=True)
        person = contact('+233500000010', is_active=True, is_member=True)
        body = self.client.get(self.url, **self.auth(person)).json()
        self.assertEqual(len(body['daily_inspirations']), 1)
        self.assertEqual(body['daily_inspirations'][0]['quote'],
                         'Freedom begins with awareness.')

    def test_an_unpublished_inspiration_is_not_sent(self):
        DailyInspiration.objects.create(
            quote='Draft', date=timezone.localdate(), is_published=False)
        person = contact('+233500000011', is_active=True, is_student=True)
        body = self.client.get(self.url, **self.auth(person)).json()
        self.assertEqual(body['daily_inspirations'], [])

    def test_no_enrolment_is_an_empty_section_not_an_error(self):
        person = contact('+233500000012', is_active=True, is_member=True)
        response = self.client.get(self.url, **self.auth(person))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body['primary_enrolment'])
        self.assertEqual(body['active_enrolments'], [])


class EnrolmentApprovesContactTests(TestCase):
    """Enrolling someone is JCF saying they belong here."""

    def setUp(self):
        self.program = Program.objects.create(
            title='Foundations', year=2026,
            starts_on=timezone.localdate())

    def test_enrolling_admits_an_unflagged_contact(self):
        person = contact('+233500000030', is_active=True)
        self.assertFalse(tiers.is_approved(person))

        Enrolment.objects.create(contact=person, program=self.program)

        person.refresh_from_db()
        self.assertTrue(person.is_member)
        self.assertTrue(tiers.is_approved(person))

    def test_re_saving_does_not_re_admit_someone_unflagged_since(self):
        person = contact('+233500000031', is_active=True)
        enrolment = Enrolment.objects.create(
            contact=person, program=self.program)
        # Staff withdraw approval afterwards.
        person.refresh_from_db()
        person.is_member = False
        person.save(update_fields=['is_member'])

        enrolment.status = Enrolment.Status.PAUSED
        enrolment.save()

        person.refresh_from_db()
        self.assertFalse(person.is_member)

    def test_enrolling_does_not_reactivate_a_deactivated_contact(self):
        # is_active is a deliberate staff decision and not ours to undo.
        person = contact('+233500000032', is_active=False)
        Enrolment.objects.create(contact=person, program=self.program)

        person.refresh_from_db()
        self.assertFalse(person.is_active)
        self.assertFalse(tiers.is_approved(person))
