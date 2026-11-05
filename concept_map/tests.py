from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from characters.models import Character
from concept_map.models import ConceptConnection, ConceptNode
from projects.models import Project
from projects.utils import ensure_concept_node


class ConceptMapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='graph@example.com', password='TestPass-934!')
        self.project = Project.objects.create(user=self.user, name='Red de prueba')
        self.client.force_login(self.user)
        session = self.client.session
        session['active_project_id'] = self.project.pk
        session.save()

    def test_graph_builds_nodes_from_existing_entities(self):
        Character.objects.create(project=self.project, full_name='Personaje de prueba')
        response = self.client.get(reverse('concept_map'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Personaje de prueba')
        self.assertTrue(ConceptNode.objects.filter(project=self.project, node_type='CHARACTER').exists())

    def test_connection_between_nodes_is_saved(self):
        first = Character.objects.create(project=self.project, full_name='Personaje de prueba')
        second = Character.objects.create(project=self.project, full_name='Sarrath')
        node1 = ensure_concept_node(self.project, first, 'CHARACTER')
        node2 = ensure_concept_node(self.project, second, 'CHARACTER')
        response = self.client.post(reverse('concept_map'), {
            'source_node': node1.pk,
            'target_node': node2.pk,
            'relationship_type': 'familia',
            'label': 'hija de',
            'description': 'Relación de ejemplo',
        })
        self.assertRedirects(response, reverse('concept_map'))
        connection = ConceptConnection.objects.get(project=self.project)
        self.assertEqual(connection.label, 'hija de')

    def test_node_position_is_saved(self):
        char = Character.objects.create(project=self.project, full_name='Mover')
        node = ensure_concept_node(self.project, char, 'CHARACTER')
        response = self.client.post(
            reverse('concept_node_position', args=[node.pk]),
            data='{"x": 410, "y": 220}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        node.refresh_from_db()
        self.assertEqual(node.position_x, 410)
        self.assertEqual(node.position_y, 220)

    def test_existing_character_relationship_appears_automatically_in_graph(self):
        from characters.models import CharacterRelationship
        first = Character.objects.create(project=self.project, full_name='Personaje de prueba')
        second = Character.objects.create(project=self.project, full_name='Sarrath')
        CharacterRelationship.objects.create(
            project=self.project,
            character_1=first,
            character_2=second,
            relationship_type='hija de',
        )
        response = self.client.get(reverse('concept_map'))
        self.assertEqual(response.status_code, 200)
        graph = response.context['graph_data']
        self.assertTrue(any(edge['label'] == 'hija de' for edge in graph['connections']))


    def test_main_residence_creates_character_to_place_connection(self):
        from projects.models import Place
        from characters.models import Character
        place = Place.objects.create(project=self.project, name='Ciudad Central', type='Ciudad')
        character = Character.objects.create(project=self.project, full_name='Habitante', main_residence=place)
        response = self.client.get(reverse('concept_map'))
        self.assertEqual(response.status_code, 200)
        graph = response.context['graph_data']
        self.assertTrue(any(edge['label'] == 'vive en' for edge in graph['connections']))

    def test_connection_options_use_spanish_entity_types_and_placeholder(self):
        first = Character.objects.create(project=self.project, full_name='Habitante')
        second = Character.objects.create(project=self.project, full_name='Amiga')
        ensure_concept_node(self.project, first, 'CHARACTER')
        ensure_concept_node(self.project, second, 'CHARACTER')
        response = self.client.get(reverse('concept_map'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Elegir opción')
        self.assertContains(response, 'Personaje')
