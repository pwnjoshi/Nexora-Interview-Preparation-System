# interview/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_resume, name='upload_resume'),
    path('dashboard/', views.dashboard, name='interview_dashboard'),
    path('start/', views.start_interview_view, name='start_interview'),
    path('instructions/', views.interview_instructions_view, name='interview_instructions'),
    path('question/', views.interview_question_view, name='interview_question'),
    path('results/<str:session_id>/', views.results_view, name='interview_results'),
    
    # New pages
    path('reports/', views.reports_view, name='reports'),
    path('reports/pdf/', views.reports_pdf_view, name='reports_pdf'),
    path('help/', views.help_view, name='help'),
    path('settings/', views.settings_view, name='settings'),
    path('feedback/', views.feedback_view, name='feedback'),
    path('profile/', views.profile_view, name='profile'),
]