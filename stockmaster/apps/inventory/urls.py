from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Add actual view paths later
    path('', views.index, name='index'),
] 