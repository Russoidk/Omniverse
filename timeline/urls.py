from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='timeline'),
    path('nuevo/', views.create, name='event_create'),
    path('exportar/<str:file_format>/', views.export_timeline, name='timeline_export'),
    path('orden/<int:event_id>/<str:direction>/', views.move_event_order, name='event_move_order'),
    path('lapsos/nuevo/', views.span_create, name='span_create'),
    path('lapsos/<int:pk>/editar/', views.span_edit, name='span_edit'),
    path('lapsos/<int:pk>/eliminar/', views.span_delete, name='span_delete'),
    path('<int:pk>/', views.detail, name='event_detail'),
    path('<int:pk>/editar/', views.edit, name='event_edit'),
    path('<int:pk>/eliminar/', views.delete, name='event_delete'),
    path('<int:pk>/relaciones/nueva/', views.add_relationship, name='event_add_relationship'),
    path('<int:pk>/relaciones/<int:relationship_id>/eliminar/', views.delete_relationship, name='event_delete_relationship'),
]
