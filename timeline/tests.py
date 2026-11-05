from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from characters.models import Character
from projects.models import Project, Place
from timeline.models import Event, EventCharacter, EventPlace


class TimelineWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='timeline@example.com', password='TestPass-934!')
        self.project = Project.objects.create(user=self.user, name='Historia')
        self.client.force_login(self.user)
        session = self.client.session
        session['active_project_id'] = self.project.pk
        session.save()

    def test_create_event_and_link_entities(self):
        character = Character.objects.create(project=self.project, full_name='Protagonista')
        place = Place.objects.create(project=self.project, name='Ciudad Central', type='Ciudad')
        response = self.client.post(reverse('event_create'), {
            'title': 'Llegada a Ciudad Central',
            'description': 'Prueba de acontecimiento',
            'date_value': 'tres días después',
            'date_type': 'TEXT',
            'event_type': 'Viaje',
            'characters': [str(character.pk)],
            'places': [str(place.pk)],
        })
        event = Event.objects.get(project=self.project, title='Llegada a Ciudad Central')
        self.assertRedirects(response, reverse('event_detail', args=[event.pk]))
        self.assertTrue(EventCharacter.objects.filter(event=event, character=character).exists())
        self.assertTrue(EventPlace.objects.filter(event=event, place=place).exists())


    def test_create_event_without_links_and_choose_ancient_era(self):
        response = self.client.post(reverse('event_create'), {
            'title': 'Fundación antigua',
            'description': 'Acontecimiento de prueba.',
            'date_value': '450',
            'date_era': 'BC',
            'date_type': 'YEAR',
            'event_type': 'Fundación',
            'timeline_span': '',
            'characters': [],
            'places': [],
        })
        event = Event.objects.get(project=self.project, title='Fundación antigua')
        self.assertEqual(event.date_era, Event.ERA_BC)
        self.assertEqual(response.status_code, 302)
        from concept_map.models import ConceptNode
        self.assertTrue(ConceptNode.objects.filter(project=self.project, object_id=event.pk).exists())


    def test_event_dates_use_custom_project_era_abbreviations(self):
        self.project.era_bc_name = 'Antes de la Era Común'
        self.project.era_bc_abbreviation = 'a. e. c.'
        self.project.save()
        event = Event.objects.create(
            project=self.project, title='Fundación', date_value='450', date_era='BC', date_type='YEAR'
        )
        self.assertEqual(event.display_date, '450 a. e. c.')

    def test_automatic_birth_event_cannot_be_deleted_manually(self):
        from timeline.services import sync_birth_event
        character = Character.objects.create(project=self.project, full_name='Nacida', birth_date='774')
        event = sync_birth_event(character)
        response = self.client.post(reverse('event_delete', args=[event.pk]))
        self.assertRedirects(response, reverse('event_detail', args=[event.pk]))
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())

    def test_subscribed_account_can_export_timeline(self):
        self.user.is_subscribed = True
        self.user.save(update_fields=['is_subscribed'])
        Event.objects.create(project=self.project, title='Evento de prueba', date_value='774')
        for fmt, content_type in [('pdf', 'application/pdf'), ('png', 'image/png')]:
            response = self.client.get(reverse('timeline_export', args=[fmt]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], content_type)

    def test_event_relationship_is_saved(self):
        first = Event.objects.create(project=self.project, title='Batalla', event_type='Guerra')
        second = Event.objects.create(project=self.project, title='Tratado', event_type='Política')
        response = self.client.post(reverse('event_add_relationship', args=[first.pk]), {
            'event_2': str(second.pk),
            'relationship_type': 'provocó',
            'description': 'La batalla llevó a la firma del tratado.',
        })
        from timeline.models import EventRelationship
        relation = EventRelationship.objects.get(project=self.project, event_1=first, event_2=second)
        self.assertRedirects(response, reverse('event_detail', args=[first.pk]))
        self.assertEqual(relation.relationship_type, 'provocó')


class TimelineSpanNestingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='spans@example.com', password='TestPass-934!')
        self.project = Project.objects.create(user=self.user, name='Cronología con lapsos')
        self.client.force_login(self.user)
        session = self.client.session
        session['active_project_id'] = self.project.pk
        session.save()

    def test_span_creates_start_and_end_events_and_nests_events_in_range(self):
        from timeline.models import TimelineSpan
        span = TimelineSpan.objects.create(
            project=self.project,
            title='Periodo de reconstrucción',
            start_value='100',
            end_value='200',
            span_type='Era',
            description='Una etapa importante.',
        )
        inner_event = Event.objects.create(
            project=self.project, title='Se funda la ciudad', date_value='150', event_type='Fundación'
        )
        boundary_year_event = Event.objects.create(
            project=self.project, title='Acontecimiento del año inicial', date_value='100', event_type='Inicio'
        )
        response = self.client.get(reverse('timeline'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Event.objects.filter(timeline_span=span, span_marker='START', date_value='100').exists())
        self.assertTrue(Event.objects.filter(timeline_span=span, span_marker='END', date_value='200').exists())
        span_item = next(item for item in response.context['timeline_items'] if item['kind'] == 'span')
        self.assertEqual(
            {event.pk for event in span_item['span'].inner_events},
            {inner_event.pk, boundary_year_event.pk},
        )
        # Los marcadores de la versión visual actual usan las etiquetas INICIO y FINAL.
        self.assertContains(response, 'INICIO')
        self.assertContains(response, 'FINAL')
        self.assertContains(response, 'Inicio del lapso: Periodo de reconstrucción')
        self.assertContains(response, 'Final del lapso: Periodo de reconstrucción')

    def test_event_can_be_manually_assigned_to_a_text_only_span(self):
        from timeline.models import TimelineSpan
        span = TimelineSpan.objects.create(
            project=self.project, title='Viaje largo', start_value='Salida al amanecer', end_value='Llegada al anochecer'
        )
        event = Event.objects.create(
            project=self.project, title='Cruza el bosque', date_value='A mitad del camino', timeline_span=span
        )
        response = self.client.get(reverse('timeline'))
        span_item = next(item for item in response.context['timeline_items'] if item['kind'] == 'span')
        self.assertIn(event.pk, [child.pk for child in span_item['span'].inner_events])


    def test_span_nesting_respects_before_christ_and_after_christ(self):
        from timeline.models import TimelineSpan
        span = TimelineSpan.objects.create(
            project=self.project, title='República antigua',
            start_value='300', start_era='BC', end_value='100', end_era='BC',
        )
        ancient = Event.objects.create(
            project=self.project, title='Tratado antiguo', date_value='200', date_era='BC',
        )
        modern = Event.objects.create(
            project=self.project, title='Acontecimiento posterior', date_value='200', date_era='AD',
        )
        response = self.client.get(reverse('timeline'))
        self.assertEqual(response.status_code, 200)
        span_item = next(item for item in response.context['timeline_items'] if item['kind'] == 'span')
        self.assertIn(ancient.pk, [event.pk for event in span_item['span'].inner_events])
        self.assertNotIn(modern.pk, [event.pk for event in span_item['span'].inner_events])

    def test_deleting_span_preserves_real_events_assigned_to_it(self):
        from timeline.models import TimelineSpan
        span = TimelineSpan.objects.create(
            project=self.project, title='Campaña', start_value='100', end_value='110'
        )
        event = Event.objects.create(
            project=self.project, title='Batalla intermedia', date_value='105', timeline_span=span
        )
        response = self.client.post(reverse('span_delete', args=[span.pk]))
        self.assertRedirects(response, reverse('timeline'))
        event.refresh_from_db()
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())
        self.assertIsNone(event.timeline_span_id)
        self.assertFalse(Event.objects.filter(span_marker__in=['START', 'END']).exists())

