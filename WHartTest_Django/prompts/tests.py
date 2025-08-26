from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import UserPrompt


class UserPromptModelTests(TestCase):
    """用户提示词模型测试"""

    def setUp(self):
        """测试前准备"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # 创建默认提示词
        self.default_prompt = UserPrompt.objects.create(
            user=self.user,
            name="默认提示词",
            content="这是默认提示词内容",
            description="默认提示词描述",
            is_default=True,
            is_active=True
        )

        # 创建非默认提示词
        self.normal_prompt = UserPrompt.objects.create(
            user=self.user,
            name="普通提示词",
            content="这是普通提示词内容",
            description="普通提示词描述",
            is_default=False,
            is_active=True
        )

    def test_default_prompt_uniqueness(self):
        """测试默认提示词唯一性"""
        # 尝试创建另一个默认提示词
        new_prompt = UserPrompt.objects.create(
            user=self.user,
            name="另一个默认提示词",
            content="另一个默认提示词内容",
            is_default=True,
            is_active=True
        )

        # 检查原来的默认提示词是否被取消默认
        self.default_prompt.refresh_from_db()
        self.assertFalse(self.default_prompt.is_default)
        self.assertTrue(new_prompt.is_default)

    def test_get_user_default_prompt(self):
        """测试获取用户默认提示词"""
        default_prompt = UserPrompt.get_user_default_prompt(self.user)
        self.assertEqual(default_prompt, self.default_prompt)

    def test_get_user_prompts(self):
        """测试获取用户所有提示词"""
        prompts = UserPrompt.get_user_prompts(self.user)
        self.assertEqual(prompts.count(), 2)


class UserPromptAPITests(TestCase):
    """用户提示词API测试"""

    def setUp(self):
        """测试前准备"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # 创建默认提示词
        self.default_prompt = UserPrompt.objects.create(
            user=self.user,
            name="默认提示词",
            content="这是默认提示词内容",
            description="默认提示词描述",
            is_default=True,
            is_active=True
        )

        # 创建非默认提示词
        self.normal_prompt = UserPrompt.objects.create(
            user=self.user,
            name="普通提示词",
            content="这是普通提示词内容",
            description="普通提示词描述",
            is_default=False,
            is_active=True
        )

        # 登录
        self.client.force_authenticate(user=self.user)

    def test_list_prompts(self):
        """测试获取提示词列表"""
        url = '/api/prompts/user-prompts/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 在测试环境中，响应直接是列表格式
        self.assertEqual(len(response.data), 2)

    def test_get_default_prompt(self):
        """测试获取默认提示词"""
        url = '/api/prompts/user-prompts/default/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 在测试环境中，检查响应格式
        if isinstance(response.data, dict) and 'data' in response.data:
            self.assertEqual(response.data['data']['id'], self.default_prompt.id)
        else:
            self.assertEqual(response.data['id'], self.default_prompt.id)

    def test_create_prompt(self):
        """测试创建提示词"""
        url = '/api/prompts/user-prompts/'
        data = {
            'name': '新提示词',
            'content': '这是新提示词内容',
            'description': '新提示词描述',
            'is_default': False,
            'is_active': True
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserPrompt.objects.count(), 3)
        # 验证返回的数据
        if isinstance(response.data, dict) and 'data' in response.data:
            self.assertEqual(response.data['data']['name'], '新提示词')
        else:
            self.assertEqual(response.data['name'], '新提示词')

    def test_set_default_prompt(self):
        """测试设置默认提示词"""
        url = f'/api/prompts/user-prompts/{self.normal_prompt.id}/set_default/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 检查是否成功设置为默认
        self.normal_prompt.refresh_from_db()
        self.default_prompt.refresh_from_db()
        self.assertTrue(self.normal_prompt.is_default)
        self.assertFalse(self.default_prompt.is_default)

    def test_duplicate_prompt(self):
        """测试复制提示词"""
        url = f'/api/prompts/user-prompts/{self.default_prompt.id}/duplicate/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserPrompt.objects.count(), 3)

        # 检查复制的提示词
        duplicate_name = f"{self.default_prompt.name} (副本)"
        duplicate_exists = UserPrompt.objects.filter(name=duplicate_name).exists()
        self.assertTrue(duplicate_exists)
