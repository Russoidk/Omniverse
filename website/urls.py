from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('crear-cuenta/', views.register, name='register'),
    path('web/iniciar-sesion/', views.web_login, name='web_login'),
    path('mi-cuenta/', views.account, name='web_account'),
    path('suscripcion/', views.subscription, name='web_subscription'),
    path('suscripcion/activar/', views.activate_subscription, name='activate_subscription'),
    path('suscripcion/cancelar/', views.cancel_subscription, name='cancel_subscription'),
    path('mi-cuenta/cambiar-contrasena/', views.change_password, name='web_change_password'),
    path('web/cerrar-sesion/', views.web_logout, name='web_logout'),
]
