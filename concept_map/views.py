import json
import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from characters.models import Character, CharacterRelationship
from projects.models import Place
from projects.utils import get_active_project, ensure_concept_node
from timeline.models import Event, EventCharacter, EventPlace, EventRelationship
from .forms import ConceptConnectionForm
from .models import ConceptConnection, ConceptNode


def _active_project_or_redirect(request):
    project = get_active_project(request)
    if project is None:
        messages.info(request, 'Selecciona un proyecto para continuar.')
    return project


@login_required
def index(request):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')

    # Nodes always point to the same real entities used by the other modules.
    for obj, node_type in [
        *((obj, 'CHARACTER') for obj in Character.objects.filter(project=project)),
        *((obj, 'EVENT') for obj in Event.objects.filter(project=project, span_marker='')),
        *((obj, 'PLACE') for obj in Place.objects.filter(project=project)),
    ]:
        ensure_concept_node(project, obj, node_type)

    nodes = list(ConceptNode.objects.filter(project=project).select_related('content_type').order_by('id'))
    stale = [node.pk for node in nodes if node.content_object is None]
    if stale:
        ConceptNode.objects.filter(pk__in=stale).delete()
        nodes = [node for node in nodes if node.pk not in stale]

    total = max(len(nodes), 1)
    # A golden-angle spiral fills the available area instead of putting every
    # late-added node on the same outer ring. Coordinates stay normalized; the
    # browser enlarges the physical canvas as the network grows.
    raw_max_radius = 38 * math.sqrt(total)
    target_radius = min(380, max(55, 60 * math.sqrt(total)))
    fit_scale = target_radius / raw_max_radius if raw_max_radius else 1
    for idx, node in enumerate(nodes):
        if node.position_x == 0 and node.position_y == 0:
            if total == 1:
                node.position_x, node.position_y = 500, 325
            else:
                angle = idx * 2.399963229728653 - math.pi / 2
                radius = 38 * math.sqrt(idx + 1) * fit_scale
                node.position_x = max(90, min(910, 500 + radius * math.cos(angle)))
                node.position_y = max(85, min(565, 325 + radius * 0.62 * math.sin(angle)))
            node.save(update_fields=['position_x', 'position_y', 'updated_at'])

    content_type_ids = {
        'character': ContentType.objects.get_for_model(Character, for_concrete_model=False).pk,
        'event': ContentType.objects.get_for_model(Event, for_concrete_model=False).pk,
        'place': ContentType.objects.get_for_model(Place, for_concrete_model=False).pk,
    }
    node_ids = {
        (node.content_type_id, node.object_id): node.pk
        for node in nodes
    }
    graph_edges = []

    # Character-to-character edges are sourced from the character sheet's relationship table.
    for relation in CharacterRelationship.objects.filter(project=project).select_related('character_1', 'character_2'):
        source = node_ids.get((content_type_ids['character'], relation.character_1_id))
        target = node_ids.get((content_type_ids['character'], relation.character_2_id))
        if source and target:
            graph_edges.append({
                'id': f'character-{relation.pk}', 'source': source, 'target': target,
                'label': relation.relationship_type or 'relación', 'kind': 'automatic',
            })

    # A character's main residence is a real relationship too, not only a text label on the sheet.
    for character in Character.objects.filter(project=project, main_residence__isnull=False).select_related('main_residence'):
        source = node_ids.get((content_type_ids['character'], character.pk))
        target = node_ids.get((content_type_ids['place'], character.main_residence_id))
        if source and target:
            graph_edges.append({
                'id': f'character-residence-{character.pk}', 'source': source, 'target': target,
                'label': 'vive en', 'kind': 'automatic',
            })

    # A character's participation in an event appears automatically in the graph.
    for relation in EventCharacter.objects.filter(event__project=project).select_related('event', 'character'):
        source = node_ids.get((content_type_ids['character'], relation.character_id))
        target = node_ids.get((content_type_ids['event'], relation.event_id))
        if source and target:
            graph_edges.append({
                'id': f'event-character-{relation.pk}', 'source': source, 'target': target,
                'label': relation.role or 'participa en', 'kind': 'automatic',
            })

    # Locations linked to events also appear in the map automatically.
    for relation in EventPlace.objects.filter(event__project=project).select_related('event', 'place'):
        source = node_ids.get((content_type_ids['event'], relation.event_id))
        target = node_ids.get((content_type_ids['place'], relation.place_id))
        if source and target:
            graph_edges.append({
                'id': f'event-place-{relation.pk}', 'source': source, 'target': target,
                'label': relation.role or 'ocurre en', 'kind': 'automatic',
            })

    # Causal and temporal links between events are reflected in the graph.
    for relation in EventRelationship.objects.filter(project=project).select_related('event_1', 'event_2'):
        source = node_ids.get((content_type_ids['event'], relation.event_1_id))
        target = node_ids.get((content_type_ids['event'], relation.event_2_id))
        if source and target:
            graph_edges.append({
                'id': f'event-relation-{relation.pk}', 'source': source, 'target': target,
                'label': relation.relationship_type or 'relacionado con', 'kind': 'automatic',
            })

    explicit_connections = list(ConceptConnection.objects.filter(project=project).select_related(
        'source_node', 'target_node'
    ).order_by('created_at'))
    for connection in explicit_connections:
        graph_edges.append({
            'id': f'concept-{connection.pk}', 'source': connection.source_node_id,
            'target': connection.target_node_id,
            'label': connection.label or connection.relationship_type or 'relacionado',
            'kind': 'custom',
        })

    graph_data = {
        'nodes': [
            {'id': node.pk, 'label': node.label, 'type': node.node_type,
             'x': node.position_x, 'y': node.position_y}
            for node in nodes
        ],
        'connections': graph_edges,
    }
    form = ConceptConnectionForm(request.POST or None, project=project)
    if request.method == 'POST' and form.is_valid():
        connection = form.save(commit=False)
        connection.project = project
        connection.full_clean()
        connection.save()
        messages.success(request, 'La conexión personalizada fue creada.')
        return redirect('concept_map')

    return render(request, 'concept_map/index.html', {
        'project': project,
        'nodes': nodes,
        'connections': explicit_connections,
        'graph_edge_count': len(graph_edges),
        'graph_data': graph_data,
        'form': form,
    })


@login_required
@require_POST
def delete_connection(request, connection_id):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    connection = get_object_or_404(ConceptConnection, pk=connection_id, project=project)
    connection.delete()
    messages.success(request, 'La conexión personalizada fue eliminada.')
    return redirect('concept_map')


@login_required
@require_POST
def update_node_position(request, node_id):
    project = _active_project_or_redirect(request)
    if project is None:
        return JsonResponse({'ok': False, 'error': 'No hay proyecto activo.'}, status=403)
    node = get_object_or_404(ConceptNode, pk=node_id, project=project)
    try:
        payload = json.loads(request.body.decode('utf-8'))
        x = float(payload['x'])
        y = float(payload['y'])
        # The conceptual map is a panning/zooming canvas; nodes may live outside the initial viewport.
        if not (-100000 <= x <= 100000 and -100000 <= y <= 100000):
            raise ValueError
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Posición inválida.'}, status=400)
    node.position_x = x
    node.position_y = y
    node.save(update_fields=['position_x', 'position_y', 'updated_at'])
    return JsonResponse({'ok': True})
