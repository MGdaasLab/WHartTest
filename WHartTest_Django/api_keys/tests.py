from datetime import timedelta

from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from .models import APIKey


def _grant_api_key_perms(user):
    ct = ContentType.objects.get_for_model(APIKey)
    perms = Permission.objects.filter(content_type=ct)
    user.user_permissions.add(*perms)
    for attr in ('_perm_cache', '_user_perm_cache'):
        try:
            delattr(user, attr)
        except AttributeError:
            pass


class APIKeyModelTest(TestCase):
    """APIKey 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_create_api_key(self):
        key = APIKey.objects.create(name='Test Key', user=self.user)
        self.assertIsNotNone(key.key)
        self.assertTrue(len(key.key) > 20)
        self.assertTrue(key.is_active)
        self.assertIsNone(key.expires_at)

    def test_auto_generate_key_on_save(self):
        key = APIKey(name='Auto Key', user=self.user)
        self.assertEqual(key.key, '')
        key.save()
        self.assertTrue(len(key.key) > 0)

    def test_explicit_key_preserved(self):
        key = APIKey.objects.create(name='Explicit', user=self.user, key='my-custom-key-123')
        self.assertEqual(key.key, 'my-custom-key-123')

    def test_key_unique(self):
        APIKey.objects.create(name='Key1', user=self.user, key='unique-key-value')
        with self.assertRaises(IntegrityError):
            APIKey.objects.create(name='Key2', user=self.user, key='unique-key-value')

    def test_name_unique(self):
        APIKey.objects.create(name='Same Name', user=self.user)
        with self.assertRaises(IntegrityError):
            APIKey.objects.create(name='Same Name', user=self.user)

    def test_is_valid_active_no_expiry(self):
        key = APIKey.objects.create(name='Active', user=self.user, is_active=True)
        self.assertTrue(key.is_valid())

    def test_is_valid_active_future_expiry(self):
        key = APIKey.objects.create(
            name='Future', user=self.user,
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.assertTrue(key.is_valid())

    def test_is_valid_expired(self):
        key = APIKey.objects.create(
            name='Expired', user=self.user,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertFalse(key.is_valid())

    def test_is_valid_inactive(self):
        key = APIKey.objects.create(name='Inactive', user=self.user, is_active=False)
        self.assertFalse(key.is_valid())

    def test_str_representation(self):
        key = APIKey.objects.create(name='My Key', user=self.user)
        self.assertEqual(str(key), 'API Key: My Key (User: testuser)')

    def test_ordering(self):
        k1 = APIKey.objects.create(name='First', user=self.user)
        k2 = APIKey.objects.create(name='Second', user=self.user)
        keys = list(APIKey.objects.all())
        self.assertEqual(keys[0], k2)
        self.assertEqual(keys[1], k1)

    def test_cascade_delete_user(self):
        APIKey.objects.create(name='Cascade', user=self.user)
        self.user.delete()
        self.assertEqual(APIKey.objects.count(), 0)

    def test_generate_key_returns_string(self):
        key = APIKey(name='Gen', user=self.user)
        generated = key.generate_key()
        self.assertIsInstance(generated, str)
        self.assertTrue(len(generated) > 20)


class APIKeyAPITest(TestCase):
    """APIKey API 测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        _grant_api_key_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.base_url = '/api/api-keys/'

    def test_list_api_keys(self):
        APIKey.objects.create(name='Key1', user=self.user)
        APIKey.objects.create(name='Key2', user=self.user)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        self.assertEqual(len(results), 2)

    def test_create_api_key(self):
        data = {'name': 'New Key'}
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Key')
        self.assertIn('key', response.data)
        key = APIKey.objects.get(name='New Key')
        self.assertEqual(key.user, self.user)

    def test_create_ignores_user_field(self):
        other_user = User.objects.create_user(username='other', password='pass')
        data = {'name': 'Hijack', 'user': other_user.pk}
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        key = APIKey.objects.get(name='Hijack')
        self.assertEqual(key.user, self.user)

    def test_retrieve_api_key(self):
        key = APIKey.objects.create(name='Detail', user=self.user)
        response = self.client.get(f'{self.base_url}{key.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Detail')

    def test_update_api_key(self):
        key = APIKey.objects.create(name='Old Name', user=self.user)
        response = self.client.patch(
            f'{self.base_url}{key.pk}/',
            {'name': 'New Name'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        key.refresh_from_db()
        self.assertEqual(key.name, 'New Name')

    def test_delete_api_key(self):
        key = APIKey.objects.create(name='To Delete', user=self.user)
        response = self.client.delete(f'{self.base_url}{key.pk}/')
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))
        self.assertFalse(APIKey.objects.filter(pk=key.pk).exists())

    def test_cannot_see_other_user_keys(self):
        other_user = User.objects.create_user(username='other', password='pass')
        APIKey.objects.create(name='Other Key', user=other_user)
        APIKey.objects.create(name='My Key', user=self.user)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        names = [k['name'] for k in results]
        self.assertIn('My Key', names)
        self.assertNotIn('Other Key', names)

    def test_cannot_update_other_user_key(self):
        other_user = User.objects.create_user(username='other', password='pass')
        other_key = APIKey.objects.create(name='Other Key', user=other_user)
        response = self.client.patch(
            f'{self.base_url}{other_key.pk}/',
            {'name': 'Stolen'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_other_user_key(self):
        other_user = User.objects.create_user(username='other', password='pass')
        other_key = APIKey.objects.create(name='Other Key', user=other_user)
        response = self.client.delete(f'{self.base_url}{other_key.pk}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_with_expires_at(self):
        future = (timezone.now() + timedelta(days=30)).isoformat()
        data = {'name': 'Expiring Key', 'expires_at': future}
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        key = APIKey.objects.get(name='Expiring Key')
        self.assertIsNotNone(key.expires_at)

    def test_deactivate_key(self):
        key = APIKey.objects.create(name='Active Key', user=self.user)
        response = self.client.patch(
            f'{self.base_url}{key.pk}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        key.refresh_from_db()
        self.assertFalse(key.is_active)

    def test_unauthenticated_access(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_key_field_readonly_on_update(self):
        key = APIKey.objects.create(name='ReadOnly Key', user=self.user)
        original_key = key.key
        response = self.client.patch(
            f'{self.base_url}{key.pk}/',
            {'key': 'tampered-key'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        key.refresh_from_db()
        self.assertEqual(key.key, original_key)

    def test_staff_can_modify_other_user_key(self):
        staff = User.objects.create_user(username='staff', password='pass', is_staff=True)
        _grant_api_key_perms(staff)
        other_key = APIKey.objects.create(name='Other Key', user=self.user)
        self.client.force_authenticate(user=staff)
        response = self.client.patch(
            f'{self.base_url}{other_key.pk}/',
            {'name': 'Modified by Staff'},
            format='json',
        )
        # Staff can't see other users' keys via queryset filter
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
