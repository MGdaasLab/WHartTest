# 导入 Django 管理命令基类。
from django.core.management.base import BaseCommand

# 导入用户模型工厂，兼容自定义 User 模型。
from django.contrib.auth import get_user_model

# 导入环境变量读取模块。
import os

# 导入加密安全随机数模块（用于生成随机初始密码与 API Key）。
import secrets

# 获取当前项目实际使用的用户模型。
User = get_user_model()


class Command(BaseCommand):
    # 命令说明：初始化管理员、默认 API Key 与演示数据。
    help = '创建默认管理员账号和默认API Key'

    def handle(self, *args, **options):
        # 读取管理员初始化参数。安全：不再回退到源码公开过的固定口令
        # （admin123456）——未配置 DJANGO_ADMIN_PASSWORD 时改为随机生成，
        # 仅在 stdout 打印一次，提示部署方立即修改。
        admin_username = os.environ.get('DJANGO_ADMIN_USERNAME', 'admin')
        admin_email = os.environ.get('DJANGO_ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.environ.get('DJANGO_ADMIN_PASSWORD', '')
        password_generated = False
        if not admin_password:
            admin_password = 'Whart-' + secrets.token_urlsafe(18)
            password_generated = True

        # 检查管理员是否已存在
        admin_user = User.objects.filter(username=admin_username).first()
        admin_created = False
        
        # 条件：管理员账号已存在；动作：跳过创建；结果：保证命令可重复执行且幂等。
        if admin_user:
            self.stdout.write(
                self.style.WARNING(f'管理员账号 "{admin_username}" 已存在，跳过创建')
            )
        else:
            # 条件：管理员不存在；动作：创建超级用户；结果：完成系统首个管理账号初始化。
            admin_user = User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password
            )
            admin_created = True
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'成功创建管理员账号:\n'
                    f'  用户名: {admin_username}\n'
                    f'  邮箱: {admin_email}\n'
                    f'  密码: {admin_password}'
                    + (
                        '\n  ⚠️ 该密码为随机生成的初始密码，请立即登录修改'
                        if password_generated else ''
                    )
                )
            )

        # 创建默认API Key（用于MCP服务）
        from api_keys.models import APIKey

        # 安全：固定演示密钥（wharttest-default-mcp-key-2025）已随源码公开，
        # 任何拿到源码的人都能用它通过 MCP 认证。改为随机生成，仅在 stdout 展示一次。
        default_api_key_value = "whart-" + secrets.token_urlsafe(32)
        
        # 检查是否已存在默认Key
        default_key = APIKey.objects.filter(
            user=admin_user,
            name="Default MCP Key (Auto-generated)"
        ).first()
        
        # 条件：默认 Key 已存在；动作：跳过；结果：避免重复生成固定演示密钥。
        if default_key:
            self.stdout.write(
                self.style.WARNING('默认API Key已存在，跳过创建')
            )
        else:
            # 条件：默认 Key 不存在；动作：创建预置 MCP Key；结果：开箱即用联调 MCP 服务。
            APIKey.objects.create(
                user=admin_user,
                name="Default MCP Key (Auto-generated)",
                key=default_api_key_value,
                is_active=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'成功创建默认API Key:\n'
                    f'  名称: Default MCP Key (Auto-generated)\n'
                    f'  密钥: {default_api_key_value}\n'
                    f'  ⚠️  生产环境请删除此密钥并创建新的安全密钥'
                )
            )
        
        # 创建演示项目（提供开箱即用的示例）
        from projects.models import Project, ProjectMember

        demo_project_name = "演示项目 (Demo Project)"
        demo_project = Project.objects.filter(name=demo_project_name).first()
        
        # 条件：演示项目已存在；动作：跳过；结果：保持命令幂等，不重复制造演示数据。
        if demo_project:
            self.stdout.write(
                self.style.WARNING(f'演示项目 "{demo_project_name}" 已存在，跳过创建')
            )
        else:
            # 条件：演示项目不存在；动作：创建项目+Owner 成员；结果：首次部署后可直接体验业务流程。
            demo_project = Project.objects.create(
                name=demo_project_name,
                description=(
                    "WHartTest"
                ),
                creator=admin_user
            )
            
            # 添加管理员为项目拥有者
            ProjectMember.objects.create(
                project=demo_project,
                user=admin_user,
                role='owner'
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n成功创建演示项目:\n'
                    f'  项目名称: {demo_project_name}\n'
                    f'  项目ID: {demo_project.id}\n'
                    f'  创建人: {admin_username}\n'
                    f'  说明: 包含示例用例和模块的演示项目\n'
                    f'  ℹ️  登录后可在【项目管理】中查看'
                )
            )

        # 只汇总「本次真正写入数据库」的凭据；已存在时打印提示而不是新生成的随机值，
        # 否则容器重启等幂等重跑场景下，运维照着日志配置必然鉴权失败。
        summary_lines = [f'管理员账号: {admin_username}']
        if admin_created and password_generated:
            summary_lines.append(f'初始密码: {admin_password}')
        elif admin_created:
            summary_lines.append('初始密码: （使用 DJANGO_ADMIN_PASSWORD 配置值）')
        else:
            summary_lines.append('管理员账号已存在，本次未新建（密码未变更）')
        if default_key:
            summary_lines.append('API Key: 已存在，本次未新建（请到后台查看或重新创建）')
        else:
            summary_lines.append(f'API Key: {default_api_key_value}')
        summary_lines.append(f'演示项目: {demo_project_name}')

        self.stdout.write(
            self.style.SUCCESS(
                '\n========================================\n'
                '系统初始化完成\n'
                '========================================\n'
                + '\n'.join(summary_lines) + '\n'
                '========================================\n'
                '生产环境请及时修改密码和 API Key\n'
                '========================================\n'
            )
        )
