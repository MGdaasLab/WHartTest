from django.contrib.auth.models import User
from rest_framework.test import APITestCase


class UserRegistrationSecurityTests(APITestCase):
    def test_registration_cannot_set_privileged_account_flags(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "username": "registration-attacker",
                "password": "Test1234!",
                "email": "attacker@example.com",
                "is_staff": True,
                "is_superuser": True,
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        user = User.objects.get(username="registration-attacker")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertEqual(user.user_permissions.count(), 0)

        payload = response.json()["data"]
        self.assertFalse(payload["is_staff"])
        self.assertTrue(payload["is_active"])

        login_response = self.client.post(
            "/api/token/",
            {"username": user.username, "password": "Test1234!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertFalse(login_response.json()["data"]["user"]["is_staff"])
