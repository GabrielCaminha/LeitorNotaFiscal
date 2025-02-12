from django.contrib.auth.views import LoginView
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='register'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('welcome/', views.welcome, name='welcome'),
    path('logout/', views.user_logout, name='logout'),
    path('upload_xml/', views.upload_xml, name='upload_xml'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)