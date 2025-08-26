from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from projects.models import Project, ProjectMember


class ProjectOwnerTests(TestCase):
    """测试项目拥有者相关功能"""

    def setUp(self):
        """设置测试环境"""
        # 创建测试用户
        self.owner = User.objects.create_user(
            username='owner_user',
            email='owner@example.com',
            password='password123'
        )
        self.admin = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            password='password123'
        )
        self.member = User.objects.create_user(
            username='member_user',
            email='member@example.com',
            password='password123'
        )
        self.new_owner = User.objects.create_user(
            username='new_owner_user',
            email='new_owner@example.com',
            password='password123'
        )

        # 创建测试项目
        self.project = Project.objects.create(
            name='Test Project',
            description='Test Project Description',
            creator=self.owner
        )

        # 添加项目成员
        ProjectMember.objects.create(
            project=self.project,
            user=self.owner,
            role='owner'
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.admin,
            role='admin'
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='member'
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.new_owner,
            role='member'
        )

        # 设置API客户端
        self.client = APIClient()

    def test_change_project_owner(self):
        """测试更改项目拥有者，原拥有者应自动降级为管理员"""
        # 登录原拥有者
        self.client.force_authenticate(user=self.owner)

        # 构建请求URL和数据
        url = reverse('project-update-member-role', args=[self.project.id])
        data = {
            'user_id': self.new_owner.id,
            'role': 'owner'
        }

        # 发送请求
        response = self.client.patch(url, data, format='json')

        # 验证响应
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证新拥有者角色
        new_owner_membership = ProjectMember.objects.get(project=self.project, user=self.new_owner)
        self.assertEqual(new_owner_membership.role, 'owner')

        # 验证原拥有者角色已降级为管理员
        original_owner_membership = ProjectMember.objects.get(project=self.project, user=self.owner)
        self.assertEqual(original_owner_membership.role, 'admin')

    def test_only_one_owner_allowed(self):
        """测试项目只能有一个拥有者"""
        # 登录原拥有者
        self.client.force_authenticate(user=self.owner)

        # 先将管理员设为拥有者
        url = reverse('project-update-member-role', args=[self.project.id])
        data = {
            'user_id': self.admin.id,
            'role': 'owner'
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 再将普通成员设为拥有者
        data = {
            'user_id': self.member.id,
            'role': 'owner'
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证只有一个拥有者
        owner_count = ProjectMember.objects.filter(project=self.project, role='owner').count()
        self.assertEqual(owner_count, 1)

        # 验证最新设置的成员是拥有者
        member_role = ProjectMember.objects.get(project=self.project, user=self.member)
        self.assertEqual(member_role.role, 'owner')

        # 验证其他人都是管理员
        admin_role = ProjectMember.objects.get(project=self.project, user=self.admin)
        owner_role = ProjectMember.objects.get(project=self.project, user=self.owner)
        self.assertEqual(admin_role.role, 'admin')
        self.assertEqual(owner_role.role, 'admin')
