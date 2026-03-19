from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='no-reply@test.local',
)
class PasswordResetEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='reset_user',
            email='reset_user@test.local',
            password='pass12345',
        )

    def test_password_reset_request_sends_email(self):
        response = self.client.post(
            reverse('password_reset'),
            {'email': self.user.email},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Reset your BookMySeat password', mail.outbox[0].subject)
        self.assertIn('/password-reset-confirm/', mail.outbox[0].body)

    def test_password_reset_rejects_unknown_email(self):
        response = self.client.post(
            reverse('password_reset'),
            {'email': 'missing@test.local'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No active account found with this email address.')
        self.assertEqual(len(mail.outbox), 0)
