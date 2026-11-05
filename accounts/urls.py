from django.urls import path
from . import views

urlpatterns = [
    path('programa/', views.home, name='home'),
    path('iniciar-sesion/', views.login_view, name='login'),
    path('cerrar-sesion/', views.logout_view, name='logout'),
    path('seleccionar-proyecto/<int:project_id>/', views.select_project, name='select_project'),
]
