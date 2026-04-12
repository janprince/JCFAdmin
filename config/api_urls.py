"""
Public API endpoints for the JCF website.
All endpoints are read-only (GET) unless noted otherwise.
"""
import json
import logging

from django.urls import path
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import Event
from events.serializers import EventSerializer

from blog.models import Post
from blog.serializers import PostSerializer, PostListSerializer

from django.db.models import Count

from centres.models import Centre
from centres.serializers import CentreSerializer, CentreListSerializer

from causes.models import Cause
from causes.serializers import CauseSerializer, CauseListSerializer

from website.models import (
    GalleryItem, VolunteerOpportunity, Testimonial,
    TeamMember, ImpactStat,
)
from website.serializers import (
    GalleryItemSerializer, VolunteerOpportunitySerializer,
    TestimonialSerializer, TeamMemberSerializer, ImpactStatSerializer,
    ContactSubmissionSerializer, VolunteerApplicationSerializer,
    JoinCentreRequestSerializer, NewsletterSubscriberSerializer,
)


# --- Events ---

class EventListAPIView(generics.ListAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        qs = Event.objects.filter(is_published=True).select_related('category')
        filter_type = self.request.query_params.get('filter')
        if filter_type == 'upcoming':
            from django.utils import timezone
            qs = qs.filter(date__gte=timezone.now().date())
        elif filter_type == 'past':
            from django.utils import timezone
            qs = qs.filter(date__lt=timezone.now().date())
        return qs


class EventDetailAPIView(generics.RetrieveAPIView):
    serializer_class = EventSerializer
    queryset = Event.objects.filter(is_published=True).select_related('category')
    lookup_field = 'slug'


# --- Blog ---

class PostListAPIView(generics.ListAPIView):
    serializer_class = PostListSerializer

    def get_queryset(self):
        qs = Post.objects.filter(status='published').select_related('author', 'category')
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__name__iexact=category)
        return qs


class PostDetailAPIView(generics.RetrieveAPIView):
    serializer_class = PostSerializer
    queryset = Post.objects.filter(status='published').select_related('author', 'category').prefetch_related('tags')
    lookup_field = 'slug'


# --- Centres ---

class CentreListAPIView(generics.ListAPIView):
    serializer_class = CentreListSerializer
    queryset = Centre.objects.filter(is_active=True).annotate(
        member_count=Count('members'),
    )


class CentreDetailAPIView(generics.RetrieveAPIView):
    serializer_class = CentreSerializer
    queryset = Centre.objects.filter(is_active=True).annotate(
        member_count=Count('members'),
    )
    lookup_field = 'slug'


# --- Causes ---

class CauseListAPIView(generics.ListAPIView):
    serializer_class = CauseListSerializer
    queryset = Cause.objects.filter(is_active=True).select_related('category')


class CauseDetailAPIView(generics.RetrieveAPIView):
    serializer_class = CauseSerializer
    queryset = Cause.objects.filter(is_active=True).select_related('category')
    lookup_field = 'slug'


# --- Website content (read-only) ---

class GalleryListAPIView(generics.ListAPIView):
    serializer_class = GalleryItemSerializer

    def get_queryset(self):
        qs = GalleryItem.objects.filter(is_published=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__iexact=category)
        return qs


class VolunteerOpportunityListAPIView(generics.ListAPIView):
    serializer_class = VolunteerOpportunitySerializer
    queryset = VolunteerOpportunity.objects.filter(is_active=True)
    pagination_class = None


class TestimonialListAPIView(generics.ListAPIView):
    serializer_class = TestimonialSerializer
    queryset = Testimonial.objects.filter(is_published=True)
    pagination_class = None


class TeamMemberListAPIView(generics.ListAPIView):
    serializer_class = TeamMemberSerializer
    queryset = TeamMember.objects.filter(is_active=True)
    pagination_class = None


class ImpactStatListAPIView(generics.ListAPIView):
    serializer_class = ImpactStatSerializer
    queryset = ImpactStat.objects.all()
    pagination_class = None


# --- Form submissions (POST only) ---

class ContactSubmissionCreateAPIView(generics.CreateAPIView):
    serializer_class = ContactSubmissionSerializer


class VolunteerApplicationCreateAPIView(generics.CreateAPIView):
    serializer_class = VolunteerApplicationSerializer


class JoinCentreRequestCreateAPIView(generics.CreateAPIView):
    serializer_class = JoinCentreRequestSerializer


class NewsletterSubscribeAPIView(generics.CreateAPIView):
    serializer_class = NewsletterSubscriberSerializer


# --- Donations (Paystack) ---

logger = logging.getLogger(__name__)


class DonationVerifyAPIView(APIView):
    """
    POST /api/donations/verify/
    Frontend calls this after a successful Paystack payment.
    We verify the transaction with Paystack's API, then create a Donation record.
    """

    def post(self, request):
        reference = request.data.get('reference', '').strip()
        cause_id = request.data.get('cause_id')

        if not reference:
            return Response(
                {'error': 'reference is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent duplicate processing
        from causes.models import Donation
        if Donation.objects.filter(paystack_reference=reference).exists():
            return Response({'status': 'already_processed'})

        # Verify with Paystack
        from causes.paystack import verify_transaction
        tx = verify_transaction(reference)
        if tx is None:
            return Response(
                {'error': 'Payment verification failed'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Amount from Paystack is in pesewas (smallest unit) — convert to GHS
        amount_major = tx['amount'] / 100
        customer = tx.get('customer', {})

        # Resolve cause
        cause = None
        if cause_id:
            from causes.models import Cause
            cause = Cause.objects.filter(id=cause_id, is_active=True).first()

        donation = Donation.objects.create(
            cause=cause,
            donor_name=customer.get('first_name', '') or customer.get('email', ''),
            donor_email=customer.get('email', ''),
            amount=amount_major,
            currency=tx.get('currency', 'GHS'),
            method=Donation.Method.ONLINE,
            status=Donation.Status.COMPLETED,
            paystack_reference=reference,
            donated_at=tx.get('paid_at') or timezone.now(),
        )

        return Response({
            'status': 'success',
            'donation_id': donation.id,
            'amount': str(donation.amount),
            'currency': donation.currency,
        }, status=status.HTTP_201_CREATED)


class PaystackWebhookAPIView(APIView):
    """
    POST /api/webhook/paystack/
    Paystack sends webhook events here as a safety net.
    We verify the signature, then process charge.success events.
    """

    def post(self, request):
        signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE', '')
        if not signature:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        from causes.paystack import validate_webhook_signature
        if not validate_webhook_signature(request.body, signature):
            logger.warning('Paystack webhook: invalid signature')
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        event = payload.get('event')
        if event != 'charge.success':
            # Acknowledge but ignore non-charge events
            return Response({'status': 'ignored'})

        data = payload.get('data', {})
        reference = data.get('reference', '')

        if not reference:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        from causes.models import Donation, Cause

        # Idempotency: skip if already recorded
        if Donation.objects.filter(paystack_reference=reference).exists():
            return Response({'status': 'already_processed'})

        amount_major = data.get('amount', 0) / 100
        customer = data.get('customer', {})

        # Try to resolve cause from metadata
        cause = None
        metadata = data.get('metadata', {})
        custom_fields = metadata.get('custom_fields', [])
        for field in custom_fields:
            if field.get('variable_name') == 'cause_id':
                cause = Cause.objects.filter(
                    id=field['value'], is_active=True,
                ).first()
                break

        Donation.objects.create(
            cause=cause,
            donor_name=customer.get('first_name', '') or customer.get('email', ''),
            donor_email=customer.get('email', ''),
            amount=amount_major,
            currency=data.get('currency', 'GHS'),
            method=Donation.Method.ONLINE,
            status=Donation.Status.COMPLETED,
            paystack_reference=reference,
            donated_at=data.get('paid_at') or timezone.now(),
        )

        logger.info('Paystack webhook: recorded donation ref=%s', reference)
        return Response({'status': 'success'})


# --- URL patterns ---

app_name = 'api'

urlpatterns = [
    # Events
    path('events/', EventListAPIView.as_view(), name='event_list'),
    path('events/<slug:slug>/', EventDetailAPIView.as_view(), name='event_detail'),

    # Blog
    path('posts/', PostListAPIView.as_view(), name='post_list'),
    path('posts/<slug:slug>/', PostDetailAPIView.as_view(), name='post_detail'),

    # Centres
    path('centres/', CentreListAPIView.as_view(), name='centre_list'),
    path('centres/<slug:slug>/', CentreDetailAPIView.as_view(), name='centre_detail'),

    # Causes
    path('causes/', CauseListAPIView.as_view(), name='cause_list'),
    path('causes/<slug:slug>/', CauseDetailAPIView.as_view(), name='cause_detail'),

    # Website content
    path('gallery/', GalleryListAPIView.as_view(), name='gallery_list'),
    path('volunteer-opportunities/', VolunteerOpportunityListAPIView.as_view(), name='volunteer_list'),
    path('testimonials/', TestimonialListAPIView.as_view(), name='testimonial_list'),
    path('team/', TeamMemberListAPIView.as_view(), name='team_list'),
    path('impact-stats/', ImpactStatListAPIView.as_view(), name='impact_stats'),

    # Form submissions (POST only)
    path('contact/', ContactSubmissionCreateAPIView.as_view(), name='contact_submit'),
    path('volunteer-apply/', VolunteerApplicationCreateAPIView.as_view(), name='volunteer_apply'),
    path('join-centre/', JoinCentreRequestCreateAPIView.as_view(), name='join_centre'),
    path('newsletter/', NewsletterSubscribeAPIView.as_view(), name='newsletter_subscribe'),

    # Donations (Paystack)
    path('donations/verify/', DonationVerifyAPIView.as_view(), name='donation_verify'),
    path('webhook/paystack/', PaystackWebhookAPIView.as_view(), name='paystack_webhook'),
]
