from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import PlaceForm, ProjectForm, ProjectSettingsForm
from .models import Place, Project
from .utils import get_active_project, ensure_concept_node


@login_required
def create_project(request, inside_project=False):
    project_count = Project.objects.filter(user=request.user).count()
    if not request.user.is_subscribed and project_count >= 1:
        template = 'projects/project_limit_inside.html' if inside_project else 'projects/project_limit.html'
        return render(request, template)

    form = ProjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        project = form.save(commit=False)
        project.user = request.user
        project.save()
        request.session['active_project_id'] = project.id
        messages.success(request, f'El proyecto «{project.name}» fue creado.')
        return redirect('home')

    template = 'projects/create_project_inside.html' if inside_project else 'projects/create_project.html'
    return render(request, template, {'form': form})


@login_required
def create_project_from_settings(request):
    return create_project(request, inside_project=True)


@login_required
def change_project(request):
    projects = Project.objects.filter(user=request.user).order_by('name')
    return render(request, 'projects/change_project.html', {'projects': projects})


def _active_project_or_redirect(request):
    project = get_active_project(request)
    if project is None:
        messages.info(request, 'Selecciona un proyecto para administrar sus lugares.')
    return project


@login_required
def place_list(request):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    places = Place.objects.filter(project=project).order_by('name')
    return render(request, 'projects/places.html', {'project': project, 'places': places})


@login_required
def place_create(request):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    form = PlaceForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        place = form.save(commit=False)
        place.project = project
        place.save()
        ensure_concept_node(project, place, 'PLACE')
        messages.success(request, f'El lugar «{place.name}» fue creado.')
        return redirect('places')
    return render(request, 'projects/place_form.html', {'project': project, 'form': form, 'mode': 'create'})


@login_required
def place_edit(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    place = get_object_or_404(Place, pk=pk, project=project)
    form = PlaceForm(request.POST or None, request.FILES or None, instance=place)
    if request.method == 'POST' and form.is_valid():
        place = form.save(commit=False)
        place.project = project
        place.save()
        ensure_concept_node(project, place, 'PLACE')
        messages.success(request, 'El lugar fue actualizado.')
        return redirect('places')
    return render(request, 'projects/place_form.html', {'project': project, 'form': form, 'mode': 'edit', 'place': place})


@login_required
def place_delete(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    place = get_object_or_404(Place, pk=pk, project=project)
    if request.method == 'POST':
        from django.contrib.contenttypes.models import ContentType
        from concept_map.models import ConceptNode
        ct = ContentType.objects.get_for_model(place, for_concrete_model=False)
        ConceptNode.objects.filter(project=project, content_type=ct, object_id=place.pk).delete()
        place.delete()
        messages.success(request, 'El lugar fue eliminado.')
        return redirect('places')
    return render(request, 'projects/place_confirm_delete.html', {'project': project, 'place': place})


@login_required
@require_POST
def place_quick_create(request):
    """Create a place from the character editor without navigating away."""
    project = get_active_project(request)
    if project is None:
        return JsonResponse({'ok': False, 'error': 'No hay un proyecto activo.'}, status=400)
    name = (request.POST.get('name') or '').strip()
    place_type = (request.POST.get('type') or 'Lugar').strip() or 'Lugar'
    description = (request.POST.get('description') or '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Escribe el nombre del lugar.'}, status=400)
    if len(name) > 200 or len(place_type) > 100:
        return JsonResponse({'ok': False, 'error': 'El nombre o tipo es demasiado largo.'}, status=400)
    place = Place.objects.create(project=project, name=name, type=place_type, description=description)
    ensure_concept_node(project, place, 'PLACE')
    return JsonResponse({'ok': True, 'id': place.pk, 'name': place.name, 'type': place.type})


@login_required
def project_settings(request):
    project = get_active_project(request)
    if project is None:
        messages.info(request, 'Selecciona un proyecto para configurar sus opciones.')
        return redirect('home')
    form = ProjectSettingsForm(request.POST or None, instance=project)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Los ajustes del proyecto fueron guardados.')
        return redirect('project_settings')
    return render(request, 'projects/project_settings.html', {
        'project': project, 'form': form,
    })


@login_required
def change_password(request):
    project = get_active_project(request)
    form = PasswordChangeForm(user=request.user, data=request.POST or None)
    for field_name, label in [('old_password', 'Contraseña actual'), ('new_password1', 'Nueva contraseña'), ('new_password2', 'Repetir nueva contraseña')]:
        if field_name in form.fields:
            form.fields[field_name].label = label
            form.fields[field_name].widget.attrs.update({'class': 'form-control'})
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'La contraseña se cambió correctamente.')
        return redirect('project_settings' if project else 'home')
    return render(request, 'projects/change_password.html', {
        'project': project, 'form': form,
    })
