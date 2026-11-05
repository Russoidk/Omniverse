from django import forms

from projects.models import Place
from .models import Character, CharacterRelationship


class CharacterForm(forms.ModelForm):
    class Meta:
        model = Character
        fields = [
            'image', 'full_name', 'role',
            'quote_1', 'quote_1_author', 'quote_1_context', 'quote_2', 'quote_2_author', 'quote_2_context',
            'birth_date', 'age_at_story_start', 'species', 'current_status',
            'faction', 'main_residence',
            'dominant_traits', 'destructive_traits', 'secret_dream',
            'likes', 'dislikes', 'happier_if',
            'childhood', 'adolescence', 'adulthood',
        ]
        labels = {
            'image': 'Retrato',
            'full_name': 'Nombre completo',
            'role': 'Rol o título',
            'quote_1': 'Cita que defina su visión del mundo',
            'quote_1_author': 'Autor o fuente',
            'quote_1_context': 'Contexto de la cita',
            'quote_2': 'Cita que lo describa o contradiga',
            'quote_2_author': 'Autor o fuente',
            'quote_2_context': 'Contexto de la cita',
            'birth_date': 'Fecha de nacimiento',
            'age_at_story_start': 'Edad al inicio de la historia',
            'species': 'Especie o raza',
            'current_status': 'Estado actual',
            'faction': 'Facción, grupo o afiliación',
            'main_residence': 'Residencia principal',
            'dominant_traits': 'Rasgos dominantes',
            'destructive_traits': 'Rasgos destructivos',
            'secret_dream': 'Sueño secreto',
            'likes': 'Gustos',
            'dislikes': 'Disgustos',
            'happier_if': 'Sería más feliz si…',
            'childhood': 'Infancia',
            'adolescence': 'Adolescencia',
            'adulthood': 'Adultez',
        }
        widgets = {
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'placeholder': 'Nombre del personaje'}),
            'role': forms.TextInput(attrs={'placeholder': 'Protagonista, antagonista, título…'}),
            'quote_1': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Una frase que revele cómo interpreta el mundo…', 'data-autogrow': 'true'}),
            'quote_1_context': forms.TextInput(attrs={'placeholder': 'Escena, capítulo o situación…'}),
            'quote_2': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Una frase que lo describa, lo contradiga o revele otra faceta…', 'data-autogrow': 'true'}),
            'quote_2_context': forms.TextInput(attrs={'placeholder': 'Escena, capítulo o situación…'}),
            'birth_date': forms.TextInput(attrs={'placeholder': 'Ej. 29/02/774 o Tres días después…'}),
            'age_at_story_start': forms.NumberInput(attrs={'min': 0}),
            'species': forms.TextInput(attrs={'placeholder': 'Especie, raza, tipo de ser…'}),
            'current_status': forms.TextInput(attrs={'placeholder': 'Vivo, desaparecido, fallecido…'}),
            'faction': forms.TextInput(attrs={'placeholder': 'Facción, reino, organización…'}),
            'dominant_traits': forms.Textarea(attrs={'rows': 3, 'data-autogrow': 'true'}),
            'destructive_traits': forms.Textarea(attrs={'rows': 3, 'data-autogrow': 'true'}),
            'secret_dream': forms.Textarea(attrs={'rows': 3, 'data-autogrow': 'true'}),
            'likes': forms.Textarea(attrs={'rows': 3, 'data-autogrow': 'true'}),
            'dislikes': forms.Textarea(attrs={'rows': 3, 'data-autogrow': 'true'}),
            'happier_if': forms.Textarea(attrs={'rows': 3, 'data-autogrow': 'true'}),
            'childhood': forms.Textarea(attrs={'rows': 4, 'data-autogrow': 'true'}),
            'adolescence': forms.Textarea(attrs={'rows': 4, 'data-autogrow': 'true'}),
            'adulthood': forms.Textarea(attrs={'rows': 4, 'data-autogrow': 'true'}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.fields['main_residence'].required = False
        self.fields['main_residence'].queryset = (
            Place.objects.filter(project=project).order_by('name')
            if project else Place.objects.none()
        )
        self.fields['image'].required = False
        for field in self.fields.values():
            if not isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs.setdefault('class', 'form-control')

    def clean_main_residence(self):
        place = self.cleaned_data.get('main_residence')
        if place and self.project and place.project_id != self.project.id:
            raise forms.ValidationError('El lugar debe pertenecer al proyecto activo.')
        return place


class CharacterRelationshipForm(forms.Form):
    character_name = forms.CharField(
        max_length=200,
        label='Nombre del personaje relacionado',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Escribe el nombre, aunque todavía no tenga ficha…',
            'autocomplete': 'off',
        }),
    )
    relationship_type = forms.CharField(
        max_length=200,
        label='Tipo de relación',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej. padre, rival, mentor, amistad…',
        }),
    )
    description = forms.CharField(
        required=False,
        label='Descripción',
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': 'Detalles opcionales de la relación…',
            'data-autogrow': 'true',
        }),
    )

    def __init__(self, *args, project=None, current_character=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.current_character = current_character

    def clean_character_name(self):
        name = (self.cleaned_data.get('character_name') or '').strip()
        if not name:
            raise forms.ValidationError('Escribe el nombre del personaje relacionado.')
        if self.current_character and name.casefold() == self.current_character.full_name.strip().casefold():
            raise forms.ValidationError('No puedes crear una relación del personaje consigo mismo.')
        return name
