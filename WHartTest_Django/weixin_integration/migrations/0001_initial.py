from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import weixin_integration.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("langgraph_integration", "0022_alter_llmconfig_provider"),
        ("projects", "0004_remove_project_password_remove_project_system_url_and_more"),
        ("prompts", "0010_alter_userprompt_prompt_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="WeixinBotAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("raw_account_id", models.CharField(max_length=255, unique=True)),
                ("account_id", models.CharField(db_index=True, max_length=255, unique=True)),
                ("token", models.CharField(max_length=1024)),
                ("base_url", models.URLField(default="https://ilinkai.weixin.qq.com")),
                ("scanned_user_id", models.CharField(blank=True, default="", max_length=255)),
                ("sync_cursor", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("worker_running", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("connected", "已连接"), ("running", "运行中"), ("stopped", "已停止"), ("error", "异常")], default="connected", max_length=20)),
                ("last_error", models.TextField(blank=True, default="")),
                ("last_inbound_at", models.DateTimeField(blank=True, null=True)),
                ("last_outbound_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weixin_bot_accounts", to="projects.project")),
                ("prompt", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="weixin_bot_accounts", to="prompts.userprompt")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weixin_bot_accounts", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "微信机器人账号",
                "verbose_name_plural": "微信机器人账号",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="WeixinLoginSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(db_index=True, max_length=100, unique=True)),
                ("qrcode", models.TextField(blank=True, default="")),
                ("qr_data_url", models.TextField(blank=True, default="")),
                ("base_url", models.URLField(default="https://ilinkai.weixin.qq.com")),
                ("status", models.CharField(choices=[("wait", "等待扫码"), ("scaned", "已扫码"), ("confirmed", "已确认"), ("expired", "已过期"), ("failed", "失败")], default="wait", max_length=20)),
                ("raw_account_id", models.CharField(blank=True, db_index=True, default="", max_length=255)),
                ("account_id", models.CharField(blank=True, db_index=True, default="", max_length=255)),
                ("bot_token", models.CharField(blank=True, default="", max_length=1024)),
                ("scanned_user_id", models.CharField(blank=True, default="", max_length=255)),
                ("error_message", models.TextField(blank=True, default="")),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weixin_login_sessions", to="projects.project")),
                ("prompt", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="weixin_login_sessions", to="prompts.userprompt")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weixin_login_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "微信登录会话",
                "verbose_name_plural": "微信登录会话",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="WeixinConversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("peer_user_id", models.CharField(db_index=True, max_length=255)),
                ("context_token", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversations", to="weixin_integration.weixinbotaccount")),
                ("chat_session", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="weixin_conversation", to="langgraph_integration.chatsession")),
            ],
            options={
                "verbose_name": "微信会话",
                "verbose_name_plural": "微信会话",
                "ordering": ["-updated_at"],
                "unique_together": {("account", "peer_user_id")},
            },
        ),
        migrations.CreateModel(
            name="WeixinConversationMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("user", "用户"), ("assistant", "助手"), ("system", "系统")], max_length=20)),
                ("content", models.TextField()),
                ("external_message_id", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="weixin_integration.weixinconversation")),
            ],
            options={
                "verbose_name": "微信会话消息",
                "verbose_name_plural": "微信会话消息",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="weixinconversationmessage",
            constraint=models.UniqueConstraint(condition=models.Q(("external_message_id__gt", "")), fields=("conversation", "external_message_id"), name="unique_weixin_conversation_external_message"),
        ),
    ]
