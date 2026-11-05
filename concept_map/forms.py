from django import forms

from .models import ConceptConnection, ConceptNode


class ConceptConnectionForm(forms.ModelForm):
    class Meta:
        model = ConceptConnection
        fields = ['source_node', 'target_node', 'relationship_type', 'label', 'description']
        labels = {
            'source_node': 'Desde',
            'target_node': 'Hacia',
            'relationship_type': 'Tipo de conexión',
            'label': 'Etiqueta visible',
            'description': 'Descripción',
        }
        widgets = {
            'relationship_type': forms.TextInput(attrs={
                'placeholder': 'Ej. familia, causalidad, alianza…'
            }),
            'label': forms.TextInput(attrs={
                'placeholder': 'Ej. hija de, provocó, protege a…'
            }),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        if project is not None:
            self.instance.project = project
        nodes = ConceptNode.objects.filter(project=project).select_related('content_type')
        self.fields['source_node'].queryset = nodes
        self.fields['target_node'].queryset = nodes
        type_labels = {'CHARACTER': 'Personaje', 'EVENT': 'Acontecimiento', 'PLACE': 'Lugar'}
        def node_label(node):
            type_label = type_labels.get(node.node_type, 'Elemento')
            return f'{node.label} ({type_label})'
        self.fields['source_node'].label_from_instance = node_label
        self.fields['target_node'].label_from_instance = node_label
        self.fields['source_node'].empty_label = 'Elegir opción'
        self.fields['target_node'].empty_label = 'Elegir opción'
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get('source_node')
        target = cleaned.get('target_node')
        if source and target:
            if source.pk == target.pk:
                raise forms.ValidationError('Elige dos elementos distintos.')
            if source.project_id != self.project.id or target.project_id != self.project.id:
                raise forms.ValidationError('Solo puedes conectar elementos del proyecto activo.')
        return cleaned
