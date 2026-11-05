from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='concept_map'),
    path('conexiones/<int:connection_id>/eliminar/', views.delete_connection, name='concept_connection_delete'),
    path('nodos/<int:node_id>/posicion/', views.update_node_position, name='concept_node_position'),
]
