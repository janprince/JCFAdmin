from django.urls import path

from . import views

app_name = 'studies'

urlpatterns = [
    path('', views.StudiesListView.as_view(), name='studies_list'),
    path('enrolments/add/', views.EnrolmentCreateView.as_view(), name='enrolment_create'),
    path('enrolments/<int:pk>/edit/', views.EnrolmentUpdateView.as_view(), name='enrolment_update'),
    path('assignments/add/', views.AssignmentCreateView.as_view(), name='assignment_create'),
    path('assignments/<int:pk>/edit/', views.AssignmentUpdateView.as_view(), name='assignment_update'),
    path('milestones/add/', views.MilestoneCreateView.as_view(), name='milestone_create'),
    path('milestones/<int:pk>/edit/', views.MilestoneUpdateView.as_view(), name='milestone_update'),
    path('mentorships/add/', views.MentorshipCreateView.as_view(), name='mentorship_create'),
    path('mentorships/<int:pk>/edit/', views.MentorshipUpdateView.as_view(), name='mentorship_update'),
]
