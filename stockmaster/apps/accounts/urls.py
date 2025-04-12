from django.urls import path
from .views import (
    LogoutView,
    install_app,
    auth_callback,
    landing_page,
    index
)

app_name = 'accounts'

urlpatterns = [
    path('login/', install_app, name='login'),
    path('auth/callback/', auth_callback, name='callback'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', landing_page, name='landing_page'),
    path('dashboard/', index, name='index'),
] 