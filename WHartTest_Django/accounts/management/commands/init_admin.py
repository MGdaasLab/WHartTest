# 导入 Django 管理命令基类。
from django.core.management.base import BaseCommand

# 导入用户模型工厂，兼容自定义 User 模型。
from django.contrib.auth import get_user_model

# 导入环境变量读取模块。
import os

# 获取当前项目实际使用的用户模型。
User = get_user_model()


class Command(BaseCommand):
    # 命令说明：初始化管理员、默认 API Key、MCP 配置与演示数据。
    help = '创建默认管理员账号和默认API Key'

    def handle(self, *args, **options):
        # 读取管理员初始化参数，未配置时使用开发默认值。
        admin_username = os.environ.get('DJANGO_ADMIN_USERNAME', 'admin')
        admin_email = os.environ.get('DJANGO_ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.environ.get('DJANGO_ADMIN_PASSWORD', 'admin123456')

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
                )
            )
        
        # 无论管理员是新建还是已存在，都执行提示词初始化补齐逻辑。
        self._initialize_admin_prompts(admin_user, admin_created)
        
        # 创建默认API Key（用于MCP服务）
        from api_keys.models import APIKey
        
        default_api_key_value = "wharttest-default-mcp-key-2025"
        
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
        
        # 创建默认远程MCP配置（自动配置MCP工具）
        from mcp_tools.models import RemoteMCPConfig
        
        mcp_configs = [
            {
                'name': 'WHartTest-Tools',
                'url': 'http://mcp:8006/mcp',
                'transport': 'streamable-http',
                'description': '系统自动生成的WHartTest MCP工具配置，提供测试用例管理功能'
            },
            {
                'name': 'Playwright-MCP',
                'url': 'http://playwright-mcp:8931/mcp',
                'transport': 'streamable-http',
                'description': '系统自动生成的Playwright浏览器自动化MCP配置，提供网页操作、截图和自动化测试功能'
            }
        ]
        
        created_configs = []
        # 逐项检查并创建默认 MCP 配置，保证重复执行时不会覆盖用户已有配置。
        for config in mcp_configs:
            existing_config = RemoteMCPConfig.objects.filter(
                name=config['name']
            ).first()
            
            if existing_config:
                self.stdout.write(
                    self.style.WARNING(f'MCP配置 "{config["name"]}" 已存在，跳过创建')
                )
            else:
                RemoteMCPConfig.objects.create(
                    name=config['name'],
                    url=config['url'],
                    transport=config['transport'],
                    is_active=True
                )
                created_configs.append(config['name'])
                self.stdout.write(
                    self.style.SUCCESS(f'  ✅ 创建MCP配置: {config["name"]} ({config["url"]})')
                )
        
        # 仅在本次确实创建了配置时输出汇总信息，避免日志噪声。
        if created_configs:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n成功创建 {len(created_configs)} 个默认MCP配置\n'
                    f'  用户可在【系统管理】>【MCP配置】中查看和管理'
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
                    "这是系统自动生成的演示项目，帮助您快速了解WHartTest的功能。\n\n"
                    "此项目包含：\n"
                    "• 示例测试用例模块和用例\n"
                    "• MCP工具集成示例\n"
                    "• 测试执行演示\n\n"
                    "您可以：\n"
                    "1. 查看和编辑示例用例\n"
                    "2. 尝试执行测试用例\n"
                    "3. 学习如何使用MCP工具\n"
                    "4. 在此基础上创建自己的项目\n\n"
                    "提示：您可以随时删除此演示项目。"
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
        
        # 初始化知识库全局配置（仅在未被手工配置时注入默认值）。
        self._initialize_knowledge_global_config(admin_user)
        
        self.stdout.write(
            self.style.SUCCESS(
                '\n========================================\n'
                '🎉 系统初始化完成！\n'
                '========================================\n'
                f'管理员账号: {admin_username}\n'
                f'初始密码: {admin_password}\n'
                f'API Key: {default_api_key_value}\n'
                f'演示项目: {demo_project_name}\n'
                '========================================\n'
                '⚠️  生产环境请及时修改密码和API Key\n'
                '========================================\n'
            )
        )
    
    def _initialize_admin_prompts(self, admin_user, admin_created):
        """为管理员初始化默认提示词"""
        try:
            from prompts.services import initialize_user_prompts
            
            # 条件：管理员是新建用户；动作：仅提示结果；结果：避免和 post_save 信号重复写入。
            if admin_created:
                # 新创建的用户，信号已经自动初始化了提示词
                self.stdout.write(
                    self.style.SUCCESS('✅ 管理员提示词已通过信号自动初始化')
                )
            else:
                # 条件：管理员为已存在用户；动作：补齐缺失提示词；结果：历史环境升级后也能拿到完整默认提示词。
                result = initialize_user_prompts(admin_user, force_update=False)
                
                if result['summary']['created_count'] > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ 管理员提示词初始化完成:\n'
                            f'  新建: {result["summary"]["created_count"]} 个\n'
                            f'  跳过: {result["summary"]["skipped_count"]} 个'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING('管理员提示词已存在，跳过初始化')
                    )
                    
        except Exception as e:
            # 提示词初始化失败不影响主流程，记录错误便于后续人工补偿。
            self.stdout.write(
                self.style.ERROR(f'❌ 初始化管理员提示词失败: {e}')
            )
    
    def _initialize_knowledge_global_config(self, admin_user):
        """初始化知识库全局配置（使用Xinference默认配置）"""
        try:
            from knowledge.models import KnowledgeGlobalConfig
            
            # 获取或创建配置（单例模式）
            config = KnowledgeGlobalConfig.get_config()
            
            # 条件：配置尚未被用户修改；动作：写入默认 Xinference 参数；结果：知识库功能可直接启动。
            if config.updated_by is None:
                xinference_url = os.environ.get('XINFERENCE_API_BASE_URL', 'http://xinference:9997')
                # Embedding 配置
                config.embedding_service = 'xinference'
                config.api_base_url = xinference_url
                config.api_key = ''
                config.model_name = os.environ.get('XINFERENCE_EMBEDDING_MODEL', 'qwen3-vl-emb-2b')
                # Reranker 配置（同一 Xinference 实例）
                config.reranker_service = 'xinference'
                config.reranker_api_url = xinference_url
                config.reranker_api_key = ''
                config.reranker_model_name = os.environ.get('XINFERENCE_RERANKER_MODEL', 'Qwen3-VL-Reranker-2B')
                config.chunk_size = 1000
                config.chunk_overlap = 200
                config.updated_by = admin_user
                config.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n成功初始化知识库全局配置:\n'
                        f'  嵌入服务: Xinference\n'
                        f'  API地址: {config.api_base_url}\n'
                        f'  嵌入模型: {config.model_name}\n'
                        f'  Reranker: {config.reranker_model_name}\n'
                        f'  分块大小: {config.chunk_size}\n'
                        f'  分块重叠: {config.chunk_overlap}\n'
                        f'  ℹ️  可在【知识库管理】>【知识库配置】中修改'
                    )
                )
            else:
                # 条件：已有人工配置；动作：跳过默认覆盖；结果：保留用户现有生产参数。
                self.stdout.write(
                    self.style.WARNING('知识库全局配置已存在，跳过初始化')
                )
                
        except Exception as e:
            # 配置初始化失败不阻断其他初始化项，输出错误供运维排查。
            self.stdout.write(
                self.style.ERROR(f'❌ 初始化知识库全局配置失败: {e}')
            )
