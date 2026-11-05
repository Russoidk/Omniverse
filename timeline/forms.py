from django import forms

from characters.models import Character
from projects.models import Place
from .models import Event, EventRelationship, TimelineSpan


class EventForm(forms.ModelForm):
    characters = forms.ModelMultipleChoiceField(
        queryset=Character.objects.none(), required=False,
        label='Personajes relacionados',
        widget=forms.SelectMultiple(attrs={'size': 5, 'class': 'form-control'}),
    )
    places = forms.ModelMultipleChoiceField(
        queryset=Place.objects.none(), required=False,
        label='Lugares relacionados',
        widget=forms.SelectMultiple(attrs={'size': 5, 'class': 'form-control'}),
    )

    class Meta:
        model = Event
        fields = ['title', 'description', 'date_value', 'date_era', 'date_type', 'event_type', 'timeline_span']
        labels = {
            'title': 'Nombre del acontecimiento',
            'description': 'Descripción',
            'date_value': 'Fecha o referencia temporal',
            'date_era': 'Era histórica',
            'date_type': 'Formato de fecha',
            'event_type': 'Tipo de acontecimiento',
            'timeline_span': 'Lapso de tiempo',
        }
        help_texts = {
            'timeline_span': 'Opcional. Si no se puede ordenar la fecha automáticamente, asigna aquí el lapso al que pertenece este acontecimiento.',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Ej. La caída de una capital'}),
            'description': forms.Textarea(attrs={'rows': 4, 'data-autogrow': 'true'}),
            'date_value': forms.TextInput(attrs={'placeholder': 'Ej. 29/02/774, año 774…'}),
            'date_era': forms.Select(attrs={'class': 'form-control'}),
            'event_type': forms.TextInput(attrs={'placeholder': 'Batalla, viaje, coronación… (texto libre)'}),
            'timeline_span': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.fields['characters'].queryset = Character.objects.filter(project=project).order_by('full_name')
        self.fields['places'].queryset = Place.objects.filter(project=project).order_by('name')
        self.fields['timeline_span'].queryset = TimelineSpan.objects.filter(project=project).order_by('start_value', 'title')
        self.fields['timeline_span'].required = False
        # Default older/imported clients without this control to D.C.
        self.fields['date_era'].required = False
        self.fields['date_era'].choices = self._era_choices(project)
        self.fields['timeline_span'].empty_label = 'Detectar por fecha / sin lapso'
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


    @staticmethod
    def _era_choices(project):
        if project is None:
            return Event.ERA_CHOICES
        return [
            (Event.ERA_BC, f'{project.era_bc_name} ({project.era_bc_abbreviation})'),
            (Event.ERA_AD, f'{project.era_ad_name} ({project.era_ad_abbreviation})'),
        ]

    def clean_date_era(self):
        return self.cleaned_data.get('date_era') or Event.ERA_AD

    def clean_timeline_span(self):
        span = self.cleaned_data.get('timeline_span')
        if span and self.project and span.project_id != self.project.id:
            raise forms.ValidationError('El lapso debe pertenecer al proyecto activo.')
        return span


class EventRelationshipForm(forms.ModelForm):
    class Meta:
        model = EventRelationship
        fields = ['event_2', 'relationship_type', 'description']
        labels = {
            'event_2': 'Acontecimiento relacionado',
            'relationship_type': 'Relación entre acontecimientos',
            'description': 'Descripción',
        }
        widgets = {
            'relationship_type': forms.TextInput(attrs={
                'placeholder': 'Ej. causó, ocurrió antes que, consecuencia de…'
            }),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, project=None, current_event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.current_event = current_event
        self.fields['event_2'].queryset = Event.objects.filter(
            project=project, span_marker=''
        ).exclude(pk=getattr(current_event, 'pk', None)).order_by('date_value', 'title')
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned = super().clean()
        event_2 = cleaned.get('event_2')
        relationship_type = cleaned.get('relationship_type')
        if self.project and self.current_event and event_2 and relationship_type:
            duplicate = EventRelationship.objects.filter(
                project=self.project,
                event_1=self.current_event,
                event_2=event_2,
                relationship_type=relationship_type,
            ).exists()
            if duplicate:
                raise forms.ValidationError('Esta relación ya existe entre esos acontecimientos.')
        return cleaned


class TimelineSpanForm(forms.ModelForm):
    class Meta:
        model = TimelineSpan
        fields = ['title', 'start_value', 'start_era', 'end_value', 'end_era', 'span_type', 'description']
        labels = {
            'title': 'Nombre del lapso',
            'start_value': 'Comienzo',
            'start_era': 'Era del comienzo',
            'end_value': 'Finalización',
            'end_era': 'Era de la finalización',
            'span_type': 'Categoría o tipo',
            'description': 'Descripción',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Ej. Periodo de reconstrucción'}),
            'start_value': forms.TextInput(attrs={'placeholder': 'Ej. 120'}),
            'start_era': forms.Select(attrs={'class': 'form-control'}),
            'end_value': forms.TextInput(attrs={'placeholder': 'Ej. 145'}),
            'end_era': forms.Select(attrs={'class': 'form-control'}),
            'span_type': forms.TextInput(attrs={'placeholder': 'Ej. Era, guerra, reinado… (texto libre)'}),
            'description': forms.Textarea(attrs={'rows': 3, 'data-autogrow': 'true', 'placeholder': 'Qué caracteriza este periodo…'}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_era'].required = False
        self.fields['end_era'].required = False
        if project is None and getattr(self.instance, 'project_id', None):
            project = self.instance.project
        if project:
            choices = [
                (Event.ERA_BC, f'{project.era_bc_name} ({project.era_bc_abbreviation})'),
                (Event.ERA_AD, f'{project.era_ad_name} ({project.era_ad_abbreviation})'),
            ]
        else:
            choices = Event.ERA_CHOICES
        self.fields['start_era'].choices = choices
        self.fields['end_era'].choices = choices
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean_start_era(self):
        return self.cleaned_data.get('start_era') or Event.ERA_AD

    def clean_end_era(self):
        return self.cleaned_data.get('end_era') or Event.ERA_AD
