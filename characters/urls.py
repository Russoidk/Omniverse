from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='characters'),
    path('nuevo/', views.create, name='character_create'),
    path('<int:pk>/', views.detail, name='character_detail'),
    path('<int:pk>/editar/', views.edit, name='character_edit'),
    path('<int:pk>/eliminar/', views.delete, name='character_delete'),
    path('<int:pk>/relaciones/nueva/', views.add_relationship, name='character_add_relationship'),
    path('<int:pk>/relaciones/<int:relationship_id>/eliminar/', views.delete_relationship, name='character_delete_relationship'),
    path('<int:pk>/exportar/<str:file_format>/', views.export_character, name='character_export'),
]
