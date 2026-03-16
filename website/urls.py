from django.urls import path
from . import views

app_name = 'website'

urlpatterns = [
    # Gallery
    path('gallery/', views.GalleryListView.as_view(), name='gallery_list'),
    path('gallery/add/', views.GalleryCreateView.as_view(), name='gallery_create'),
    path('gallery/<int:pk>/edit/', views.GalleryUpdateView.as_view(), name='gallery_update'),
    path('gallery/<int:pk>/delete/', views.GalleryDeleteView.as_view(), name='gallery_delete'),

    # Volunteer Opportunities
    path('volunteers/', views.VolunteerOpportunityListView.as_view(), name='volunteer_list'),
    path('volunteers/add/', views.VolunteerOpportunityCreateView.as_view(), name='volunteer_create'),
    path('volunteers/<int:pk>/edit/', views.VolunteerOpportunityUpdateView.as_view(), name='volunteer_update'),

    # Testimonials
    path('testimonials/', views.TestimonialListView.as_view(), name='testimonial_list'),
    path('testimonials/add/', views.TestimonialCreateView.as_view(), name='testimonial_create'),
    path('testimonials/<int:pk>/edit/', views.TestimonialUpdateView.as_view(), name='testimonial_update'),

    # Team Members
    path('team/', views.TeamMemberListView.as_view(), name='team_list'),
    path('team/add/', views.TeamMemberCreateView.as_view(), name='team_create'),
    path('team/<int:pk>/edit/', views.TeamMemberUpdateView.as_view(), name='team_update'),

    # Impact Stats
    path('impact/', views.ImpactStatListView.as_view(), name='impact_list'),
    path('impact/add/', views.ImpactStatCreateView.as_view(), name='impact_create'),
    path('impact/<int:pk>/edit/', views.ImpactStatUpdateView.as_view(), name='impact_update'),

    # Contact Submissions (read-only)
    path('contacts/', views.ContactSubmissionListView.as_view(), name='contact_list'),
    path('contacts/<int:pk>/read/', views.mark_contact_read, name='contact_mark_read'),

    # Volunteer Applications
    path('applications/', views.VolunteerApplicationListView.as_view(), name='volunteer_app_list'),
    path('applications/<int:pk>/status/<str:status>/', views.update_volunteer_app_status, name='volunteer_app_status'),

    # Join Centre Requests
    path('join-requests/', views.JoinCentreRequestListView.as_view(), name='join_request_list'),
    path('join-requests/<int:pk>/status/<str:status>/', views.update_join_request_status, name='join_request_status'),

    # Newsletter Subscribers
    path('newsletter/', views.NewsletterSubscriberListView.as_view(), name='newsletter_list'),
]
