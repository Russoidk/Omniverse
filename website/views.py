from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import RegistrationForm, WebsiteAuthenticationForm


def landing(request):
    return render(request, 'website/landing.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('web_account')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, '¡Tu cuenta está lista! Ya puedes comenzar a organizar tus ideas.')
        return redirect('web_account')
    return render(request, 'website/register.html', {'form': form})


def web_login(request):
    if request.user.is_authenticated:
        return redirect('web_account')
    form = WebsiteAuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        messages.success(request, 'Sesión iniciada correctamente.')
        return redirect('web_account')
    return render(request, 'website/login.html', {'form': form})


@login_required(login_url='web_login')
def account(request):
    return render(request, 'website/account.html', {'user_account': request.user})


@login_required(login_url='web_login')
def subscription(request):
    return render(request, 'website/subscription.html', {'user_account': request.user})


@login_required(login_url='web_login')
@require_POST
def activate_subscription(request):
    request.user.is_subscribed = True
    request.user.save(update_fields=['is_subscribed', 'updated_at'])
    messages.success(request, 'Suscripción simulada activada. Tu cuenta ya tiene acceso a las funciones Plus.')
    return redirect('web_account')


@login_required(login_url='web_login')
@require_POST
def cancel_subscription(request):
    request.user.is_subscribed = False
    request.user.save(update_fields=['is_subscribed', 'updated_at'])
    messages.info(request, 'La suscripción simulada fue desactivada. Tu cuenta volvió al plan gratuito.')
    return redirect('web_account')


@login_required(login_url='web_login')
def change_password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    for field in form.fields.values():
        field.widget.attrs['class'] = 'site-input'
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Tu contraseña se actualizó correctamente.')
        return redirect('web_account')
    return render(request, 'website/change_password.html', {'form': form})


@require_POST
def web_logout(request):
    logout(request)
    messages.info(request, 'Has cerrado la sesión.')
    return redirect('landing')
