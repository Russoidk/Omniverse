from django.contrib.contenttypes.models import ContentType

from .models import Project


def get_active_project(request):
    """Return the active project only if it belongs to the authenticated user."""
    if not request.user.is_authenticated:
        return None
    project_id = request.session.get('active_project_id')
    if not project_id:
        return None
    return Project.objects.filter(pk=project_id, user=request.user).first()


def ensure_concept_node(project, obj, node_type):
    """Create or retrieve the graph node representing a real project entity."""
    from concept_map.models import ConceptNode

    content_type = ContentType.objects.get_for_model(obj, for_concrete_model=False)
    node, _ = ConceptNode.objects.get_or_create(
        project=project,
        content_type=content_type,
        object_id=obj.pk,
        defaults={'node_type': node_type},
    )
    if node.node_type != node_type:
        node.node_type = node_type
        node.save(update_fields=['node_type', 'updated_at'])
    return node
