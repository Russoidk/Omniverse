from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from projects.models import Project
from characters.models import Character
from projects.models import Place
from timeline.models import Event


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = AuthenticationForm(request, data=request.POST or None)
    form.error_messages['invalid_login'] = 'El correo electrónico o la contraseña no son correctos. Inténtalo de nuevo.'
    form.error_messages['inactive'] = 'Esta cuenta está desactivada.'
    form.fields['username'].label = 'Correo electrónico'
    form.fields['username'].widget.attrs.update({
        'placeholder': 'tu@email.com',
        'autofocus': True,
        'class': 'form-control',
    })
    form.fields['password'].label = 'Contraseña'
    form.fields['password'].widget.attrs.update({'placeholder': 'Tu contraseña', 'class': 'form-control'})
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('home')
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def home(request):
    projects = Project.objects.filter(user=request.user).order_by('name')
    active_project_id = request.session.get('active_project_id')
    active_project = projects.filter(id=active_project_id).first() if active_project_id else None
    if active_project:
        return render(request, 'home.html', {
            'project': active_project,
            'character_count': Character.objects.filter(project=active_project).count(),
            'event_count': Event.objects.filter(project=active_project, span_marker='').count(),
            'place_count': Place.objects.filter(project=active_project).count(),
            'recent_events': Event.objects.filter(project=active_project, span_marker='').order_by('-updated_at')[:5],
        })
    request.session.pop('active_project_id', None)
    return render(request, 'project_selector.html', {'projects': projects})


@login_required
def select_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    request.session['active_project_id'] = project.id
    return redirect('home')


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')
