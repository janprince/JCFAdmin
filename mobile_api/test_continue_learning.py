"""Continue Learning API (owner spec + designs 43–47)."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from members.models import Contact
from mobile_api.continue_learning_api import decode_cursor, encode_cursor
from mobile_api.models import MobileToken
from programs.models import Program
from studies.models import Enrolment
from teachings.models import (Teaching, TeachingModule, TeachingProgress,
                              TeachingSeries)


def make_contact(phone, **flags):
    return Contact.objects.create(
        full_name=f'Test {phone}', phone=phone,
        email=f'{phone.strip("+")}@example.com', is_active=True, **flags)


class Base(TestCase):
    counter = 0

    def setUp(self):
        self.url = reverse('mobile_api:learning_continue')
        self.member = make_contact('+233900000001', is_member=True)
        self.now = timezone.now()

    def enrol(self, series, **kwargs):
        Base.counter += 1
        program = Program.objects.get_or_create(
            title=f'Programme {Base.counter}',
            defaults={'year': 2026, 'audience': 'public',
                      'is_published': True})[0]
        return Enrolment.objects.create(
            contact=kwargs.pop('contact', self.member), program=program,
            series=series, **kwargs)

    def auth(self, contact=None):
        token = MobileToken.issue(contact or self.member)
        return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}

    def get(self, contact=None, **params):
        return self.client.get(self.url, params, **self.auth(contact))

    def series(self, title=None, **kwargs):
        Base.counter += 1
        return TeachingSeries.objects.create(
            title=title or f'Series {Base.counter}', **kwargs)

    def lesson(self, series=None, topic=None, order=0, **kwargs):
        Base.counter += 1
        kwargs.setdefault('status', Teaching.Status.PUBLISHED)
        return Teaching.objects.create(
            topic=topic or f'Lesson {Base.counter}', series=series,
            order=order, **kwargs)

    def progress(self, teaching, percent=0, completed=False, contact=None,
                 viewed=None):
        row = TeachingProgress.objects.create(
            contact=contact or self.member, teaching=teaching,
            percent=percent, completed=completed)
        if viewed is not None:
            TeachingProgress.objects.filter(pk=row.pk).update(
                last_viewed_at=viewed)
            row.refresh_from_db()
        return row


class AuthTests(Base):
    def test_a_guest_gets_nothing(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_a_member_gets_the_payload(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        for key in ('resume_item', 'learning_summary', 'active_courses',
                    'up_next_lessons', 'recommendations', 'server_time'):
            self.assertIn(key, response.json())


class ResumeItemTests(Base):
    def test_no_history_means_no_resume_item(self):
        self.assertIsNone(self.get().json()['resume_item'])

    def test_the_most_recently_touched_unfinished_lesson_wins(self):
        course = self.series()
        old = self.lesson(course, topic='Older', order=1)
        recent = self.lesson(course, topic='Recent', order=2)
        self.progress(old, percent=30,
                      viewed=self.now - timedelta(days=3))
        self.progress(recent, percent=40,
                      viewed=self.now - timedelta(hours=1))
        self.assertEqual(self.get().json()['resume_item']['title'], 'Recent')

    def test_a_completed_lesson_is_never_the_resume_item(self):
        course = self.series()
        done = self.lesson(course, topic='Done', order=1)
        nxt = self.lesson(course, topic='Next up', order=2)
        self.progress(done, percent=100, completed=True,
                      viewed=self.now - timedelta(minutes=5))
        resume = self.get().json()['resume_item']
        self.assertEqual(resume['title'], nxt.topic)

    def test_it_falls_back_to_the_first_lesson_of_a_new_enrolment(self):
        course = self.series()
        first = self.lesson(course, topic='Opening', order=1)
        self.lesson(course, topic='Second', order=2)
        self.enrol(course)
        self.assertEqual(self.get().json()['resume_item']['title'],
                         first.topic)

    def test_a_locked_lesson_is_never_offered(self):
        course = self.series()
        gate = self.lesson(course, topic='Gate', order=1)
        locked = self.lesson(course, topic='Locked', order=2,
                             prerequisite=gate)
        self.progress(locked, percent=10,
                      viewed=self.now - timedelta(minutes=1))
        resume = self.get().json()['resume_item']
        # It must offer the unmet prerequisite, not the locked lesson.
        self.assertNotEqual(resume['title'], 'Locked')

    def test_premium_content_is_not_offered_to_a_plain_contact(self):
        """The screen still opens — it is their own learning hub — but a
        lesson they cannot play is never the thing it offers to resume."""
        plain = make_contact('+233900000009')
        course = self.series()
        premium = self.lesson(course, topic='Premium',
                              tier=Teaching.Tier.PREMIUM)
        self.progress(premium, percent=20, contact=plain)
        response = self.client.get(self.url, **self.auth(plain))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['resume_item'])

    def test_premium_content_is_offered_to_a_member(self):
        course = self.series()
        self.lesson(course, topic='Premium', tier=Teaching.Tier.PREMIUM)
        self.progress(Teaching.objects.get(topic='Premium'), percent=20)
        self.assertEqual(
            self.get().json()['resume_item']['title'], 'Premium')

    def test_an_unpublished_lesson_is_skipped(self):
        course = self.series()
        draft = self.lesson(course, topic='Draft', order=1,
                            status=Teaching.Status.PENDING)
        self.progress(draft, percent=50)
        self.assertIsNone(self.get().json()['resume_item'])

    def test_the_resume_item_reports_remaining_time(self):
        course = self.series()
        lesson = self.lesson(course, topic='Timed', duration_seconds=600)
        row = self.progress(lesson, percent=50)
        row.position_seconds = 240
        row.save()
        resume = self.get().json()['resume_item']
        self.assertEqual(resume['duration_seconds'], 600)
        self.assertEqual(resume['remaining_seconds'], 360)

    def test_the_destination_is_an_identifier_not_a_route(self):
        course = self.series()
        lesson = self.lesson(course, lesson_type=Teaching.LessonType.AUDIO)
        self.progress(lesson, percent=10)
        destination = self.get().json()['resume_item']['destination']
        self.assertEqual(destination['type'], 'audio')
        self.assertEqual(destination['lesson_id'], lesson.id)


class SummaryTests(Base):
    def test_completed_lessons_are_counted_over_everything(self):
        course = self.series()
        for i in range(3):
            self.progress(self.lesson(course, order=i), percent=100,
                          completed=True)
        summary = self.get(limit=1).json()['learning_summary']
        # A page limit of one must not shrink the total.
        self.assertEqual(summary['completed_lessons'], 3)

    def test_a_course_counts_as_complete_only_when_every_lesson_is(self):
        course = self.series()
        a = self.lesson(course, order=1)
        b = self.lesson(course, order=2)
        self.progress(a, percent=100, completed=True)
        self.assertEqual(
            self.get().json()['learning_summary']['completed_courses'], 0)
        self.progress(b, percent=100, completed=True)
        self.assertEqual(
            self.get().json()['learning_summary']['completed_courses'], 1)

    def test_streak_counts_consecutive_days_back_from_today(self):
        course = self.series()
        for days in (0, 1, 2):
            self.progress(self.lesson(course, order=days), percent=20,
                          viewed=self.now - timedelta(days=days))
        self.assertEqual(
            self.get().json()['learning_summary']['current_streak_days'], 3)

    def test_a_lapsed_streak_reads_as_zero(self):
        course = self.series()
        self.progress(self.lesson(course), percent=20,
                      viewed=self.now - timedelta(days=5))
        self.assertEqual(
            self.get().json()['learning_summary']['current_streak_days'], 0)

    def test_a_gap_ends_the_streak(self):
        course = self.series()
        for days in (0, 1, 4):
            self.progress(self.lesson(course, order=days), percent=20,
                          viewed=self.now - timedelta(days=days))
        self.assertEqual(
            self.get().json()['learning_summary']['current_streak_days'], 2)

    def test_no_history_is_a_zero_streak_not_an_error(self):
        self.assertEqual(
            self.get().json()['learning_summary']['current_streak_days'], 0)


class ActiveCourseTests(Base):
    def test_an_enrolled_course_appears(self):
        course = self.series(title='Enrolled')
        self.lesson(course)
        self.enrol(course)
        titles = [c['title']
                  for c in self.get().json()['active_courses']['results']]
        self.assertEqual(titles, ['Enrolled'])

    def test_a_course_merely_started_also_counts_as_active(self):
        course = self.series(title='Started')
        self.progress(self.lesson(course), percent=10)
        titles = [c['title']
                  for c in self.get().json()['active_courses']['results']]
        self.assertEqual(titles, ['Started'])

    def test_progress_is_the_share_of_completed_lessons(self):
        course = self.series()
        a = self.lesson(course, order=1)
        self.lesson(course, order=2)
        self.lesson(course, order=3)
        self.lesson(course, order=4)
        self.progress(a, percent=100, completed=True)
        row = self.get().json()['active_courses']['results'][0]
        self.assertEqual(row['progress_percentage'], 25)
        self.assertEqual(row['completed_lessons'], 1)
        self.assertEqual(row['total_lessons'], 4)

    def test_a_finished_course_reports_completed(self):
        course = self.series()
        self.progress(self.lesson(course), percent=100, completed=True)
        self.assertEqual(
            self.get().json()['active_courses']['results'][0]['status'],
            'completed')

    def test_an_expired_enrolment_reports_expired_and_locked(self):
        course = self.series()
        self.lesson(course)
        self.enrol(course, access_expires_at=self.now - timedelta(days=1))
        row = self.get().json()['active_courses']['results'][0]
        self.assertEqual(row['status'], 'expired')
        self.assertFalse(row['access']['allowed'])
        self.assertEqual(row['access']['restriction_reason'], 'expired')

    def test_modules_are_counted_when_they_exist(self):
        course = self.series()
        module = TeachingModule.objects.create(series=course, title='One')
        self.progress(self.lesson(course, module=module), percent=100,
                      completed=True)
        row = self.get().json()['active_courses']['results'][0]
        self.assertEqual(row['total_modules'], 1)
        self.assertEqual(row['completed_modules'], 1)

    def test_a_course_without_modules_reports_zero_not_a_guess(self):
        course = self.series()
        self.progress(self.lesson(course), percent=20)
        row = self.get().json()['active_courses']['results'][0]
        self.assertEqual(row['total_modules'], 0)

    def test_the_current_lesson_is_the_first_unfinished_one(self):
        course = self.series()
        a = self.lesson(course, order=1)
        b = self.lesson(course, order=2)
        self.progress(a, percent=100, completed=True)
        row = self.get().json()['active_courses']['results'][0]
        self.assertEqual(row['current_lesson_id'], b.id)


class UpNextTests(Base):
    def test_completed_lessons_are_excluded(self):
        course = self.series()
        done = self.lesson(course, topic='Finished', order=1)
        todo = self.lesson(course, topic='Pending', order=2)
        self.progress(done, percent=100, completed=True)
        titles = [l['title']
                  for l in self.get().json()['up_next_lessons']['results']]
        self.assertEqual(titles, ['Pending'])

    def test_a_lesson_with_an_unmet_prerequisite_is_locked(self):
        course = self.series()
        gate = self.lesson(course, topic='Gate', order=1)
        self.lesson(course, topic='Gated', order=2, prerequisite=gate)
        self.enrol(course)
        rows = {l['title']: l
                for l in self.get().json()['up_next_lessons']['results']}
        self.assertEqual(rows['Gated']['status'], 'locked')
        self.assertFalse(rows['Gated']['prerequisite']['satisfied'])
        self.assertEqual(rows['Gated']['prerequisite']['prerequisite_title'],
                         'Gate')

    def test_a_satisfied_prerequisite_unlocks_the_lesson(self):
        course = self.series()
        gate = self.lesson(course, topic='Gate', order=1)
        self.lesson(course, topic='Gated', order=2, prerequisite=gate)
        self.progress(gate, percent=100, completed=True)
        rows = {l['title']: l
                for l in self.get().json()['up_next_lessons']['results']}
        self.assertEqual(rows['Gated']['status'], 'not_started')
        self.assertTrue(rows['Gated']['prerequisite']['satisfied'])

    def test_content_type_filter(self):
        course = self.series()
        self.lesson(course, topic='Watch',
                    lesson_type=Teaching.LessonType.VIDEO)
        self.lesson(course, topic='Read',
                    lesson_type=Teaching.LessonType.WRITTEN)
        self.enrol(course)
        titles = [l['title'] for l in self.get(
            content_type='written').json()['up_next_lessons']['results']]
        self.assertEqual(titles, ['Read'])

    def test_a_non_downloadable_lesson_says_so(self):
        course = self.series()
        self.lesson(course, downloadable=False)
        self.enrol(course)
        download = self.get().json()[
            'up_next_lessons']['results'][0]['download']
        self.assertFalse(download['downloadable'])
        self.assertEqual(download['state'], 'unavailable')

    def test_a_downloadable_lesson_starts_not_downloaded(self):
        course = self.series()
        self.lesson(course, downloadable=True)
        self.enrol(course)
        download = self.get().json()[
            'up_next_lessons']['results'][0]['download']
        self.assertTrue(download['downloadable'])
        self.assertEqual(download['state'], 'not_downloaded')

    def test_in_progress_status(self):
        course = self.series()
        lesson = self.lesson(course)
        self.progress(lesson, percent=45)
        row = self.get().json()['up_next_lessons']['results'][0]
        self.assertEqual(row['status'], 'in_progress')
        self.assertEqual(row['progress_percentage'], 45)


class PaginationTests(Base):
    def test_lesson_cursor_walks_without_repeats(self):
        course = self.series()
        for i in range(7):
            self.lesson(course, order=i)
        self.enrol(course)
        seen, cursor, pages = [], None, 0
        while pages < 10:
            params = {'limit': 3}
            if cursor:
                params['lesson_cursor'] = cursor
            body = self.get(**params).json()['up_next_lessons']
            seen += [l['lesson_id'] for l in body['results']]
            cursor = body['next_cursor']
            pages += 1
            if not cursor:
                break
        self.assertEqual(len(seen), 7)
        self.assertEqual(len(set(seen)), 7)

    def test_course_cursor_walks_without_repeats(self):
        for _ in range(5):
            course = self.series()
            self.lesson(course)
            self.enrol(course)
        seen, cursor, pages = [], None, 0
        while pages < 10:
            params = {'limit': 2}
            if cursor:
                params['course_cursor'] = cursor
            body = self.get(**params).json()['active_courses']
            seen += [c['course_id'] for c in body['results']]
            cursor = body['next_cursor']
            pages += 1
            if not cursor:
                break
        self.assertEqual(len(set(seen)), 5)

    def test_a_corrupt_cursor_returns_page_one(self):
        course = self.series()
        self.lesson(course)
        self.enrol(course)
        body = self.get(lesson_cursor='%%%not-base64%%%')
        self.assertEqual(body.status_code, 200)
        self.assertEqual(
            len(body.json()['up_next_lessons']['results']), 1)

    def test_limit_is_capped(self):
        course = self.series()
        for i in range(3):
            self.lesson(course, order=i)
        self.enrol(course)
        body = self.get(limit=99999).json()
        self.assertEqual(len(body['up_next_lessons']['results']), 3)

    def test_cursor_round_trip(self):
        self.assertEqual(decode_cursor(encode_cursor(42)), ['42'])

    def test_has_more_matches_the_cursor(self):
        course = self.series()
        for i in range(4):
            self.lesson(course, order=i)
        self.enrol(course)
        body = self.get(limit=2).json()['up_next_lessons']
        self.assertTrue(body['has_more'])
        self.assertIsNotNone(body['next_cursor'])


class RecommendationTests(Base):
    def test_a_flagged_course_is_recommended(self):
        self.series(title='Suggested', is_recommended=True,
                    recommendation_reason='Continue your learning path')
        rows = self.get().json()['recommendations']
        self.assertEqual(rows[0]['title'], 'Suggested')
        self.assertEqual(rows[0]['recommendation_reason'],
                         'Continue your learning path')

    def test_an_active_course_is_never_recommended(self):
        course = self.series(title='Already mine', is_recommended=True)
        self.progress(self.lesson(course), percent=10)
        self.assertEqual(self.get().json()['recommendations'], [])

    def test_an_unflagged_course_is_not_recommended(self):
        self.series(title='Ordinary')
        self.assertEqual(self.get().json()['recommendations'], [])


class ProgressWriteTests(Base):
    def url_for(self, lesson):
        return reverse('mobile_api:learning_lesson_progress',
                       args=[lesson.id])

    def post(self, lesson, **data):
        return self.client.post(
            self.url_for(lesson), data, content_type='application/json',
            **self.auth())

    def test_a_guest_cannot_write_progress(self):
        lesson = self.lesson(self.series())
        response = self.client.post(
            self.url_for(lesson), {'percent': 10},
            content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_progress_is_recorded(self):
        lesson = self.lesson(self.series(), duration_seconds=600)
        body = self.post(lesson, percent=40, position_seconds=240).json()
        self.assertEqual(body['progress_percentage'], 40)
        self.assertEqual(body['position_seconds'], 240)
        self.assertFalse(body['completed'])

    def test_progress_never_moves_backwards(self):
        lesson = self.lesson(self.series())
        self.post(lesson, percent=60, position_seconds=300)
        body = self.post(lesson, percent=10, position_seconds=20).json()
        self.assertEqual(body['progress_percentage'], 60)
        self.assertEqual(body['position_seconds'], 300)

    def test_reaching_the_threshold_completes_the_lesson(self):
        lesson = self.lesson(self.series())
        body = self.post(lesson, percent=92).json()
        self.assertTrue(body['completed'])
        self.assertEqual(body['progress_percentage'], 100)

    def test_opening_a_lesson_does_not_complete_it(self):
        lesson = self.lesson(self.series())
        body = self.post(lesson, percent=0, position_seconds=0).json()
        self.assertFalse(body['completed'])

    def test_out_of_range_percentages_are_clamped(self):
        lesson = self.lesson(self.series())
        self.assertEqual(
            self.post(lesson, percent=-40).json()['progress_percentage'], 0)
        self.assertTrue(
            self.post(lesson, percent=9999).json()['completed'])

    def test_a_premium_lesson_refuses_a_plain_contact(self):
        plain = make_contact('+233900000021')
        lesson = self.lesson(self.series(), tier=Teaching.Tier.PREMIUM)
        token = MobileToken.issue(plain)
        response = self.client.post(
            self.url_for(lesson), {'percent': 10},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.assertEqual(response.status_code, 403)

    def test_an_unknown_lesson_is_404(self):
        lesson = self.lesson(self.series(),
                             status=Teaching.Status.PENDING)
        self.assertEqual(self.post(lesson, percent=10).status_code, 404)

    def test_a_non_numeric_percent_is_refused(self):
        lesson = self.lesson(self.series())
        self.assertEqual(
            self.post(lesson, percent='half').status_code, 400)
