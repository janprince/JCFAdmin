"""Upcoming Activities browse API (designs 37–41)."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import (Activity, ActivityRegistration,
                               ActivityReminder, ActivitySave)
from members.models import Contact
from mobile_api.activities_api import decode_cursor, encode_cursor
from mobile_api.models import MobileToken


def make_contact(phone, **flags):
    return Contact.objects.create(
        full_name=f'Test {phone}', phone=phone,
        email=f'{phone.strip("+")}@example.com', is_active=True, **flags)


def token_for(contact):
    return MobileToken.issue(contact)


class ActivityFactory:
    counter = 0

    @classmethod
    def create(cls, **kwargs):
        cls.counter += 1
        defaults = {
            'title': f'Activity {cls.counter}',
            'starts_at': timezone.now() + timedelta(days=cls.counter),
            'duration_minutes': 60,
            'activity_type': Activity.ActivityType.SATSANG,
            'activity_format': Activity.Format.IN_PERSON,
            'venue': 'JCF Centre',
            'city': 'Accra',
        }
        defaults.update(kwargs)
        return Activity.objects.create(**defaults)


class UpcomingFeedTests(TestCase):
    url = None

    def setUp(self):
        self.url = reverse('mobile_api:activities_upcoming')
        self.now = timezone.now()

    def get(self, contact=None, **params):
        headers = {}
        if contact is not None:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token_for(contact).access_token}'
        return self.client.get(self.url, params, **headers)

    # --- shape -----------------------------------------------------------

    def test_returns_server_time_and_timezone(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertIn('server_time', response.json())
        self.assertIn('timezone', response.json())

    def test_lists_upcoming_soonest_first(self):
        later = ActivityFactory.create(
            title='Later', starts_at=self.now + timedelta(days=5))
        sooner = ActivityFactory.create(
            title='Sooner', starts_at=self.now + timedelta(days=1))
        titles = [r['title'] for r in self.get().json()['results']]
        self.assertEqual(titles.index('Sooner') < titles.index('Later'), True)
        self.assertIn(later.title, titles)
        self.assertIn(sooner.title, titles)

    def test_excludes_finished_activities(self):
        ActivityFactory.create(
            title='Yesterday', starts_at=self.now - timedelta(days=1))
        titles = [r['title'] for r in self.get().json()['results']]
        self.assertNotIn('Yesterday', titles)

    def test_keeps_an_activity_that_is_under_way(self):
        ActivityFactory.create(
            title='Running', starts_at=self.now - timedelta(minutes=10),
            duration_minutes=90)
        titles = [r['title'] for r in self.get().json()['results']]
        self.assertIn('Running', titles)

    def test_inactive_activities_are_never_listed(self):
        ActivityFactory.create(title='Draft', is_active=False)
        titles = [r['title'] for r in self.get().json()['results']]
        self.assertNotIn('Draft', titles)

    def test_card_carries_derived_state(self):
        ActivityFactory.create(
            title='Card', activity_type=Activity.ActivityType.WORKSHOP,
            activity_format=Activity.Format.ONLINE, online_platform='Zoom',
            language='English')
        item = self.get().json()['results'][0]
        self.assertEqual(item['activity_type'], 'workshop')
        self.assertEqual(item['activity_type_label'], 'Workshop')
        self.assertEqual(item['format'], 'online')
        self.assertEqual(item['location_line'], 'Zoom')
        self.assertEqual(item['destination']['type'], 'activity')
        self.assertEqual(item['destination']['event_id'], item['id'])
        self.assertIn('ends_at', item)

    def test_hybrid_location_line_names_both_halves(self):
        ActivityFactory.create(
            activity_format=Activity.Format.HYBRID, venue='JCF Centre',
            city='Accra', online_platform='Zoom')
        item = self.get().json()['results'][0]
        self.assertEqual(item['location_line'], 'JCF Centre, Accra + Zoom')

    # --- primary filters -------------------------------------------------

    def test_live_filter_keeps_only_live_activities(self):
        ActivityFactory.create(title='Live one', kind=Activity.Kind.LIVE)
        ActivityFactory.create(title='Sitting', kind=Activity.Kind.PRACTICE)
        titles = [r['title'] for r in self.get(filter='live').json()['results']]
        self.assertEqual(titles, ['Live one'])

    def test_online_filter_includes_hybrid(self):
        ActivityFactory.create(
            title='Web', activity_format=Activity.Format.ONLINE)
        ActivityFactory.create(
            title='Both', activity_format=Activity.Format.HYBRID)
        ActivityFactory.create(
            title='Hall', activity_format=Activity.Format.IN_PERSON)
        titles = {r['title']
                  for r in self.get(filter='online').json()['results']}
        self.assertEqual(titles, {'Web', 'Both'})

    def test_in_person_filter_includes_hybrid(self):
        ActivityFactory.create(
            title='Web', activity_format=Activity.Format.ONLINE)
        ActivityFactory.create(
            title='Both', activity_format=Activity.Format.HYBRID)
        ActivityFactory.create(
            title='Hall', activity_format=Activity.Format.IN_PERSON)
        titles = {r['title']
                  for r in self.get(filter='in_person').json()['results']}
        self.assertEqual(titles, {'Hall', 'Both'})

    def test_unknown_filter_falls_back_to_all(self):
        ActivityFactory.create(title='Anything')
        body = self.get(filter='nonsense').json()
        self.assertEqual(body['applied_filter'], 'all')
        self.assertEqual(len(body['results']), 1)

    # --- advanced filters ------------------------------------------------

    def test_type_filter(self):
        ActivityFactory.create(
            title='Sit', activity_type=Activity.ActivityType.MEDITATION)
        ActivityFactory.create(
            title='Class', activity_type=Activity.ActivityType.WORKSHOP)
        titles = [r['title']
                  for r in self.get(types='meditation').json()['results']]
        self.assertEqual(titles, ['Sit'])

    def test_fee_filter_free_covers_null_and_zero(self):
        ActivityFactory.create(title='Free none', fee_amount=None)
        ActivityFactory.create(title='Free zero', fee_amount=Decimal('0'))
        ActivityFactory.create(title='Paid', fee_amount=Decimal('50'))
        titles = {r['title'] for r in self.get(fee='free').json()['results']}
        self.assertEqual(titles, {'Free none', 'Free zero'})

    def test_fee_filter_paid(self):
        ActivityFactory.create(title='Free', fee_amount=None)
        ActivityFactory.create(title='Paid', fee_amount=Decimal('50'))
        titles = [r['title'] for r in self.get(fee='paid').json()['results']]
        self.assertEqual(titles, ['Paid'])

    def test_fee_display_drops_trailing_zeros(self):
        ActivityFactory.create(
            fee_amount=Decimal('50.00'), fee_currency='GHS')
        item = self.get().json()['results'][0]
        self.assertEqual(item['fee']['display'], 'GHS 50')
        self.assertFalse(item['fee']['free'])

    def test_free_activity_reports_no_fee_display(self):
        ActivityFactory.create(fee_amount=None)
        item = self.get().json()['results'][0]
        self.assertTrue(item['fee']['free'])
        self.assertEqual(item['fee']['display'], '')

    def test_language_filter(self):
        ActivityFactory.create(title='En', language='English')
        ActivityFactory.create(title='Fr', language='French')
        titles = [r['title']
                  for r in self.get(languages='French').json()['results']]
        self.assertEqual(titles, ['Fr'])

    def test_search_matches_title_venue_and_facilitator(self):
        ActivityFactory.create(title='Morning stillness')
        ActivityFactory.create(title='Other', venue='Lakeside Hall')
        ActivityFactory.create(title='Third', facilitator_name='Ama Serwaa')
        for query, expected in (('stillness', 'Morning stillness'),
                                ('lakeside', 'Other'),
                                ('serwaa', 'Third')):
            with self.subTest(query=query):
                titles = [r['title']
                          for r in self.get(q=query).json()['results']]
                self.assertEqual(titles, [expected])

    def test_facets_count_the_window_not_the_page(self):
        for _ in range(3):
            ActivityFactory.create(
                activity_type=Activity.ActivityType.MEDITATION)
        ActivityFactory.create(activity_type=Activity.ActivityType.RETREAT)
        facets = self.get(limit=1).json()['available_filters']
        counts = {f['value']: f['count'] for f in facets['types']}
        self.assertEqual(counts['meditation'], 3)
        self.assertEqual(counts['retreat'], 1)

    # --- date window -----------------------------------------------------

    def test_day_window_selects_a_single_local_day(self):
        target = (timezone.localtime(self.now) + timedelta(days=3)).date()
        ActivityFactory.create(
            title='On the day', starts_at=self.now + timedelta(days=3))
        ActivityFactory.create(
            title='Next week', starts_at=self.now + timedelta(days=10))
        titles = [r['title'] for r in self.get(
            **{'from': target.isoformat(), 'to': target.isoformat()}
        ).json()['results']]
        self.assertEqual(titles, ['On the day'])

    def test_past_day_reads_as_empty(self):
        yesterday = (timezone.localtime(self.now) - timedelta(days=1)).date()
        ActivityFactory.create(
            title='Gone', starts_at=self.now - timedelta(days=1))
        body = self.get(**{'from': yesterday.isoformat(),
                           'to': yesterday.isoformat()}).json()
        self.assertEqual(body['results'], [])

    def test_unparseable_dates_are_ignored_rather_than_fatal(self):
        ActivityFactory.create(title='Still here')
        body = self.get(**{'from': 'not-a-date', 'to': '??'})
        self.assertEqual(body.status_code, 200)
        self.assertEqual(len(body.json()['results']), 1)

    # --- pagination ------------------------------------------------------

    def test_cursor_walks_the_whole_list_without_repeats(self):
        for index in range(7):
            ActivityFactory.create(
                title=f'Item {index}',
                starts_at=self.now + timedelta(days=index + 1))
        seen, cursor, pages = [], None, 0
        while pages < 10:
            params = {'limit': 3}
            if cursor:
                params['cursor'] = cursor
            body = self.get(**params).json()
            seen.extend(r['id'] for r in body['results'])
            cursor = body['next_cursor']
            pages += 1
            if not cursor:
                break
        self.assertEqual(len(seen), 7)
        self.assertEqual(len(set(seen)), 7)

    def test_ties_on_start_time_are_broken_by_id(self):
        stamp = self.now + timedelta(days=2)
        first = ActivityFactory.create(title='Tie A', starts_at=stamp)
        second = ActivityFactory.create(title='Tie B', starts_at=stamp)
        page_one = self.get(limit=1).json()
        self.assertEqual(page_one['results'][0]['id'], first.id)
        page_two = self.get(limit=1, cursor=page_one['next_cursor']).json()
        self.assertEqual(page_two['results'][0]['id'], second.id)

    def test_last_page_has_no_cursor(self):
        ActivityFactory.create()
        self.assertIsNone(self.get(limit=5).json()['next_cursor'])

    def test_a_corrupt_cursor_returns_page_one_not_an_error(self):
        ActivityFactory.create(title='Only')
        body = self.get(cursor='%%%not-base64%%%')
        self.assertEqual(body.status_code, 200)
        self.assertEqual(len(body.json()['results']), 1)

    def test_cursor_round_trip(self):
        activity = ActivityFactory.create()
        stamp, ident = decode_cursor(encode_cursor(activity))
        self.assertEqual(ident, activity.id)
        self.assertEqual(stamp, activity.starts_at)

    def test_limit_is_capped(self):
        for _ in range(3):
            ActivityFactory.create()
        self.assertEqual(len(self.get(limit=9999).json()['results']), 3)

    # --- featured --------------------------------------------------------

    def test_featured_is_the_soonest_flagged_activity(self):
        ActivityFactory.create(
            title='Far', is_featured=True,
            starts_at=self.now + timedelta(days=20))
        ActivityFactory.create(
            title='Near', is_featured=True, featured_blurb='Join us',
            starts_at=self.now + timedelta(days=2))
        featured = self.get().json()['featured_activity']
        self.assertEqual(featured['title'], 'Near')
        self.assertEqual(featured['featured_blurb'], 'Join us')

    def test_featured_is_absent_when_nothing_is_flagged(self):
        ActivityFactory.create()
        self.assertIsNone(self.get().json()['featured_activity'])

    def test_featured_never_advertises_something_locked(self):
        ActivityFactory.create(
            title='Members only', is_featured=True,
            audience=Activity.Audience.MEMBERS)
        self.assertIsNone(self.get().json()['featured_activity'])

    def test_featured_is_omitted_on_later_pages(self):
        ActivityFactory.create(is_featured=True)
        for _ in range(3):
            ActivityFactory.create()
        page_one = self.get(limit=1).json()
        self.assertIsNotNone(page_one['featured_activity'])
        page_two = self.get(limit=1, cursor=page_one['next_cursor']).json()
        self.assertIsNone(page_two['featured_activity'])

    def test_cancelled_activities_are_not_featured(self):
        ActivityFactory.create(is_featured=True, cancelled=True)
        self.assertIsNone(self.get().json()['featured_activity'])

    # --- visibility ladder ----------------------------------------------

    def test_guest_sees_members_only_activity_locked(self):
        ActivityFactory.create(
            title='Members', audience=Activity.Audience.MEMBERS)
        item = self.get().json()['results'][0]
        self.assertFalse(item['access']['allowed'])
        self.assertTrue(item['access']['sign_in_required'])
        self.assertEqual(item['access']['reason'], 'sign_in')

    def test_guest_never_sees_students_only_activity(self):
        ActivityFactory.create(
            title='Students', audience=Activity.Audience.STUDENTS)
        self.assertEqual(self.get().json()['results'], [])

    def test_member_sees_students_activity_locked(self):
        member = make_contact('+233200000001', is_member=True)
        ActivityFactory.create(
            title='Students', audience=Activity.Audience.STUDENTS)
        item = self.get(member).json()['results'][0]
        self.assertFalse(item['access']['allowed'])
        self.assertEqual(item['access']['reason'], 'students_only')

    def test_student_opens_everything(self):
        student = make_contact('+233200000002', is_student=True)
        ActivityFactory.create(audience=Activity.Audience.STUDENTS)
        item = self.get(student).json()['results'][0]
        self.assertTrue(item['access']['allowed'])

    def test_open_to_me_filter_drops_locked_items_for_a_guest(self):
        ActivityFactory.create(
            title='Open', audience=Activity.Audience.PUBLIC)
        ActivityFactory.create(
            title='Locked', audience=Activity.Audience.MEMBERS)
        titles = [r['title']
                  for r in self.get(access='open_to_me').json()['results']]
        self.assertEqual(titles, ['Open'])

    # --- personal state --------------------------------------------------

    def test_guest_state_is_all_false(self):
        ActivityFactory.create()
        item = self.get().json()['results'][0]
        self.assertFalse(item['reminder_set'])
        self.assertFalse(item['saved'])
        self.assertIsNone(item['registration']['my_status'])

    def test_reminders_saves_and_registrations_are_reported(self):
        member = make_contact('+233200000003', is_member=True)
        activity = ActivityFactory.create(registration_required=True)
        ActivityReminder.objects.create(contact=member, activity=activity)
        ActivitySave.objects.create(contact=member, activity=activity)
        ActivityRegistration.objects.create(contact=member, activity=activity)
        item = self.get(member).json()['results'][0]
        self.assertTrue(item['reminder_set'])
        self.assertTrue(item['saved'])
        self.assertEqual(item['registration']['my_status'], 'registered')

    # --- live and lifecycle ---------------------------------------------

    def test_live_now_flag(self):
        ActivityFactory.create(
            kind=Activity.Kind.LIVE,
            starts_at=self.now - timedelta(minutes=5), duration_minutes=60)
        item = self.get().json()['results'][0]
        self.assertTrue(item['is_live_now'])

    def test_starting_soon_flag(self):
        ActivityFactory.create(starts_at=self.now + timedelta(minutes=30))
        self.assertTrue(self.get().json()['results'][0]['starting_soon'])

    def test_cancelled_activity_is_shown_and_marked(self):
        ActivityFactory.create(
            title='Off', cancelled=True, rescheduled_note='Moved to Friday')
        item = self.get().json()['results'][0]
        self.assertTrue(item['cancelled'])
        self.assertEqual(item['rescheduled_note'], 'Moved to Friday')
        self.assertFalse(item['is_live_now'])


class RegistrationStateTests(TestCase):
    def setUp(self):
        self.now = timezone.now()

    def test_not_required(self):
        activity = ActivityFactory.create(registration_required=False)
        self.assertEqual(activity.registration_state(self.now),
                         'not_required')

    def test_opens_later(self):
        activity = ActivityFactory.create(
            registration_required=True,
            registration_opens_at=self.now + timedelta(days=1))
        self.assertEqual(activity.registration_state(self.now), 'opens_later')

    def test_open(self):
        activity = ActivityFactory.create(
            registration_required=True, capacity=10,
            starts_at=self.now + timedelta(days=3))
        self.assertEqual(activity.registration_state(self.now), 'open')

    def test_full_without_waitlist(self):
        activity = ActivityFactory.create(
            registration_required=True, capacity=1,
            starts_at=self.now + timedelta(days=3))
        ActivityRegistration.objects.create(
            contact=make_contact('+233200000010'), activity=activity)
        self.assertEqual(activity.registration_state(self.now), 'full')

    def test_full_with_waitlist(self):
        activity = ActivityFactory.create(
            registration_required=True, capacity=1, waitlist_enabled=True,
            starts_at=self.now + timedelta(days=3))
        ActivityRegistration.objects.create(
            contact=make_contact('+233200000011'), activity=activity)
        self.assertEqual(activity.registration_state(self.now), 'waitlist')

    def test_cancelled_registration_frees_the_seat(self):
        activity = ActivityFactory.create(
            registration_required=True, capacity=1,
            starts_at=self.now + timedelta(days=3))
        ActivityRegistration.objects.create(
            contact=make_contact('+233200000012'), activity=activity,
            status=ActivityRegistration.Status.CANCELLED)
        self.assertEqual(activity.registration_state(self.now), 'open')

    def test_closes_defaults_to_start_time(self):
        activity = ActivityFactory.create(
            registration_required=True,
            starts_at=self.now - timedelta(minutes=5), duration_minutes=90)
        self.assertEqual(activity.registration_state(self.now), 'closed')

    def test_cancelled_activity_beats_every_other_state(self):
        activity = ActivityFactory.create(
            registration_required=True, cancelled=True, capacity=10,
            starts_at=self.now + timedelta(days=3))
        self.assertEqual(activity.registration_state(self.now), 'cancelled')

    def test_external_registration(self):
        activity = ActivityFactory.create(
            registration_required=True,
            external_registration_url='https://example.org/signup',
            starts_at=self.now + timedelta(days=3))
        self.assertEqual(activity.registration_state(self.now), 'external')

    def test_seats_left_is_none_when_uncapped(self):
        self.assertIsNone(ActivityFactory.create().seats_left())


class RegistrationEndpointTests(TestCase):
    def setUp(self):
        self.url = reverse('mobile_api:activities_register')
        self.member = make_contact('+233200000020', is_member=True)
        self.auth = {'HTTP_AUTHORIZATION':
                     f'Bearer {token_for(self.member).access_token}'}
        self.now = timezone.now()

    def post(self, **data):
        return self.client.post(
            self.url, data, content_type='application/json', **self.auth)

    def test_guest_cannot_register(self):
        activity = ActivityFactory.create(registration_required=True)
        response = self.client.post(
            self.url, {'activity_id': activity.id},
            content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_register_takes_a_seat(self):
        activity = ActivityFactory.create(
            registration_required=True, capacity=5,
            starts_at=self.now + timedelta(days=2))
        response = self.post(activity_id=activity.id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['my_status'], 'registered')
        self.assertEqual(activity.seats_left(), 4)

    def test_registering_twice_is_idempotent(self):
        activity = ActivityFactory.create(
            registration_required=True, capacity=5,
            starts_at=self.now + timedelta(days=2))
        self.post(activity_id=activity.id)
        second = self.post(activity_id=activity.id)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(activity.seats_taken(), 1)

    def test_full_activity_with_waitlist_waitlists(self):
        activity = ActivityFactory.create(
            registration_required=True, capacity=1, waitlist_enabled=True,
            starts_at=self.now + timedelta(days=2))
        ActivityRegistration.objects.create(
            contact=make_contact('+233200000021'), activity=activity)
        response = self.post(activity_id=activity.id)
        self.assertEqual(response.json()['my_status'], 'waitlisted')

    def test_full_activity_without_waitlist_is_refused(self):
        activity = ActivityFactory.create(
            registration_required=True, capacity=1,
            starts_at=self.now + timedelta(days=2))
        ActivityRegistration.objects.create(
            contact=make_contact('+233200000022'), activity=activity)
        response = self.post(activity_id=activity.id)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['state'], 'full')

    def test_closed_registration_is_refused(self):
        activity = ActivityFactory.create(
            registration_required=True,
            registration_closes_at=self.now - timedelta(hours=1),
            starts_at=self.now + timedelta(days=2))
        self.assertEqual(self.post(activity_id=activity.id).status_code, 409)

    def test_external_registration_hands_back_the_url(self):
        activity = ActivityFactory.create(
            registration_required=True,
            external_registration_url='https://example.org/signup',
            starts_at=self.now + timedelta(days=2))
        response = self.post(activity_id=activity.id)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['external_url'],
                         'https://example.org/signup')

    def test_cannot_register_for_something_out_of_reach(self):
        activity = ActivityFactory.create(
            registration_required=True,
            audience=Activity.Audience.STUDENTS,
            starts_at=self.now + timedelta(days=2))
        self.assertEqual(self.post(activity_id=activity.id).status_code, 403)

    def test_cancelling_releases_the_seat(self):
        activity = ActivityFactory.create(
            registration_required=True, capacity=1,
            starts_at=self.now + timedelta(days=2))
        self.post(activity_id=activity.id)
        response = self.post(activity_id=activity.id, cancel=True)
        self.assertIsNone(response.json()['my_status'])
        self.assertEqual(activity.seats_left(), 1)

    def test_unknown_activity_is_404(self):
        self.assertEqual(self.post(activity_id=999999).status_code, 404)


class SaveEndpointTests(TestCase):
    def setUp(self):
        self.url = reverse('mobile_api:activities_save')
        self.member = make_contact('+233200000030', is_member=True)
        self.auth = {'HTTP_AUTHORIZATION':
                     f'Bearer {token_for(self.member).access_token}'}

    def test_toggles_on_and_off(self):
        activity = ActivityFactory.create()
        first = self.client.post(
            self.url, {'activity_id': activity.id},
            content_type='application/json', **self.auth)
        self.assertTrue(first.json()['saved'])
        second = self.client.post(
            self.url, {'activity_id': activity.id},
            content_type='application/json', **self.auth)
        self.assertFalse(second.json()['saved'])
        self.assertEqual(ActivitySave.objects.count(), 0)

    def test_saving_does_not_register(self):
        activity = ActivityFactory.create(registration_required=True)
        self.client.post(
            self.url, {'activity_id': activity.id},
            content_type='application/json', **self.auth)
        self.assertEqual(ActivityRegistration.objects.count(), 0)

    def test_guest_cannot_save(self):
        activity = ActivityFactory.create()
        response = self.client.post(
            self.url, {'activity_id': activity.id},
            content_type='application/json')
        self.assertEqual(response.status_code, 401)


class CalendarTests(TestCase):
    def setUp(self):
        self.url = reverse('mobile_api:activities_calendar')
        self.now = timezone.now()

    def test_counts_activities_per_local_day(self):
        day = timezone.localtime(self.now) + timedelta(days=2)
        ActivityFactory.create(starts_at=self.now + timedelta(days=2))
        ActivityFactory.create(
            starts_at=self.now + timedelta(days=2, hours=1))
        body = self.client.get(
            self.url, {'month': f'{day.year:04d}-{day.month:02d}'}).json()
        entry = next(d for d in body['days'] if d['date'] == day.date()
                     .isoformat())
        self.assertEqual(entry['count'], 2)

    def test_marks_days_with_a_live_session(self):
        day = timezone.localtime(self.now) + timedelta(days=3)
        ActivityFactory.create(
            kind=Activity.Kind.LIVE, starts_at=self.now + timedelta(days=3))
        body = self.client.get(
            self.url, {'month': f'{day.year:04d}-{day.month:02d}'}).json()
        entry = next(d for d in body['days'] if d['date'] == day.date()
                     .isoformat())
        self.assertTrue(entry['has_live'])

    def test_days_are_sorted_and_sparse(self):
        ActivityFactory.create(starts_at=self.now + timedelta(days=1))
        body = self.client.get(self.url).json()
        dates = [d['date'] for d in body['days']]
        self.assertEqual(dates, sorted(dates))

    def test_bad_month_falls_back_to_the_current_one(self):
        body = self.client.get(self.url, {'month': 'oops'}).json()
        today = timezone.localdate()
        self.assertEqual(body['month'], f'{today.year:04d}-{today.month:02d}')

    def test_calendar_honours_the_primary_filter(self):
        day = timezone.localtime(self.now) + timedelta(days=4)
        ActivityFactory.create(
            kind=Activity.Kind.PRACTICE,
            starts_at=self.now + timedelta(days=4))
        body = self.client.get(
            self.url, {'month': f'{day.year:04d}-{day.month:02d}',
                       'filter': 'live'}).json()
        self.assertEqual(body['days'], [])


class ActivityDetailTests(TestCase):
    def test_returns_the_same_shape_as_a_row(self):
        activity = ActivityFactory.create(title='Detail')
        response = self.client.get(
            reverse('mobile_api:activities_detail', args=[activity.id]))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['title'], 'Detail')
        self.assertIn('registration', body)
        self.assertIn('server_time', body)

    def test_hidden_activity_is_404(self):
        activity = ActivityFactory.create(
            audience=Activity.Audience.STUDENTS)
        response = self.client.get(
            reverse('mobile_api:activities_detail', args=[activity.id]))
        self.assertEqual(response.status_code, 404)
