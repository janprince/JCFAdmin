"""Groups: join-request flow (API) and staff approval (services)."""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from engagement.models import Notification
from members.models import Contact
from mobile_api.models import MobileToken

from .models import Group, GroupMembership
from . import services


class GroupsApiTests(APITestCase):
    def setUp(self):
        self.member = Contact.objects.create(
            full_name='Ama Member', phone='+233200000001',
            email='ama@example.com', is_active=True, is_member=True,
        )
        self.group = Group.objects.create(name='Accra Prayer Circle')
        self.staff = get_user_model().objects.create_user(
            username='staff', email='staff@jcf.org', password='x',
        )

    def _auth(self, contact=None):
        token = MobileToken.issue(contact or self.member)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    # --- listing ---

    def test_list_requires_member_auth(self):
        res = self.client.get('/api/mobile/v1/groups/')
        self.assertEqual(res.status_code, 401)

    def test_list_shows_active_groups_with_my_status(self):
        Group.objects.create(name='Hidden', is_active=False)
        self._auth()
        res = self.client.get('/api/mobile/v1/groups/')
        self.assertEqual(res.status_code, 200)
        names = [g['name'] for g in res.data['results']]
        self.assertEqual(names, ['Accra Prayer Circle'])
        self.assertIsNone(res.data['results'][0]['my_status'])

    # --- join flow ---

    def test_join_creates_pending_request(self):
        self._auth()
        res = self.client.post(f'/api/mobile/v1/groups/{self.group.pk}/join/',
                               {'message': 'Please add me'})
        self.assertEqual(res.status_code, 201)
        m = GroupMembership.objects.get()
        self.assertEqual(m.status, GroupMembership.Status.PENDING)
        self.assertEqual(m.message, 'Please add me')
        # Not a member until approved.
        res = self.client.get('/api/mobile/v1/groups/mine/')
        self.assertEqual(res.data['results'], [])

    def test_duplicate_request_rejected(self):
        self._auth()
        self.client.post(f'/api/mobile/v1/groups/{self.group.pk}/join/')
        res = self.client.post(f'/api/mobile/v1/groups/{self.group.pk}/join/')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(GroupMembership.objects.count(), 1)

    def test_declined_member_can_request_again(self):
        self._auth()
        self.client.post(f'/api/mobile/v1/groups/{self.group.pk}/join/')
        services.decline_request(GroupMembership.objects.get(), self.staff)
        res = self.client.post(f'/api/mobile/v1/groups/{self.group.pk}/join/')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(GroupMembership.objects.get().status,
                         GroupMembership.Status.PENDING)

    def test_full_group_rejects_requests(self):
        self.group.capacity = 1
        self.group.save()
        other = Contact.objects.create(
            full_name='Kofi', phone='+233200000002', is_active=True, is_member=True,
        )
        GroupMembership.objects.create(
            group=self.group, contact=other,
            status=GroupMembership.Status.APPROVED,
        )
        self._auth()
        res = self.client.post(f'/api/mobile/v1/groups/{self.group.pk}/join/')
        self.assertEqual(res.status_code, 400)

    # --- approval ---

    def test_approve_makes_member_and_notifies(self):
        self._auth()
        self.client.post(f'/api/mobile/v1/groups/{self.group.pk}/join/')
        m = GroupMembership.objects.get()
        services.approve_request(m, self.staff)
        m.refresh_from_db()
        self.assertEqual(m.status, GroupMembership.Status.APPROVED)
        self.assertEqual(m.decided_by, self.staff)
        self.assertEqual(Notification.objects.filter(contact=self.member).count(), 1)

        res = self.client.get('/api/mobile/v1/groups/mine/')
        self.assertEqual(res.data['results'][0]['name'], 'Accra Prayer Circle')
        res = self.client.get('/api/mobile/v1/groups/')
        self.assertEqual(res.data['results'][0]['my_status'], 'approved')

    def test_approve_refuses_when_full(self):
        self.group.capacity = 0
        self.group.save()
        m = GroupMembership.objects.create(group=self.group, contact=self.member)
        with self.assertRaises(Exception):
            services.approve_request(m, self.staff)
        m.refresh_from_db()
        self.assertEqual(m.status, GroupMembership.Status.PENDING)
