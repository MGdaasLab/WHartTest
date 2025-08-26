from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework import status
from projects.models import Project, ProjectMember


class ProjectCreationTestCase(TestCase):
    """测试项目创建时自动添加平台管理员的功能"""

    def setUp(self):
        """设置测试数据"""
        self.client = APIClient()
        
        # 创建普通用户
        self.normal_user = User.objects.create_user(
            username='normal_user',
            email='normal@example.com',
            password='testpass123'
        )
        
        # 为普通用户添加创建项目的权限
        content_type = ContentType.objects.get_for_model(Project)
        add_project_permission = Permission.objects.get(
            codename='add_project',
            content_type=content_type
        )
        self.normal_user.user_permissions.add(add_project_permission)
        
        # 创建平台管理员用户
        self.admin_user1 = User.objects.create_user(
            username='admin_user1',
            email='admin1@example.com',
            password='testpass123',
            is_superuser=True,
            is_active=True
        )
        
        self.admin_user2 = User.objects.create_user(
            username='admin_user2',
            email='admin2@example.com',
            password='testpass123',
            is_superuser=True,
            is_active=True
        )
        
        # 创建一个非活跃的平台管理员（不应该被添加）
        self.inactive_admin = User.objects.create_user(
            username='inactive_admin',
            email='inactive@example.com',
            password='testpass123',
            is_superuser=True,
            is_active=False
        )

    def test_normal_user_creates_project(self):
        """测试普通用户创建项目时，所有活跃的平台管理员都被添加为项目管理者"""
        # 使用普通用户身份登录
        self.client.force_authenticate(user=self.normal_user)
        
        # 创建项目
        project_data = {
            'name': '测试项目',
            'description': '这是一个测试项目'
        }
        
        response = self.client.post('/api/projects/', project_data)
        
        # 验证项目创建成功
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 获取创建的项目
        project = Project.objects.get(name='测试项目')
        
        # 验证项目创建者
        self.assertEqual(project.creator, self.normal_user)
        
        # 验证项目成员
        members = ProjectMember.objects.filter(project=project)
        
        # 应该有3个成员：创建者(owner) + 2个平台管理员(admin)
        self.assertEqual(members.count(), 3)
        
        # 验证创建者是项目拥有者
        creator_member = members.get(user=self.normal_user)
        self.assertEqual(creator_member.role, 'owner')
        
        # 验证平台管理员被添加为项目管理者
        admin1_member = members.get(user=self.admin_user1)
        self.assertEqual(admin1_member.role, 'admin')
        
        admin2_member = members.get(user=self.admin_user2)
        self.assertEqual(admin2_member.role, 'admin')
        
        # 验证非活跃的管理员没有被添加
        inactive_members = members.filter(user=self.inactive_admin)
        self.assertEqual(inactive_members.count(), 0)

    def test_admin_user_creates_project(self):
        """测试平台管理员创建项目时，不会重复添加自己"""
        # 使用平台管理员身份登录
        self.client.force_authenticate(user=self.admin_user1)
        
        # 创建项目
        project_data = {
            'name': '管理员测试项目',
            'description': '这是管理员创建的测试项目'
        }
        
        response = self.client.post('/api/projects/', project_data)
        
        # 验证项目创建成功
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 获取创建的项目
        project = Project.objects.get(name='管理员测试项目')
        
        # 验证项目创建者
        self.assertEqual(project.creator, self.admin_user1)
        
        # 验证项目成员
        members = ProjectMember.objects.filter(project=project)
        
        # 应该有2个成员：创建者(owner) + 1个其他平台管理员(admin)
        self.assertEqual(members.count(), 2)
        
        # 验证创建者是项目拥有者（不会重复添加）
        creator_members = members.filter(user=self.admin_user1)
        self.assertEqual(creator_members.count(), 1)
        self.assertEqual(creator_members.first().role, 'owner')
        
        # 验证其他平台管理员被添加为项目管理者
        admin2_member = members.get(user=self.admin_user2)
        self.assertEqual(admin2_member.role, 'admin')

    def test_project_creation_with_no_admins(self):
        """测试当没有其他平台管理员时的项目创建"""
        # 删除所有平台管理员
        User.objects.filter(is_superuser=True).delete()
        
        # 使用普通用户身份登录
        self.client.force_authenticate(user=self.normal_user)
        
        # 创建项目
        project_data = {
            'name': '无管理员测试项目',
            'description': '没有平台管理员的测试项目'
        }
        
        response = self.client.post('/api/projects/', project_data)
        
        # 验证项目创建成功
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 获取创建的项目
        project = Project.objects.get(name='无管理员测试项目')
        
        # 验证项目成员
        members = ProjectMember.objects.filter(project=project)
        
        # 应该只有1个成员：创建者(owner)
        self.assertEqual(members.count(), 1)
        
        # 验证创建者是项目拥有者
        creator_member = members.get(user=self.normal_user)
        self.assertEqual(creator_member.role, 'owner')