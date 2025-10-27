from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class Command(BaseCommand):
    help = '创建默认管理员账号'

    def handle(self, *args, **options):
        # 从环境变量获取管理员信息
        admin_username = os.environ.get('DJANGO_ADMIN_USERNAME', 'admin')
        admin_email = os.environ.get('DJANGO_ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.environ.get('DJANGO_ADMIN_PASSWORD', 'admin123456')

        # 检查管理员是否已存在
        if User.objects.filter(username=admin_username).exists():
            self.stdout.write(
                self.style.WARNING(f'管理员账号 "{admin_username}" 已存在，跳过创建')
            )
            return

        # 创建管理员账号
        User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'成功创建管理员账号:\n'
                f'  用户名: {admin_username}\n'
                f'  邮箱: {admin_email}\n'
                f'  密码: {admin_password}'
            )
        )