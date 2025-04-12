from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Add actual view paths later
    path('', views.index, name='index'),
] 