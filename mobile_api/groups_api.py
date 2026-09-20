"""Mobile groups API: browse admin-created groups and request to join.

Joining is approval-gated: a request creates a PENDING membership that staff
approve or decline in the dashboard; only APPROVED rows are membership.
"""
from django.utils.translation import gettext as _
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.models import Group, GroupMembership
from .authentication import IsStudentOrMember, MobileTokenAuthentication


class GroupSerializer(serializers.ModelSerializer):
    centre = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    my_status = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            'id', 'name', 'description', 'centre', 'capacity',
            'member_count', 'is_full', 'my_status',
        ]

    def get_centre(self, obj):
        return obj.centre.name if obj.centre_id else None

    def get_my_status(self, obj):
        by_group = self.context.get('my_memberships') or {}
        membership = by_group.get(obj.id)
        return membership.status if membership else None


class GroupListView(generics.ListAPIView):
    """Active groups, each annotated with the caller's membership status."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsStudentOrMember]
    serializer_class = GroupSerializer

    def get_queryset(self):
        return Group.objects.filter(is_active=True).select_related('centre')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        mine = GroupMembership.objects.filter(contact=self.request.member)
        context['my_memberships'] = {m.group_id: m for m in mine}
        return context


class MyGroupsView(generics.ListAPIView):
    """Groups the caller has been approved into."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsStudentOrMember]
    serializer_class = GroupSerializer

    def get_queryset(self):
        return Group.objects.filter(
            is_active=True,
            memberships__contact=self.request.member,
            memberships__status=GroupMembership.Status.APPROVED,
        ).select_related('centre')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        mine = GroupMembership.objects.filter(contact=self.request.member)
        context['my_memberships'] = {m.group_id: m for m in mine}
        return context


class JoinRequestView(APIView):
    """POST /groups/<pk>/join/ — ask to join; staff approve in the dashboard."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsStudentOrMember]

    def post(self, request, pk):
        try:
            group = Group.objects.get(pk=pk, is_active=True)
        except Group.DoesNotExist:
            return Response({'detail': _('Group not found.')}, status=status.HTTP_404_NOT_FOUND)

        if group.is_full:
            return Response(
                {'detail': _('This group is full.')}, status=status.HTTP_400_BAD_REQUEST
            )

        message = str(request.data.get('message', ''))[:255]
        membership, created = GroupMembership.objects.get_or_create(
            group=group, contact=request.member, defaults={'message': message},
        )
        if not created:
            if membership.status == GroupMembership.Status.APPROVED:
                return Response(
                    {'detail': _('You are already a member of this group.')},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if membership.status == GroupMembership.Status.PENDING:
                return Response(
                    {'detail': _('Your request is already awaiting approval.')},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Declined earlier — allow a fresh request.
            membership.status = GroupMembership.Status.PENDING
            membership.message = message
            membership.decided_at = None
            membership.decided_by = None
            membership.save(update_fields=['status', 'message', 'decided_at', 'decided_by'])

        return Response(
            {'status': membership.status, 'group_id': group.id},
            status=status.HTTP_201_CREATED,
        )
