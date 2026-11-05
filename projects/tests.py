from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from projects.models import Project, Place


class ProjectManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='owner@example.com', password='TestPass-934!')
        self.client.force_login(self.user)

    def test_unsubscribed_user_can_create_first_project(self):
        response = self.client.post(reverse('create_project'), {
            'name': 'Primer universo', 'description': 'Descripción de prueba'
        })
        project = Project.objects.get(user=self.user)
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(project.name, 'Primer universo')
        self.assertEqual(self.client.session['active_project_id'], project.pk)

    def test_unsubscribed_user_cannot_create_second_project(self):
        Project.objects.create(user=self.user, name='Proyecto uno')
        response = self.client.post(reverse('create_project'), {
            'name': 'Proyecto dos', 'description': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_limit.html')
        self.assertEqual(Project.objects.filter(user=self.user).count(), 1)

    def test_subscribed_user_can_create_multiple_projects(self):
        self.user.is_subscribed = True
        self.user.save(update_fields=['is_subscribed'])
        Project.objects.create(user=self.user, name='Proyecto uno')
        response = self.client.post(reverse('create_project'), {'name': 'Proyecto dos', 'description': ''})
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(Project.objects.filter(user=self.user).count(), 2)


    def test_project_settings_update_era_labels_and_dashboard_visibility(self):
        project = Project.objects.create(user=self.user, name='Proyecto original')
        session = self.client.session
        session['active_project_id'] = project.pk
        session.save()
        response = self.client.post(reverse('project_settings'), {
            'name': 'Proyecto actualizado',
            'description': 'Nueva descripción',
            'era_bc_name': 'Antes de la Era Común',
            'era_bc_abbreviation': 'a. e. c.',
            'era_ad_name': 'Era Común',
            'era_ad_abbreviation': 'e. c.',
            'dashboard_show_stats': 'on',
            'dashboard_show_module_cards': 'on',
        })
        project.refresh_from_db()
        self.assertRedirects(response, reverse('project_settings'))
        self.assertEqual(project.name, 'Proyecto actualizado')
        self.assertEqual(project.era_bc_abbreviation, 'a. e. c.')
        self.assertEqual(project.era_ad_name, 'Era Común')
        self.assertTrue(project.dashboard_show_stats)
        self.assertTrue(project.dashboard_show_module_cards)
        self.assertFalse(project.dashboard_show_recent_events)

    def test_places_are_scoped_to_active_project(self):
        project = Project.objects.create(user=self.user, name='Mi proyecto')
        other_user = User.objects.create_user(email='other@example.com', password='TestPass-934!')
        foreign_project = Project.objects.create(user=other_user, name='Otro')
        foreign_place = Place.objects.create(project=foreign_project, name='Ciudad ajena', type='Ciudad')
        session = self.client.session
        session['active_project_id'] = project.pk
        session.save()
        response = self.client.get(reverse('place_edit', args=[foreign_place.pk]))
        self.assertEqual(response.status_code, 404)
