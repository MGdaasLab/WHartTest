from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from prompts.models import UserPrompt, PromptType

class Command(BaseCommand):
    help = 'Initializes the database with default prompts for the system.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=int,
            help='User ID to assign the prompts to (default: first superuser)',
        )

    def handle(self, *args, **kwargs):
        self.stdout.write('Initializing default prompts...')

        # 获取用户
        user_id = kwargs.get('user')
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User with ID {user_id} not found'))
                return
        else:
            # 默认使用第一个超级用户
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(self.style.ERROR('No superuser found. Please create a superuser first or specify a user ID.'))
                return

        self.stdout.write(f'Using user: {user.username} (ID: {user.id})')

        # 提示词内容
        prompts_to_create = [
            {
                "name": "测试用例执行提示词",
                "prompt_type": PromptType.TEST_CASE_EXECUTION,
                "content": """# 角色
你是一个专业的软件测试执行引擎。

# 任务
根据下面提供的测试用例信息,使用你可用的工具(特别是Playwright浏览器工具)来执行UI自动化测试。

# 测试用例信息
- **用例ID**: {testcase_id}
- **用例名称**: {testcase_name}
- **前置条件**: {precondition}

# 执行步骤
{steps}

# 输出格式
在所有步骤执行完毕后,你**必须**返回一个JSON对象,格式如下:
```json
{{
  "testcase_id": {testcase_id},
  "status": "pass" | "fail",
  "summary": "对执行过程的简短总结。",
  "steps": [
    {{
      "step_number": 1,
      "description": "步骤的描述",
      "status": "pass" | "fail",
      "screenshot": "path/to/screenshot.png" | null,
      "error": "如果失败,记录错误信息" | null
    }},
    ...
  ]
}}
```""",
                "description": "用于驱动测试用例自动执行的系统提示词",
                "is_active": True,
            }
        ]

        for prompt_data in prompts_to_create:
            # 使用 get_or_create 来避免重复创建
            # 注意：程序调用类型的提示词每个用户只能有一个
            prompt, created = UserPrompt.objects.get_or_create(
                user=user,
                prompt_type=prompt_data["prompt_type"],
                defaults={
                    'name': prompt_data["name"],
                    'content': prompt_data["content"].strip(),
                    'description': prompt_data.get("description", ""),
                    'is_active': prompt_data.get("is_active", True),
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created prompt: "{prompt.name}" for user {user.username}'))
            else:
                # 如果已存在,更新内容
                prompt.name = prompt_data["name"]
                prompt.content = prompt_data["content"].strip()
                prompt.description = prompt_data.get("description", "")
                prompt.is_active = prompt_data.get("is_active", True)
                prompt.save()
                self.stdout.write(self.style.WARNING(f'Prompt "{prompt.name}" already exists for user {user.username}. Updated it.'))

        self.stdout.write(self.style.SUCCESS('Default prompts initialization complete.'))
