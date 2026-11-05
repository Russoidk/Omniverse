from django import forms

from .models import Project, Place


class ProjectForm(forms.ModelForm):

    class Meta:
        model = Project

        fields = [
            'name',
            'description',
        ]

        labels = {
            'name': 'Nombre del proyecto',
            'description': 'Descripción',
        }

        widgets = {
            'name': forms.TextInput(
                attrs={
                    'placeholder': 'Ej. Proyecto de fantasía'
                }
            ),

            'description': forms.Textarea(
                attrs={
                    'placeholder': 'Describe brevemente tu universo...',
                    'rows': 4
                }
            ),
        }

class PlaceForm(forms.ModelForm):
    class Meta:
        model = Place
        fields = ['name', 'type', 'description', 'image']
        labels = {
            'name': 'Nombre del lugar',
            'type': 'Tipo de lugar',
            'description': 'Descripción',
            'image': 'Imagen',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nombre del lugar'}),
            'type': forms.TextInput(attrs={'placeholder': 'Ciudad, reino, edificio… (texto libre)'}),
            'description': forms.Textarea(attrs={'rows': 4, 'data-autogrow': 'true'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class ProjectSettingsForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            'name', 'description',
            'era_bc_name', 'era_bc_abbreviation',
            'era_ad_name', 'era_ad_abbreviation',
            'dashboard_show_stats', 'dashboard_show_module_cards', 'dashboard_show_recent_events',
        ]
        labels = {
            'name': 'Nombre del proyecto',
            'description': 'Descripción del proyecto',
            'era_bc_name': 'Nombre de la era anterior',
            'era_bc_abbreviation': 'Abreviatura de la era anterior',
            'era_ad_name': 'Nombre de la era posterior',
            'era_ad_abbreviation': 'Abreviatura de la era posterior',
            'dashboard_show_stats': 'Mostrar estadísticas del proyecto',
            'dashboard_show_module_cards': 'Mostrar accesos rápidos a los módulos',
            'dashboard_show_recent_events': 'Mostrar actividad reciente de la cronología',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'data-autogrow': 'true'}),
            'era_bc_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Antes de la Era Común'}),
            'era_bc_abbreviation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. a. e. c.'}),
            'era_ad_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Era Común'}),
            'era_ad_abbreviation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. e. c.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('dashboard_show_stats', 'dashboard_show_module_cards', 'dashboard_show_recent_events'):
            self.fields[name].widget.attrs.update({'class': 'settings-checkbox'})

    def clean_era_bc_name(self):
        return (self.cleaned_data.get('era_bc_name') or '').strip() or 'Antes de Cristo'

    def clean_era_bc_abbreviation(self):
        return (self.cleaned_data.get('era_bc_abbreviation') or '').strip() or 'A.C.'

    def clean_era_ad_name(self):
        return (self.cleaned_data.get('era_ad_name') or '').strip() or 'Después de Cristo'

    def clean_era_ad_abbreviation(self):
        return (self.cleaned_data.get('era_ad_abbreviation') or '').strip() or 'D.C.'
