from django.urls import path
from . import views

app_name = 'rules_api'

urlpatterns = [
    # API endpoints will be added here
    path('status/', views.api_status, name='status'),
] 