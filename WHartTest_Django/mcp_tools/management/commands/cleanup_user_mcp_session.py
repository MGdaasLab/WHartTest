"""
Django管理命令：清理特定用户的MCP会话
用于手动清理特定用户项目的MCP会话，包括浏览器窗口
"""
import asyncio
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from projects.models import Project
from mcp_tools.persistent_client import mcp_session_manager


class Command(BaseCommand):
    help = '清理特定用户项目的MCP会话'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='用户ID',
        )
        parser.add_argument(
            '--project-id',
            type=int,
            help='项目ID',
        )
        parser.add_argument(
            '--list-sessions',
            action='store_true',
            help='列出所有活跃的会话',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制清理，不询问确认',
        )

    def handle(self, *args, **options):
        """执行清理命令"""
        
        if options.get('list_sessions'):
            self._list_sessions()
            return
        
        user_id = options.get('user_id')
        project_id = options.get('project_id')
        force = options.get('force', False)
        
        if not user_id or not project_id:
            self.stdout.write(
                self.style.ERROR('请提供 --user-id 和 --project-id 参数')
            )
            return
        
        # 验证用户和项目存在
        try:
            user = User.objects.get(id=user_id)
            project = Project.objects.get(id=project_id)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'用户 ID {user_id} 不存在')
            )
            return
        except Project.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'项目 ID {project_id} 不存在')
            )
            return
        
        if not force:
            confirm = input(
                f"确定要清理用户 '{user.username}' 在项目 '{project.name}' 的MCP会话吗？"
                f"这将关闭该用户在此项目中的所有浏览器窗口。(y/N): "
            )
            if confirm.lower() not in ['y', 'yes']:
                self.stdout.write(self.style.WARNING('操作已取消'))
                return
        
        self.stdout.write(f'开始清理用户 {user.username} 在项目 {project.name} 的MCP会话...')
        
        # 运行异步清理
        asyncio.run(self._async_cleanup_user_session(user_id, project_id))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'用户 {user.username} 在项目 {project.name} 的MCP会话已清理完成'
            )
        )
    
    def _list_sessions(self):
        """列出所有活跃的会话"""
        self.stdout.write('活跃的MCP会话:')
        self.stdout.write('=' * 50)
        
        if not mcp_session_manager.session_contexts:
            self.stdout.write('没有活跃的会话')
            return
        
        for session_key, context in mcp_session_manager.session_contexts.items():
            user_id, project_id = session_key.split('_', 1)
            
            try:
                user = User.objects.get(id=user_id)
                project = Project.objects.get(id=project_id)
                
                self.stdout.write(
                    f"会话: {session_key}\n"
                    f"  用户: {user.username} (ID: {user_id})\n"
                    f"  项目: {project.name} (ID: {project_id})\n"
                    f"  最后使用: {context.get('last_used', 'Unknown')}\n"
                )
            except (User.DoesNotExist, Project.DoesNotExist):
                self.stdout.write(
                    f"会话: {session_key} (用户或项目已删除)\n"
                )
    
    async def _async_cleanup_user_session(self, user_id: int, project_id: int):
        """异步清理用户会话"""
        await mcp_session_manager.cleanup_user_session(str(user_id), str(project_id))
