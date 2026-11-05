from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from projects.models import Project


class ConceptNode(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='concept_nodes'
    )
    node_type = models.CharField(max_length=100)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    position_x = models.FloatField(default=0)
    position_y = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'content_type', 'object_id'],
                name='unique_concept_object_per_project',
            )
        ]

    def __str__(self):
        return self.label

    @property
    def label(self):
        obj = self.content_object
        if obj is None:
            return 'Elemento eliminado'
        for field in ('full_name', 'title', 'name'):
            value = getattr(obj, field, None)
            if value:
                return str(value)
        return str(obj)

    def clean(self):
        super().clean()
        obj = self.content_object
        if obj is not None and hasattr(obj, 'project_id') and obj.project_id != self.project_id:
            raise ValidationError('El elemento debe pertenecer al mismo proyecto que el nodo.')


class ConceptConnection(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='concept_connections'
    )
    source_node = models.ForeignKey(
        ConceptNode, on_delete=models.CASCADE, related_name='connections_out'
    )
    target_node = models.ForeignKey(
        ConceptNode, on_delete=models.CASCADE, related_name='connections_in'
    )
    relationship_type = models.CharField(max_length=200, blank=True)
    label = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.source_node} → {self.label or self.relationship_type} → {self.target_node}'

    def clean(self):
        super().clean()
        if self.source_node_id and self.target_node_id:
            if self.source_node_id == self.target_node_id:
                raise ValidationError('Un nodo no puede conectarse consigo mismo.')
            if self.source_node.project_id != self.project_id or self.target_node.project_id != self.project_id:
                raise ValidationError('Los nodos deben pertenecer al proyecto activo.')
