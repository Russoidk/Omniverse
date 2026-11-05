from django.urls import path
from . import views

urlpatterns = [
    path('crear/', views.create_project, name='create_project'),
    path('crear-desde-ajustes/', views.create_project_from_settings, name='create_project_from_settings'),
    path('cambiar/', views.change_project, name='change_project'),
    path('ajustes/', views.project_settings, name='project_settings'),
    path('ajustes/cuenta/contraseña/', views.change_password, name='change_password'),
    path('lugares/', views.place_list, name='places'),
    path('lugares/nuevo/', views.place_create, name='place_create'),
    path('lugares/crear-rapido/', views.place_quick_create, name='place_quick_create'),
    path('lugares/<int:pk>/editar/', views.place_edit, name='place_edit'),
    path('lugares/<int:pk>/eliminar/', views.place_delete, name='place_delete'),
]
