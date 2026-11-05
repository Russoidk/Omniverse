from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class LocalWebsiteTests(TestCase):
    def test_landing_is_public(self):
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cada idea merece')
        self.assertContains(response, reverse('register'))

    def test_registration_creates_free_account_and_logs_in(self):
        response = self.client.post(reverse('register'), {
            'email': 'Creador@ejemplo.com',
            'first_name': 'Creador',
            'password1': 'ClaveLocalSegura2026!',
            'password2': 'ClaveLocalSegura2026!',
        })
        self.assertRedirects(response, reverse('web_account'))
        user = User.objects.get(email='creador@ejemplo.com')
        self.assertFalse(user.is_subscribed)
        self.assertTrue(self.client.session.get('_auth_user_id'))

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(email='repetido@ejemplo.com', password='ClaveLocalSegura2026!')
        response = self.client.post(reverse('register'), {
            'email': 'REPETIDO@ejemplo.com',
            'first_name': '',
            'password1': 'ClaveLocalSegura2026!',
            'password2': 'ClaveLocalSegura2026!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe una cuenta')
        self.assertEqual(User.objects.filter(email__iexact='repetido@ejemplo.com').count(), 1)

    def test_web_login_uses_same_account(self):
        user = User.objects.create_user(email='inicio@ejemplo.com', password='ClaveLocalSegura2026!')
        response = self.client.post(reverse('web_login'), {
            'username': 'inicio@ejemplo.com',
            'password': 'ClaveLocalSegura2026!',
        })
        self.assertRedirects(response, reverse('web_account'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)


    def test_site_account_and_subscription_pages_render(self):
        user = User.objects.create_user(email='paginas@ejemplo.com', password='ClaveLocalSegura2026!')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('web_account')).status_code, 200)
        response = self.client.get(reverse('web_subscription'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activar suscripción simulada')

    def test_application_login_links_to_local_registration(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/crear-cuenta/"')
        self.assertNotContains(response, 'https://example.com')

    def test_subscription_can_be_activated_and_cancelled(self):
        user = User.objects.create_user(email='plan@ejemplo.com', password='ClaveLocalSegura2026!')
        self.client.force_login(user)
        response = self.client.post(reverse('activate_subscription'))
        self.assertRedirects(response, reverse('web_account'))
        user.refresh_from_db()
        self.assertTrue(user.is_subscribed)
        response = self.client.post(reverse('cancel_subscription'))
        self.assertRedirects(response, reverse('web_account'))
        user.refresh_from_db()
        self.assertFalse(user.is_subscribed)

    def test_subscription_actions_require_login_and_post(self):
        response = self.client.post(reverse('activate_subscription'))
        self.assertRedirects(response, f"{reverse('web_login')}?next={reverse('activate_subscription')}")
        user = User.objects.create_user(email='metodo@ejemplo.com', password='ClaveLocalSegura2026!')
        self.client.force_login(user)
        response = self.client.get(reverse('activate_subscription'))
        self.assertEqual(response.status_code, 405)

    def test_password_change_preserves_web_session(self):
        user = User.objects.create_user(email='clave@ejemplo.com', password='ClaveLocalSegura2026!')
        self.client.force_login(user)
        response = self.client.post(reverse('web_change_password'), {
            'old_password': 'ClaveLocalSegura2026!',
            'new_password1': 'NuevaClaveLocal2027!',
            'new_password2': 'NuevaClaveLocal2027!',
        })
        self.assertRedirects(response, reverse('web_account'))
        user.refresh_from_db()
        self.assertTrue(user.check_password('NuevaClaveLocal2027!'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_program_has_separate_route(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
