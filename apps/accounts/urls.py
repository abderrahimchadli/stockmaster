from django.urls import path
from .views import (
    LoginView, 
    AuthCallbackView, 
    LogoutView,
    landing_page,
    index
)

app_name = 'accounts'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('callback/', AuthCallbackView.as_view(), name='callback'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', landing_page, name='landing_page'),
    path('dashboard/', index, name='index'),
] 