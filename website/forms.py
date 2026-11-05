from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.models import User


class RegistrationForm(forms.ModelForm):
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'class': 'site-input', 'placeholder': 'tu@correo.com', 'autocomplete': 'email'}),
    )
    first_name = forms.CharField(
        label='Nombre (opcional)', required=False, max_length=150,
        widget=forms.TextInput(attrs={'class': 'site-input', 'placeholder': '¿Cómo te llamas?', 'autocomplete': 'given-name'}),
    )
    password1 = forms.CharField(
        label='Contraseña', strip=False,
        widget=forms.PasswordInput(attrs={'class': 'site-input', 'placeholder': 'Crea una contraseña segura', 'autocomplete': 'new-password'}),
        help_text='Usa al menos 8 caracteres y evita contraseñas demasiado comunes.',
    )
    password2 = forms.CharField(
        label='Confirmar contraseña', strip=False,
        widget=forms.PasswordInput(attrs={'class': 'site-input', 'placeholder': 'Repite la contraseña', 'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ('email', 'first_name')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Ya existe una cuenta con ese correo electrónico.')
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Las contraseñas no coinciden.')
        if password1:
            candidate = User(email=self.cleaned_data.get('email', ''), first_name=self.cleaned_data.get('first_name', ''))
            validate_password(password1, user=candidate)
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = None
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class WebsiteAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'El correo electrónico o la contraseña no son correctos. Inténtalo de nuevo.',
        'inactive': 'Esta cuenta está desactivada.',
    }
    username = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'class': 'site-input', 'placeholder': 'tu@correo.com', 'autocomplete': 'email', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Contraseña',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'site-input', 'placeholder': 'Tu contraseña', 'autocomplete': 'current-password'}),
    )
