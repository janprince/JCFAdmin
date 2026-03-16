"""
Public API endpoints for the JCF website.
All endpoints are read-only (GET) unless noted otherwise.
"""
from django.urls import path
from rest_framework import generics

from events.models import Event
from events.serializers import EventSerializer

from blog.models import Post
from blog.serializers import PostSerializer, PostListSerializer

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
    queryset = Centre.objects.filter(is_active=True)


class CentreDetailAPIView(generics.RetrieveAPIView):
    serializer_class = CentreSerializer
    queryset = Centre.objects.filter(is_active=True)
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
]
