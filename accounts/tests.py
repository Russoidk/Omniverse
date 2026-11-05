from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from projects.models import Project


class AuthenticationAndProjectAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='author@example.com', password='TestPass-934!')
        self.other_user = User.objects.create_user(email='other@example.com', password='TestPass-934!')
        self.project = Project.objects.create(user=self.user, name='Universo propio')
        self.other_project = Project.objects.create(user=self.other_user, name='Universo ajeno')

    def test_home_requires_login(self):
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, f'{reverse("login")}?next={reverse("home")}')

    def test_login_form_accepts_email(self):
        response = self.client.post(reverse('login'), {
            'username': 'author@example.com',
            'password': 'TestPass-934!',
        })
        self.assertRedirects(response, reverse('home'))

    def test_user_cannot_select_another_users_project(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('select_project', args=[self.other_project.pk]))
        self.assertEqual(response.status_code, 404)

    def test_home_only_lists_own_projects(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Universo propio')
        self.assertNotContains(response, 'Universo ajeno')

    def test_logout_requires_post_and_ends_session(self):
        self.client.force_login(self.user)
        get_response = self.client.get(reverse('logout'))
        self.assertEqual(get_response.status_code, 405)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        home_response = self.client.get(reverse('home'))
        self.assertEqual(home_response.status_code, 302)
