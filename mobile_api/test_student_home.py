"""Student Home aggregate: enrolment-driven, server-authoritative."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from activities.models import Activity
from members.models import Contact
from practices.models import Practice
from programs.models import Program
from staff_mgmt.models import Worker
from studies.models import Enrolment, Mentorship, Milestone, PracticeAssignment
from teachings.models import Teaching, TeachingProgress, TeachingSeries

from .models import MobileToken

HOME = '/api/mobile/v1/home/student/'


class StudentHomeTests(APITestCase):
    def setUp(self):
        self.student = Contact.objects.create(
            full_name='Kwame Asante', phone='+233200000051',
            email='kwame@example.com', is_active=True, is_student=True)
        self.program = Program.objects.create(
            title='InnerSpace Foundations', year=2026, audience='students',
            is_published=True)
        self.series = TeachingSeries.objects.create(
            title='Foundations Curriculum', slug='foundations-curriculum',
            is_published=True)
        self.lessons = [
            Teaching.objects.create(
                topic=f'Lesson {i}', slug=f'sh-lesson-{i}', series=self.series,
                order=i, status='published', duration_seconds=600)
            for i in range(1, 5)
        ]
        self.enrolment = Enrolment.objects.create(
            contact=self.student, program=self.program, series=self.series,
            cohort='Cohort 3', is_primary=True)

    def _auth(self, contact=None):
        token = MobileToken.issue(contact or self.student)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    # --- access ---

    def test_guest_is_rejected(self):
        self.assertEqual(self.client.get(HOME).status_code, 401)

    def test_member_who_is_not_a_student_is_rejected(self):
        member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000052',
            email='ama-not-student@example.com', is_active=True,
            is_member=True)
        self.assertEqual(
            self.client.get(HOME, **self._auth(member)).status_code, 403)

    # --- enrolment selection ---

    def test_primary_open_enrolment_is_chosen(self):
        other = Program.objects.create(
            title='Second Programme', year=2026, audience='students',
            is_published=True)
        Enrolment.objects.create(
            contact=self.student, program=other, status='active')
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(
            res.data['primary_enrolment']['program_title'],
            'InnerSpace Foundations')
        self.assertEqual(res.data['primary_enrolment']['cohort'], 'Cohort 3')
        self.assertEqual(len(res.data['active_enrolments']), 2)

    def test_paused_enrolment_is_not_promoted_to_current(self):
        self.enrolment.status = Enrolment.Status.PAUSED
        self.enrolment.save()
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(res.data['primary_enrolment']['status'], 'paused')
        self.assertEqual(res.data['active_enrolments'], [])
        # A paused enrolment must not offer a continue action.
        self.assertFalse(res.data['continue_course']['access_granted'])

    def test_expired_access_is_reported(self):
        self.enrolment.access_expires_at = timezone.now() - timedelta(days=1)
        self.enrolment.save()
        res = self.client.get(HOME, **self._auth())
        self.assertIsNotNone(res.data['student_summary']['access_expires_at'])
        self.assertEqual(res.data['active_enrolments'], [])

    # --- progress ---

    def test_progress_is_computed_from_published_lessons(self):
        for lesson in self.lessons[:2]:
            TeachingProgress.objects.create(
                contact=self.student, teaching=lesson, completed=True)
        res = self.client.get(HOME, **self._auth())
        summary = res.data['progress_summary']
        self.assertEqual(summary['total_lessons'], 4)
        self.assertEqual(summary['completed_lessons'], 2)
        self.assertEqual(summary['program_percentage'], 50)
        self.assertEqual(res.data['continue_course']['lesson_id'],
                         'sh-lesson-3')

    def test_continue_course_resumes_the_last_unfinished_lesson(self):
        TeachingProgress.objects.create(
            contact=self.student, teaching=self.lessons[0], completed=True)
        TeachingProgress.objects.create(
            contact=self.student, teaching=self.lessons[3], completed=False)
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(res.data['continue_course']['lesson_id'],
                         'sh-lesson-4')

    # --- assignments ---

    def test_assignment_statuses_are_derived(self):
        practice = Practice.objects.create(
            title='Morning Stillness', audience='students', minutes=15)
        now = timezone.now()
        PracticeAssignment.objects.create(
            contact=self.student, practice=practice,
            due_at=now - timedelta(days=1))
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(res.data['assigned_practices'][0]['status'],
                         'overdue')

        PracticeAssignment.objects.all().update(due_at=now + timedelta(days=1))
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(res.data['assigned_practices'][0]['status'],
                         'due_soon')

        PracticeAssignment.objects.all().update(
            due_at=now + timedelta(days=10), started_at=now)
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(res.data['assigned_practices'][0]['status'],
                         'in_progress')

    def test_completed_assignment_leaves_the_card(self):
        practice = Practice.objects.create(
            title='Done Practice', audience='students', minutes=10)
        PracticeAssignment.objects.create(
            contact=self.student, practice=practice,
            completed_at=timezone.now())
        res = self.client.get(HOME, **self._auth())
        self.assertEqual(res.data['assigned_practices'], [])

    # --- live class ---

    def test_join_is_withheld_until_the_window_opens(self):
        Activity.objects.create(
            title='Module 3 Live', kind='live', audience='public',
            starts_at=timezone.now() + timedelta(hours=3),
            duration_minutes=60)
        res = self.client.get(HOME, **self._auth())
        live = res.data['next_live_class']
        self.assertEqual(live['status'], 'upcoming')
        self.assertFalse(live['join_allowed'])
        self.assertEqual(live['join_url'], '')

    def test_class_in_progress_is_live_and_joinable(self):
        Activity.objects.create(
            title='Module 3 Live', kind='live', audience='public',
            starts_at=timezone.now() - timedelta(minutes=5),
            duration_minutes=60)
        res = self.client.get(HOME, **self._auth())
        live = res.data['next_live_class']
        self.assertEqual(live['status'], 'live')
        self.assertTrue(live['join_allowed'])
        self.assertIsNotNone(live['ends_at'])

    def test_finished_class_is_not_returned(self):
        Activity.objects.create(
            title='Yesterday Live', kind='live', audience='public',
            starts_at=timezone.now() - timedelta(days=1),
            duration_minutes=60)
        res = self.client.get(HOME, **self._auth())
        self.assertIsNone(res.data['next_live_class'])

    # --- milestone & mentor ---

    def test_next_milestone_reflects_progress(self):
        Milestone.objects.create(
            program=self.program, title='Complete Level 1',
            required_progress=50, order=1)
        TeachingProgress.objects.create(
            contact=self.student, teaching=self.lessons[0], completed=True)
        res = self.client.get(HOME, **self._auth())
        milestone = res.data['next_milestone']
        self.assertEqual(milestone['title'], 'Complete Level 1')
        self.assertEqual(milestone['current_progress'], 25)
        self.assertEqual(milestone['status'], 'in_progress')

    def test_no_mentor_returns_null_not_a_fake_one(self):
        res = self.client.get(HOME, **self._auth())
        self.assertIsNone(res.data['mentor'])

    def test_mentor_messaging_is_opt_in(self):
        mentor_contact = Contact.objects.create(
            full_name='Kofi Mentor', phone='+233200000053',
            email='kofi-mentor@example.com', is_active=True)
        worker = Worker.objects.create(
            contact=mentor_contact, role='Programme Guide')
        Mentorship.objects.create(
            student=self.student, mentor=worker,
            availability='Weekdays 9-5 GMT')
        res = self.client.get(HOME, **self._auth())
        mentor = res.data['mentor']
        self.assertEqual(mentor['display_name'], 'Kofi Mentor')
        self.assertEqual(mentor['role'], 'Programme Guide')
        self.assertFalse(mentor['messaging_enabled'])

    # --- updates ---

    def test_overdue_assignment_sorts_above_announcements(self):
        from engagement.models import Announcement
        Announcement.objects.create(
            title='General notice', body='Something', audience='students')
        practice = Practice.objects.create(
            title='Overdue Practice', audience='students', minutes=10)
        PracticeAssignment.objects.create(
            contact=self.student, practice=practice,
            due_at=timezone.now() - timedelta(days=2))
        res = self.client.get(HOME, **self._auth())
        first = res.data['updates'][0]
        self.assertEqual(first['type'], 'assignment')
        self.assertEqual(first['priority'], 'urgent')

    def test_downloads_is_not_offered_yet(self):
        res = self.client.get(HOME, **self._auth())
        ids = [a['id'] for a in res.data['quick_actions']]
        self.assertNotIn('downloads', ids)
        self.assertIn('courses', ids)
