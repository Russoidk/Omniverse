from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from characters.models import Character
from concept_map.models import ConceptNode
from projects.models import Project
from timeline.models import Event, EventCharacter


class CharacterWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='writer@example.com', password='TestPass-934!')
        self.project = Project.objects.create(user=self.user, name='Proyecto de prueba')
        self.client.force_login(self.user)
        session = self.client.session
        session['active_project_id'] = self.project.pk
        session.save()

    def test_character_birth_creates_timeline_event_and_graph_node(self):
        response = self.client.post(reverse('character_create'), {
            'full_name': 'Personaje de prueba',
            'birth_date': '29/02/774',
            'role': 'Protagonista',
        })
        character = Character.objects.get(project=self.project, full_name='Personaje de prueba')
        self.assertRedirects(response, reverse('character_detail', args=[character.pk]))
        event = Event.objects.get(project=self.project, automatic=True, event_type='Nacimiento')
        self.assertEqual(event.date_value, '29/02/774')
        self.assertEqual(event.title, 'Nacimiento de Personaje de prueba')
        self.assertTrue(EventCharacter.objects.filter(event=event, character=character, role='Nacido/a').exists())
        self.assertTrue(ConceptNode.objects.filter(project=self.project, object_id=character.pk, node_type='CHARACTER').exists())

    def test_changing_birth_date_updates_same_event(self):
        character = Character.objects.create(project=self.project, full_name='Aria', birth_date='año 120')
        from timeline.services import sync_birth_event
        sync_birth_event(character)
        first_id = Event.objects.get(project=self.project, automatic=True).pk
        character.birth_date = 'año 121'
        character.full_name = 'Aria nueva'
        character.save()
        sync_birth_event(character)
        events = Event.objects.filter(project=self.project, automatic=True)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().pk, first_id)
        self.assertEqual(events.first().title, 'Nacimiento de Aria nueva')
        self.assertEqual(events.first().date_value, 'año 121')

    def test_character_list_does_not_show_foreign_project(self):
        other_user = User.objects.create_user(email='other@example.com', password='TestPass-934!')
        other_project = Project.objects.create(user=other_user, name='Otro mundo')
        Character.objects.create(project=other_project, full_name='Personaje secreto')
        response = self.client.get(reverse('characters'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Personaje secreto')

    def test_exports_are_blocked_for_unsubscribed_accounts(self):
        character = Character.objects.create(project=self.project, full_name='Exportación')
        response = self.client.get(reverse('character_export', args=[character.pk, 'pdf']))
        self.assertRedirects(response, reverse('character_detail', args=[character.pk]))

    def test_subscribed_account_can_export_pdf_and_png(self):
        self.user.is_subscribed = True
        self.user.save(update_fields=['is_subscribed'])
        character = Character.objects.create(project=self.project, full_name='Exportación', dominant_traits='Valiente')
        for fmt, content_type in [('pdf', 'application/pdf'), ('png', 'image/png')]:
            response = self.client.get(reverse('character_export', args=[character.pk, fmt]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], content_type)
            self.assertTrue(len(response.content) > 200)

    def test_character_relationship_is_saved_as_free_text(self):
        first = Character.objects.create(project=self.project, full_name='Personaje de prueba')
        second = Character.objects.create(project=self.project, full_name='Sarrath')
        response = self.client.post(reverse('character_add_relationship', args=[first.pk]), {
            'character_name': second.full_name,
            'relationship_type': 'la única persona en quien confía',
            'description': 'Se conocen desde la infancia.',
        })
        from characters.models import CharacterRelationship
        relation = CharacterRelationship.objects.get(project=self.project, character_1=first, character_2=second)
        self.assertRedirects(response, reverse('character_detail', args=[first.pk]))
        self.assertEqual(relation.relationship_type, 'la única persona en quien confía')

    def test_unknown_relationship_name_can_be_kept_without_a_character_sheet(self):
        from characters.models import CharacterRelationship
        source = Character.objects.create(project=self.project, full_name='Personaje principal')
        response = self.client.post(reverse('character_add_relationship', args=[source.pk]), {
            'character_name': 'Alguien del pasado',
            'relationship_type': 'antiguo mentor',
            'description': 'No quiero crearle una ficha todavía.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'characters/relationship_confirm.html')
        self.assertContains(response, 'Crear ficha vacía')
        response = self.client.post(reverse('character_add_relationship', args=[source.pk]), {
            'character_name': 'Alguien del pasado',
            'relationship_type': 'antiguo mentor',
            'description': 'No quiero crearle una ficha todavía.',
            'decision': 'reference',
        })
        relation = CharacterRelationship.objects.get(project=self.project, character_1=source)
        self.assertRedirects(response, reverse('character_detail', args=[source.pk]))
        self.assertIsNone(relation.character_2_id)
        self.assertEqual(relation.character_2_name, 'Alguien del pasado')

    def test_unknown_relationship_name_can_create_an_empty_character_sheet(self):
        from characters.models import CharacterRelationship
        source = Character.objects.create(project=self.project, full_name='Personaje principal')
        response = self.client.post(reverse('character_add_relationship', args=[source.pk]), {
            'character_name': 'Persona nueva',
            'relationship_type': 'hermana',
            'description': '',
            'decision': 'create',
        })
        target = Character.objects.get(project=self.project, full_name='Persona nueva')
        relation = CharacterRelationship.objects.get(project=self.project, character_1=source, character_2=target)
        self.assertRedirects(response, reverse('character_detail', args=[source.pk]))
        self.assertEqual(relation.relationship_type, 'hermana')
        self.assertTrue(ConceptNode.objects.filter(project=self.project, object_id=target.pk, node_type='CHARACTER').exists())

