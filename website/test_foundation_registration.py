from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from centres.models import Centre
from members.models import Contact
from website.models import FoundationRegistration, JoinCentreRequest, NewsletterSubscriber


class FoundationRegistrationTests(TestCase):
    endpoint = '/api/join-foundation/'

    def setUp(self):
        cache.clear()
        self.api = APIClient()
        self.payload = dict(name='  Sample Joiner  ', email='  JOINER@example.com ', country=' Ghana ', region=' Greater Accra ', phone='')

    def register(self, **changes):
        return self.api.post(self.endpoint, {**self.payload, **changes}, format='json')

    def user(self, role):
        user = get_user_model().objects.create_user(username=role, email=f'{role}@example.com', password='test-only-password')
        user.profile.role = role; user.profile.save()
        return user

    def test_public_form_contract_saves_before_success_without_other_enrolments(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {'status': 'registered'})
        record = FoundationRegistration.objects.get()
        self.assertEqual((record.name, record.email, record.country, record.region), ('Sample Joiner', 'joiner@example.com', 'Ghana', 'Greater Accra'))
        self.assertFalse(record.phone)
        self.assertIsNone(record.reviewed_at)
        self.assertFalse(Contact.objects.exists())
        self.assertFalse(JoinCentreRequest.objects.exists())
        self.assertFalse(NewsletterSubscriber.objects.exists())
        self.assertFalse(get_user_model().objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_optional_fields_can_be_omitted_and_international_phone_is_normalized(self):
        response = self.api.post(self.endpoint, {'name':'Sample', 'email':'sample@example.com', 'country':'United Kingdom'}, format='json')
        self.assertEqual(response.status_code, 201)
        response = self.register(phone='+44 20 7946 0958')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(FoundationRegistration.objects.get(email='joiner@example.com').phone), '+442079460958')

    def test_required_fields_lengths_email_and_phone_are_validated(self):
        for field,value in [('name','  '),('name','a'*151),('email','invalid'),('country',' '),('country','a'*101),('region','a'*101),('phone','0240000010'),('phone','+123')]:
            with self.subTest(field=field,value=value):
                response = self.register(**{field:value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertFalse(FoundationRegistration.objects.exists())

    def test_retry_deduplicates_email_without_overwriting_original_details(self):
        first = self.register()
        record = FoundationRegistration.objects.get()
        reviewer = self.user('secretary')
        from django.utils import timezone
        record.reviewed_at = timezone.now(); record.reviewed_by = reviewer; record.save()
        second = self.register(email='joiner@EXAMPLE.com', name='Someone else', country='Elsewhere')
        self.assertEqual(first.json(), second.json())
        self.assertEqual(second.status_code, 201)
        self.assertEqual(FoundationRegistration.objects.count(), 1)
        record.refresh_from_db()
        self.assertEqual(record.name, 'Sample Joiner')
        self.assertEqual(record.country, 'Ghana')
        self.assertIsNotNone(record.reviewed_at)

    def test_public_endpoint_cannot_list_read_update_or_review_records(self):
        self.register(reviewed_at='2026-01-01', reviewed_by=1, is_member=True)
        record = FoundationRegistration.objects.get()
        self.assertIsNone(record.reviewed_at)
        self.assertIsNone(record.reviewed_by)
        for method in (self.api.get, self.api.put, self.api.patch, self.api.delete):
            self.assertEqual(method(self.endpoint).status_code, 405)
        self.assertEqual(self.api.get(f'{self.endpoint}{record.pk}/').status_code, 404)

    def test_centre_endpoint_remains_a_separate_centre_required_workflow(self):
        centre = Centre.objects.create(name='Sample Centre', slug='sample-centre', country='Ghana')
        response = self.api.post('/api/join-centre/', {'name':'Centre Joiner','email':'centre@example.com','phone':'','centre':centre.pk}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(JoinCentreRequest.objects.get().centre, centre)
        self.assertFalse(FoundationRegistration.objects.exists())
        response = self.api.post('/api/join-centre/', {'name':'Missing Centre','email':'missing@example.com'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_inbox_filters_counts_and_review_are_role_protected(self):
        self.register()
        record = FoundationRegistration.objects.get()
        url = reverse('website:foundation_registration_list')
        action = reverse('website:foundation_registration_review', args=[record.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        media = self.user('media_operations'); self.client.force_login(media)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(action).status_code, 403)
        secretary = self.user('secretary'); self.client.force_login(secretary)
        response = self.client.get(url, {'country':'Ghana','q':'Accra','status':'new'})
        self.assertContains(response, 'Sample Joiner')
        self.assertContains(self.client.get('/dashboard/'), 'New introductions from the Join page')
        self.assertEqual(self.client.get(action).status_code, 405)
        self.assertEqual(self.client.post(action).status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.reviewed_by, secretary)
        stamp = record.reviewed_at
        self.client.post(action); record.refresh_from_db()
        self.assertEqual(record.reviewed_at, stamp)
        self.assertEqual(list(self.client.get(url, {'status':'new'}).context['registrations']), [])
        self.assertContains(self.client.get(url, {'status':'reviewed'}), 'Sample Joiner')
        self.assertEqual(self.client.get('/dashboard/').context['inbox_tasks'][0]['count'], 0)

    def test_review_requires_csrf(self):
        self.register(); record = FoundationRegistration.objects.get()
        browser = Client(enforce_csrf_checks=True); browser.force_login(self.user('admin'))
        self.assertEqual(browser.post(reverse('website:foundation_registration_review', args=[record.pk])).status_code, 403)
        record.refresh_from_db(); self.assertIsNone(record.reviewed_at)

    @override_settings(FOUNDATION_REGISTRATION_RATE='2/minute')
    def test_registration_throttles_repeated_requests(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register().status_code, 201)
        response = self.register()
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response.headers)

    @override_settings(CORS_ALLOWED_ORIGINS=['https://www.jancosmicfoundation.org'])
    def test_public_website_cors_preflight_and_post(self):
        headers = {'HTTP_ORIGIN':'https://www.jancosmicfoundation.org'}
        response = self.api.options(self.endpoint, HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST', HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type', **headers)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], headers['HTTP_ORIGIN'])
        response = self.api.post(self.endpoint, self.payload, format='json', **headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], headers['HTTP_ORIGIN'])
