from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer as BaseTokenObtainPairSerializer,
)

# 权限名称翻译映射
# 您可以根据实际的权限名称进行扩展
PERMISSION_NAME_TRANSLATIONS = {
    # 系统管理权限
    "Can add log entry": "添加日志条目",
    "Can change log entry": "修改日志条目",
    "Can delete log entry": "删除日志条目",
    "Can view log entry": "查看日志条目",
    # 用户认证权限
    "Can add group": "添加用户组",
    "Can add permission": "添加权限",
    "Can add user": "添加用户",
    "Can change group": "修改用户组",
    "Can change permission": "修改权限",
    "Can change user": "修改用户",
    "Can delete group": "删除用户组",
    "Can delete permission": "删除权限",
    "Can delete user": "删除用户",
    "Can view group": "查看用户组",
    "Can view permission": "查看权限",
    "Can view user": "查看用户",
    # 令牌权限
    "Can add Token": "添加令牌",
    "Can change Token": "修改令牌",
    "Can delete Token": "删除令牌",
    "Can view Token": "查看令牌",
    # 内容类型权限
    "Can add content type": "添加内容类型",
    "Can change content type": "修改内容类型",
    "Can delete content type": "删除内容类型",
    "Can view content type": "查看内容类型",
    # 会话权限
    "Can add session": "添加会话",
    "Can change session": "修改会话",
    "Can delete session": "删除会话",
    "Can view session": "查看会话",
    # 项目管理模块权限
    "Can add 项目": "添加项目",
    "Can change 项目": "修改项目",
    "Can delete 项目": "删除项目",
    "Can view 项目": "查看项目",
    "Can add 项目成员": "添加项目成员",
    "Can change 项目成员": "修改项目成员",
    "Can delete 项目成员": "删除项目成员",
    "Can view 项目成员": "查看项目成员",
    # 用例管理权限
    "Can add 测试用例": "添加测试用例",
    "Can change 测试用例": "修改测试用例",
    "Can delete 测试用例": "删除测试用例",
    "Can view 测试用例": "查看测试用例",
    "Can add 测试用例步骤": "添加测试用例步骤",
    "Can change 测试用例步骤": "修改测试用例步骤",
    "Can delete 测试用例步骤": "删除测试用例步骤",
    "Can view 测试用例步骤": "查看测试用例步骤",
    # LLM配置权限
    "Can add LLM Configuration": "添加LLM配置",
    "Can change LLM Configuration": "修改LLM配置",
    "Can delete LLM Configuration": "删除LLM配置",
    "Can view LLM Configuration": "查看LLM配置",
    # 对话会话权限
    "Can add 对话会话": "添加对话会话",
    "Can change 对话会话": "修改对话会话",
    "Can delete 对话会话": "删除对话会话",
    "Can view 对话会话": "查看对话会话",
    # 对话消息权限
    "Can add 对话消息": "添加对话消息",
    "Can change 对话消息": "修改对话消息",
    "Can delete 对话消息": "删除对话消息",
    "Can view 对话消息": "查看对话消息",
    # API密钥权限
    "Can add API Key": "添加API密钥",
    "Can change API Key": "修改API密钥",
    "Can delete API Key": "删除API密钥",
    "Can view API Key": "查看API密钥",
    # 知识库权限
    "Can add 知识库": "添加知识库",
    "Can change 知识库": "修改知识库",
    "Can delete 知识库": "删除知识库",
    "Can view 知识库": "查看知识库",
    "Can add 文档": "添加文档",
    "Can change 文档": "修改文档",
    "Can delete 文档": "删除文档",
    "Can view 文档": "查看文档",
    "Can add 知识库文档": "添加知识库文档",
    "Can change 知识库文档": "修改知识库文档",
    "Can delete 知识库文档": "删除知识库文档",
    "Can view 知识库文档": "查看知识库文档",
    # 需求管理权限
    "Can add 需求文档": "添加需求文档",
    "Can change 需求文档": "修改需求文档",
    "Can delete 需求文档": "删除需求文档",
    "Can view 需求文档": "查看需求文档",
    "Can add 需求模块": "添加需求模块",
    "Can change 需求模块": "修改需求模块",
    "Can delete 需求模块": "删除需求模块",
    "Can view 需求模块": "查看需求模块",
    "Can add 评审报告": "添加评审报告",
    "Can change 评审报告": "修改评审报告",
    "Can delete 评审报告": "删除评审报告",
    "Can view 评审报告": "查看评审报告",
    "Can add 评审问题": "添加评审问题",
    "Can change 评审问题": "修改评审问题",
    "Can delete 评审问题": "删除评审问题",
    "Can view 评审问题": "查看评审问题",
    "Can add 模块评审结果": "添加模块评审结果",
    "Can change 模块评审结果": "修改模块评审结果",
    "Can delete 模块评审结果": "删除模块评审结果",
    "Can view 模块评审结果": "查看模块评审结果",
    # 提示词管理权限
    "Can add 用户提示词": "添加用户提示词",
    "Can change 用户提示词": "修改用户提示词",
    "Can delete 用户提示词": "删除用户提示词",
    "Can view 用户提示词": "查看用户提示词",
    # MCP工具权限
    "Can add 远程 MCP 配置": "添加远程MCP配置",
    "Can change 远程 MCP 配置": "修改远程MCP配置",
    "Can delete 远程 MCP 配置": "删除远程MCP配置",
    "Can view 远程 MCP 配置": "查看远程MCP配置",
    # 知识库扩展权限
    "Can add 文档分块": "添加文档分块",
    "Can change 文档分块": "修改文档分块",
    "Can delete 文档分块": "删除文档分块",
    "Can view 文档分块": "查看文档分块",
    "Can add 查询日志": "添加查询日志",
    "Can change 查询日志": "修改查询日志",
    "Can delete 查询日志": "删除查询日志",
    "Can view 查询日志": "查看查询日志",
    # LLM配置相关权限
    "Can add LLM配置": "添加LLM配置",
    "Can change LLM配置": "修改LLM配置",
    "Can delete LLM配置": "删除LLM配置",
    "Can view LLM配置": "查看LLM配置",
    "Can add LLM模型": "添加LLM模型",
    "Can change LLM模型": "修改LLM模型",
    "Can delete LLM模型": "删除LLM模型",
    "Can view LLM模型": "查看LLM模型",
    # LLM服务相关权限
    "Can add LLM服务": "添加LLM服务",
    "Can change LLM服务": "修改LLM服务",
    "Can delete LLM服务": "删除LLM服务",
    "Can view LLM服务": "查看LLM服务",
    # LLM提供商相关权限
    "Can add LLM提供商": "添加LLM提供商",
    "Can change LLM提供商": "修改LLM提供商",
    "Can delete LLM提供商": "删除LLM提供商",
    "Can view LLM提供商": "查看LLM提供商",
    # API密钥/秘钥相关权限
    "Can add 密钥": "添加密钥",
    "Can change 密钥": "修改密钥",
    "Can delete 密钥": "删除密钥",
    "Can view 密钥": "查看密钥",
    "Can add 秘钥": "添加秘钥",
    "Can change 秘钥": "修改秘钥",
    "Can delete 秘钥": "删除秘钥",
    "Can view 秘钥": "查看秘钥",
    # 用例管理相关权限
    "Can add 用例": "添加用例",
    "Can change 用例": "修改用例",
    "Can delete 用例": "删除用例",
    "Can view 用例": "查看用例",
    "Can add 用例步骤": "添加用例步骤",
    "Can change 用例步骤": "修改用例步骤",
    "Can delete 用例步骤": "删除用例步骤",
    "Can view 用例步骤": "查看用例步骤",
    "Can add 用例执行记录": "添加用例执行记录",
    "Can change 用例执行记录": "修改用例执行记录",
    "Can delete 用例执行记录": "删除用例执行记录",
    "Can view 用例执行记录": "查看用例执行记录",
    "Can add 用例模块": "添加用例模块",
    "Can change 用例模块": "修改用例模块",
    "Can delete 用例模块": "删除用例模块",
    "Can view 用例模块": "查看用例模块",
    "Can add 用例截屏": "添加用例截屏",
    "Can change 用例截屏": "修改用例截屏",
    "Can delete 用例截屏": "删除用例截屏",
    "Can view 用例截屏": "查看用例截屏",
    "Can add 测试用例截屏": "添加测试用例截屏",
    "Can change 测试用例截屏": "修改测试用例截屏",
    "Can delete 测试用例截屏": "删除测试用例截屏",
    "Can view 测试用例截屏": "查看测试用例截屏",
    # 消息相关权限
    "Can add 消息": "添加消息",
    "Can change 消息": "修改消息",
    "Can delete 消息": "删除消息",
    "Can view 消息": "查看消息",
    # MCP服务器配置权限
    "Can add MCP服务器配置": "添加MCP服务器配置",
    "Can change MCP服务器配置": "修改MCP服务器配置",
    "Can delete MCP服务器配置": "删除MCP服务器配置",
    "Can view MCP服务器配置": "查看MCP服务器配置",
    # API密钥相关权限
    "Can add API密钥": "添加API密钥",
    "Can change API密钥": "修改API密钥",
    "Can delete API密钥": "删除API密钥",
    "Can view API密钥": "查看API密钥",
    # 对话相关权限
    "Can add 对话": "添加对话",
    "Can change 对话": "修改对话",
    "Can delete 对话": "删除对话",
    "Can view 对话": "查看对话",
    # 向量数据库索引相关权限
    "Can add 向量数据库索引": "添加向量数据库索引",
    "Can change 向量数据库索引": "修改向量数据库索引",
    "Can delete 向量数据库索引": "删除向量数据库索引",
    "Can view 向量数据库索引": "查看向量数据库索引",
}



class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "is_staff",
            "is_active",
        )  # 添加管理员相关字段

    def create(self, validated_data):
        # 信号处理器会自动处理管理员权限分配，这里只需要正常创建用户
        # 统一走 create_user，确保密码会被哈希而不是明文入库。
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            is_staff=validated_data.get("is_staff", False),
            is_active=validated_data.get("is_active", True),
        )

        return user


class UserDetailSerializer(serializers.ModelSerializer):
    """
    用于展示用户详情（只读，不包含密码）。
    """

    groups = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_active",
            "groups",
        )  # 根据需要添加更多字段
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    用于管理员更新用户信息。
    密码字段非必填，若传入则会单独处理。
    """

    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    groups = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), many=True, required=False
    )
    # 可按需补充管理员可更新字段
    # 例如：first_name、last_name、is_staff、is_active

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_active",
            "password",
            "groups",
        )
        extra_kwargs = {
            "password": {
                "write_only": True,
                "required": False,
                "style": {"input_type": "password"},
            },
            "username": {"required": False},
            "email": {"required": False},
            # groups 字段保持 PrimaryKeyRelatedField 默认行为
        }

    def update(self, instance, validated_data):
        # 信号处理器会自动处理管理员权限分配，这里只需要正常更新用户



        # 条件：请求携带新密码；动作：调用 set_password；结果：确保密码按 Django 标准安全存储。
        password = validated_data.pop("password", None)
        if password:
            instance.set_password(password)

        # 条件：请求包含 groups；动作：整体替换用户组；结果：组关系与请求保持一致。
        if "groups" in validated_data:
            instance.groups.set(validated_data.pop("groups"))

        # 其余字段逐项赋值，避免遗漏可编辑基础资料字段。
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()  # 保存时会触发信号处理器

        return instance


class GroupSerializer(serializers.ModelSerializer):
    users = serializers.StringRelatedField(many=True, read_only=True, source="user_set")

    class Meta:
        model = Group
        fields = ("id", "name", "users")


class ContentTypeSerializer(serializers.ModelSerializer):
    """
    内容类型（模型）序列化器
    """

    app_label_cn = serializers.SerializerMethodField()
    app_label_sort = serializers.SerializerMethodField()
    app_label_subcategory = serializers.SerializerMethodField()  # 新增第二层分类
    app_label_subcategory_sort = serializers.SerializerMethodField()  # 第二层排序
    model_cn = serializers.SerializerMethodField()
    model_verbose = serializers.SerializerMethodField()

    class Meta:
        model = ContentType
        fields = (
            "id",
            "app_label",
            "app_label_cn",
            "app_label_subcategory",
            "app_label_subcategory_sort",
            "app_label_sort",
            "model",
            "model_cn",
            "model_verbose",
        )

    def get_app_label_cn(self, obj):
        """
        返回与前端菜单一致的第一层分类。
        """
        app_label = obj.app_label
        model_name = (obj.model or "").lower()

        # 条件：langgraph_integration 下不同模型；动作：拆分到不同一级菜单；结果：前端导航分组更直观。
        if app_label == "langgraph_integration":
            if model_name == "llmconfig":
                return "系统管理"
            if model_name in ["chatsession", "chatmessage"]:
                return "LLM对话"

        # 提示词配置统一归类到 LLM 对话菜单，避免系统管理菜单过载。
        if app_label == "prompts":
            return "LLM对话"

        app_labels = {
            # 前端一级菜单
            "projects": "项目管理",
            "requirements": "需求管理",
            "orchestrator_integration": "智能图表",
            "ui_automation": "UI自动化",
            "task_center": "任务中心",
            "django_celery_beat": "任务中心",
            "testcases": "测试管理",
            "testcase_templates": "测试管理",
            "knowledge": "知识库管理",
            # 系统管理
            "auth": "系统管理",
            "accounts": "系统管理",
            "api_keys": "系统管理",
            "apikey": "系统管理",
            "mcp_tools": "系统管理",
            "skills": "系统管理",
            "llms": "系统管理",
            "llm_config": "系统管理",
            "message": "系统管理",
            "mcpserverconfig": "系统管理",
            # 系统核心应用（内容类型接口已排除 admin/contenttypes/sessions）
            "authtoken": "系统管理",
        }
        return app_labels.get(app_label, "系统管理")

    def get_app_label_subcategory(self, obj):
        """
        返回与前端菜单一致的第二层分类（用于子菜单分组）。
        """
        menu_category = self.get_app_label_cn(obj)
        app_label = obj.app_label
        model_name = (obj.model or "").lower()

        # 条件：一级菜单是测试管理；动作：按模型分流到子菜单；结果：用例/套件/执行历史结构清晰。
        if menu_category == "测试管理":
            if app_label == "testcase_templates":
                return "用例管理"
            if app_label == "testcases":
                if model_name == "testsuite":
                    return "测试套件"
                if model_name in ["testexecution", "testcaseresult", "scriptexecution"]:
                    return "执行历史"
                return "用例管理"
            return None

        # 条件：一级菜单是任务中心；动作：统一归类到任务调度；结果：权限树位置与前端导航一致。
        if menu_category == "任务中心":
            if app_label in ["task_center", "django_celery_beat"]:
                return "任务调度"
            return None

        # 非系统管理菜单不需要二级分组，返回 None 让前端按一级菜单展示。
        if menu_category != "系统管理":
            return None

        # 特殊映射：LLM 配置模型归入系统管理下的 LLM 配置子菜单。
        if app_label == "langgraph_integration" and model_name == "llmconfig":
            return "LLM配置"

        subcategories = {
            "auth": self._get_auth_subcategory(obj),
            "accounts": "权限管理",
            "api_keys": "KEY管理",
            "apikey": "KEY管理",
            "mcp_tools": "MCP配置",
            "mcpserverconfig": "MCP配置",
            "skills": "Skills管理",
            "llms": "LLM配置",
            "llm_config": "LLM配置",
            "message": "消息管理",
            "task_center": "任务调度",
            "django_celery_beat": "任务调度",
        }
        return subcategories.get(app_label, None)

    def _get_auth_subcategory(self, obj):
        """
        auth应用下的具体分类 - 只对特定模型进行分类
        """
        model_name = obj.model.lower()
        # 条件：auth 模型不同；动作：映射不同二级菜单；结果：用户/组织/权限入口分离。
        if model_name == "user":
            return "用户管理"
        elif model_name == "group":
            return "组织管理"
        elif model_name == "permission":
            return "权限管理"
        else:
            # 对于auth应用下的其他模型，不分配第二层分类
            return None

    def get_app_label_subcategory_sort(self, obj):
        """
        返回第二层分类的排序权重
        """
        subcategory = self.get_app_label_subcategory(obj)
        menu_category = self.get_app_label_cn(obj)
        # 未命中二级菜单时统一放在尾部，避免破坏既有分组顺序。
        if not subcategory:
            return 99  # 没有第二层分类的排在最后

        if menu_category == "任务中心" and subcategory == "任务调度":
            return 1

        subcategory_sort = {
            # 测试管理
            "用例管理": 1,
            "测试套件": 2,
            "执行历史": 3,
            # 系统管理
            "用户管理": 1,
            "组织管理": 2,
            "权限管理": 3,
            "LLM配置": 4,
            "KEY管理": 5,
            "MCP配置": 6,
            "消息管理": 7,
            "Skills管理": 8,
            "任务调度": 9,
        }
        return subcategory_sort.get(subcategory, 99)

    def get_app_label_sort(self, obj):
        """
        返回应用标签的排序权重
        数字越小排序越靠前
        """
        app_label_cn = self.get_app_label_cn(obj)
        sort_order = {
            "项目管理": 1,
            "需求管理": 2,
            "智能图表": 3,
            "UI自动化": 4,
            "任务中心": 5,
            "测试管理": 6,
            "LLM对话": 7,
            "知识库管理": 8,
            "系统管理": 9,
        }
        return sort_order.get(app_label_cn, 99)

    def get_model_cn(self, obj):
        """
        返回模型的中文名称，根据应用名区分相同模型
        """
        try:
            verbose_name = obj.model_class()._meta.verbose_name
            app_label = obj.app_label
            model_name = obj.model

            # 按应用+模型组合进行精确翻译
            app_model_translations = {
                # llm_config 应用下的模型
                "llm_config.llmprovider": "LLM提供商配置",
                "llm_config.llmmodel": "LLM模型配置",
                "llm_config.llmconfiguration": "LLM配置",
                # llms 应用下的模型
                "llms.llmprovider": "LLM提供商",
                "llms.llmmodel": "LLM模型",
                "llms.llmservice": "LLM服务",
                # 其他应用模型
                "message.message": "消息",
                "conversation.conversation": "对话",
                "api_keys.apikey": "API密钥",
                "mcp_tools.mcpserverconfig": "MCP服务器配置",
                "mcp_tools.mcptool": "MCP工具",
                "knowledge.document": "文档",
                "knowledge.knowledgebase": "知识库",
                "knowledge.knowledgedocument": "知识库文档",
                "knowledge.documentchunk": "文档分块",
                "knowledge.vectordatabaseindex": "向量数据库索引",
                "knowledge.vectorstoreindex": "向量存储索引",
                "testcase_templates.importexporttemplate": "用例导入导出模板",
                "orchestrator_integration.orchestratortask": "智能编排任务",
                "orchestrator_integration.agenttask": "Agent任务",
                "orchestrator_integration.agentstep": "Agent步骤",
                "orchestrator_integration.agentblackboard": "Agent黑板",
                "skills.skill": "Skills",
                "langgraph_integration.usertoolapproval": "用户工具审批偏好",
                "task_center.scheduledtask": "调度任务",
                "task_center.taskexecution": "任务执行记录",
                "django_celery_beat.clockedschedule": "单次调度配置",
                "django_celery_beat.crontabschedule": "Cron调度配置",
                "django_celery_beat.intervalschedule": "间隔调度配置",
                "django_celery_beat.periodictask": "周期任务",
                "django_celery_beat.periodictasks": "周期任务状态",
                "django_celery_beat.solarschedule": "太阳事件调度配置",
                "ui_automation.uibatchexecutionrecord": "UI批量执行记录",
                "ui_automation.uicasestepsdetailed": "UI用例步骤明细",
                "ui_automation.uielement": "UI元素",
                "ui_automation.uienvironmentconfig": "UI环境配置",
                "ui_automation.uiexecutionrecord": "UI执行记录",
                "ui_automation.uimodule": "UI模块",
                "ui_automation.uipage": "UI页面",
                "ui_automation.uipagesteps": "UI页面步骤",
                "ui_automation.uipagestepsdetailed": "UI页面步骤明细",
                "ui_automation.uipublicdata": "UI公共数据",
                "ui_automation.uitestcase": "UI测试用例",
            }

            # 优先使用 应用+模型 精确映射，避免跨应用同名模型翻译冲突。
            app_model_key = f"{app_label}.{model_name}"
            if app_model_key in app_model_translations:
                return app_model_translations[app_model_key]

            # 未命中精确映射时回退到通用名称映射，保证最差情况也有中文展示。
            model_name_translations = {
                "chatsession": "对话会话",
                "chat session": "对话会话",
                "chatmessage": "对话消息",
                "chat message": "对话消息",
                "message": "消息",
                "conversation": "对话",
                "apikey": "API密钥",
                "api key": "API密钥",
                "mcpserverconfig": "MCP服务器配置",
                "mcp server config": "MCP服务器配置",
                "llmprovider": "LLM提供商",
                "llm provider": "LLM提供商",
                "llmmodel": "LLM模型",
                "llm model": "LLM模型",
                "llmconfiguration": "LLM配置",
                "llm configuration": "LLM配置",
                "vectordatabaseindex": "向量数据库索引",
                "vector database index": "向量数据库索引",
                "vectorstoreindex": "向量存储索引",
                "vector store index": "向量存储索引",
                "document": "文档",
                "knowledgebase": "知识库",
                "knowledge base": "知识库",
                "knowledgedocument": "知识库文档",
                "knowledge document": "知识库文档",
                "documentchunk": "文档分块",
                "document chunk": "文档分块",
                "user": "用户",
                "group": "用户组",
                "permission": "权限",
                "content type": "内容类型",
                "session": "会话",
                "log entry": "日志条目",
                "importexporttemplate": "用例导入导出模板",
                "orchestratortask": "智能编排任务",
                "agenttask": "Agent任务",
                "agentstep": "Agent步骤",
                "agentblackboard": "Agent黑板",
                "skill": "Skills",
                "usertoolapproval": "用户工具审批偏好",
                "mcptool": "MCP工具",
                "scheduledtask": "调度任务",
                "taskexecution": "任务执行记录",
                "clockedschedule": "单次调度配置",
                "crontabschedule": "Cron调度配置",
                "intervalschedule": "间隔调度配置",
                "periodictask": "周期任务",
                "periodictasks": "周期任务状态",
                "solarschedule": "太阳事件调度配置",
                "uibatchexecutionrecord": "UI批量执行记录",
                "uicasestepsdetailed": "UI用例步骤明细",
                "uielement": "UI元素",
                "uienvironmentconfig": "UI环境配置",
                "uiexecutionrecord": "UI执行记录",
                "uimodule": "UI模块",
                "uipage": "UI页面",
                "uipagesteps": "UI页面步骤",
                "uipagestepsdetailed": "UI页面步骤明细",
                "uipublicdata": "UI公共数据",
                "uitestcase": "UI测试用例",
            }
            return model_name_translations.get(verbose_name.lower(), verbose_name)
        except:
            # 条件：无法读取 model_class()._meta；动作：回退 model 字段翻译；结果：接口不因反射失败中断。
            app_label = obj.app_label
            model_name = obj.model

            # 按应用+模型组合进行精确翻译
            app_model_translations = {
                "llm_config.llmprovider": "LLM提供商配置",
                "llm_config.llmmodel": "LLM模型配置",
                "llm_config.llmconfiguration": "LLM配置",
                "llms.llmprovider": "LLM提供商",
                "llms.llmmodel": "LLM模型",
                "llms.llmservice": "LLM服务",
                "mcp_tools.mcptool": "MCP工具",
                "testcase_templates.importexporttemplate": "用例导入导出模板",
                "orchestrator_integration.orchestratortask": "智能编排任务",
                "orchestrator_integration.agenttask": "Agent任务",
                "orchestrator_integration.agentstep": "Agent步骤",
                "orchestrator_integration.agentblackboard": "Agent黑板",
                "skills.skill": "Skills",
                "langgraph_integration.usertoolapproval": "用户工具审批偏好",
                "task_center.scheduledtask": "调度任务",
                "task_center.taskexecution": "任务执行记录",
                "django_celery_beat.clockedschedule": "单次调度配置",
                "django_celery_beat.crontabschedule": "Cron调度配置",
                "django_celery_beat.intervalschedule": "间隔调度配置",
                "django_celery_beat.periodictask": "周期任务",
                "django_celery_beat.periodictasks": "周期任务状态",
                "django_celery_beat.solarschedule": "太阳事件调度配置",
                "ui_automation.uibatchexecutionrecord": "UI批量执行记录",
                "ui_automation.uicasestepsdetailed": "UI用例步骤明细",
                "ui_automation.uielement": "UI元素",
                "ui_automation.uienvironmentconfig": "UI环境配置",
                "ui_automation.uiexecutionrecord": "UI执行记录",
                "ui_automation.uimodule": "UI模块",
                "ui_automation.uipage": "UI页面",
                "ui_automation.uipagesteps": "UI页面步骤",
                "ui_automation.uipagestepsdetailed": "UI页面步骤明细",
                "ui_automation.uipublicdata": "UI公共数据",
                "ui_automation.uitestcase": "UI测试用例",
            }

            app_model_key = f"{app_label}.{model_name}"
            if app_model_key in app_model_translations:
                return app_model_translations[app_model_key]

            model_name_translations = {
                "chatsession": "对话会话",
                "chatmessage": "对话消息",
                "message": "消息",
                "conversation": "对话",
                "apikey": "API密钥",
                "mcpserverconfig": "MCP服务器配置",
                "llmprovider": "LLM提供商",
                "llmmodel": "LLM模型",
                "llmconfiguration": "LLM配置",
                "llmconfig": "LLM配置",
                "vectordatabaseindex": "向量数据库索引",
                "vectorstoreindex": "向量存储索引",
                "document": "文档",
                "knowledgebase": "知识库",
                "knowledgedocument": "知识库文档",
                "documentchunk": "文档分块",
                "user": "用户",
                "group": "用户组",
                "permission": "权限",
                "importexporttemplate": "用例导入导出模板",
                "orchestratortask": "智能编排任务",
                "agenttask": "Agent任务",
                "agentstep": "Agent步骤",
                "agentblackboard": "Agent黑板",
                "skill": "Skills",
                "usertoolapproval": "用户工具审批偏好",
                "mcptool": "MCP工具",
                "scheduledtask": "调度任务",
                "taskexecution": "任务执行记录",
                "clockedschedule": "单次调度配置",
                "crontabschedule": "Cron调度配置",
                "intervalschedule": "间隔调度配置",
                "periodictask": "周期任务",
                "periodictasks": "周期任务状态",
                "solarschedule": "太阳事件调度配置",
                "uibatchexecutionrecord": "UI批量执行记录",
                "uicasestepsdetailed": "UI用例步骤明细",
                "uielement": "UI元素",
                "uienvironmentconfig": "UI环境配置",
                "uiexecutionrecord": "UI执行记录",
                "uimodule": "UI模块",
                "uipage": "UI页面",
                "uipagesteps": "UI页面步骤",
                "uipagestepsdetailed": "UI页面步骤明细",
                "uipublicdata": "UI公共数据",
                "uitestcase": "UI测试用例",
            }
            return model_name_translations.get(obj.model.lower(), obj.model)

    def get_model_verbose(self, obj):
        """
        返回模型的详细名称（与model_cn相同，保持兼容性）
        """
        try:
            return obj.model_class()._meta.verbose_name
        except:
            return obj.model



class PermissionSerializer(serializers.ModelSerializer):
    content_type = ContentTypeSerializer(
        read_only=True
    )  # 使用嵌套的ContentTypeSerializer
    name_cn = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ("id", "name", "name_cn", "codename", "content_type")

    def get_name_cn(self, obj):
        """
        返回权限名称的中文翻译。
        """
        # 优先从 PERMISSION_NAME_TRANSLATIONS 映射中获取
        # 如果Django的i18n配置好了，也可以直接翻译obj.name
        # 例如: return _(obj.name)
        translated_name = PERMISSION_NAME_TRANSLATIONS.get(obj.name)
        if translated_name:
            return translated_name

        # 对未显式配置的标准CRUD权限，基于 codename 动态生成中文名称
        action_map = {
            "add": "添加",
            "change": "修改",
            "delete": "删除",
            "view": "查看",
        }
        codename = getattr(obj, "codename", "") or ""
        if "_" in codename:
            action, _model = codename.split("_", 1)
            if action in action_map:
                try:
                    # 基于 content_type 反推模型中文名，拼装成统一的 CRUD 权限文案。
                    model_cn = ContentTypeSerializer(context=self.context).get_model_cn(
                        obj.content_type
                    )
                    return f"{action_map[action]}{model_cn}"
                except Exception:
                    # 翻译失败时回退原始名称，保证接口稳定返回。
                    pass

        return obj.name


# 特定操作使用的序列化器


class UserGroupOperationSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        help_text="要操作的用户ID列表",
    )

    # 在序列化阶段先校验用户是否存在，避免在视图层再处理 DoesNotExist
    def validate_user_ids(self, value):
        # 条件：提交的 ID 数量与数据库命中数不一致；动作：抛错；结果：阻断无效批量操作。
        if not User.objects.filter(id__in=value).count() == len(set(value)):
            raise serializers.ValidationError("一个或多个用户ID无效。")
        return value


class PermissionAssignToUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(help_text="目标用户ID")
    # 如需一次分配多个权限，可在请求体中增加 permission_ids
    # 当前场景为单权限分配：权限由 URL 中的 pk 指定，用户由请求体中的 user_id 指定

    def validate_user_id(self, value):
        # 单用户权限操作需先保证目标用户存在，避免后续视图层重复判空。
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("指定的用户ID无效。")
        return value


class PermissionAssignToGroupSerializer(serializers.Serializer):
    group_id = serializers.IntegerField(help_text="目标用户组ID")

    def validate_group_id(self, value):
        # 单用户组权限操作需先保证目标用户组存在。
        if not Group.objects.filter(id=value).exists():
            raise serializers.ValidationError("指定的用户组ID无效。")
        return value


# 批量权限操作序列化器
class BatchPermissionOperationSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        help_text="要操作的权限ID列表",
    )

    def validate_permission_ids(self, value):
        from django.contrib.auth.models import Permission

        # 检查所有权限ID是否有效
        existing_count = Permission.objects.filter(id__in=value).count()
        # 条件：提交 ID 中存在重复或不存在项；动作：报错；结果：保证批量写入对象集合可完整命中。
        if existing_count != len(set(value)):
            raise serializers.ValidationError("一个或多个权限ID无效。")
        return value


class BatchUserPermissionOperationSerializer(BatchPermissionOperationSerializer):
    """批量用户权限操作序列化器"""

    pass


class BatchGroupPermissionOperationSerializer(BatchPermissionOperationSerializer):
    """批量用户组权限操作序列化器"""

    pass


class UpdateUserPermissionsSerializer(serializers.Serializer):
    """更新用户权限序列化器 - 用于完全替换用户的直接权限列表"""

    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,  # 允许空列表，表示清空所有直接权限
        help_text="要设置的权限ID列表，将完全替换用户当前的直接权限",
    )

    def validate_permission_ids(self, value):
        from django.contrib.auth.models import Permission

        if not value:  # 如果是空列表，直接返回
            return value

        # 检查所有权限ID是否有效
        existing_count = Permission.objects.filter(id__in=value).count()
        # 条件：权限 ID 非法；动作：阻断更新；结果：避免 set() 后出现不可预期的部分更新。
        if existing_count != len(set(value)):
            raise serializers.ValidationError("一个或多个权限ID无效。")
        return value


class UpdateGroupPermissionsSerializer(serializers.Serializer):
    """更新用户组权限序列化器 - 用于完全替换用户组的权限列表"""

    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,  # 允许空列表，表示清空所有权限
        help_text="要设置的权限ID列表，将完全替换用户组当前的权限",
    )

    def validate_permission_ids(self, value):
        from django.contrib.auth.models import Permission

        if not value:  # 如果是空列表，直接返回
            return value

        # 检查所有权限ID是否有效
        existing_count = Permission.objects.filter(id__in=value).count()
        # 条件：权限 ID 非法；动作：阻断更新；结果：避免用户组权限被写入不完整集合。
        if existing_count != len(set(value)):
            raise serializers.ValidationError("一个或多个权限ID无效。")
        return value


class MyTokenObtainPairSerializer(BaseTokenObtainPairSerializer):
    # 覆盖默认的错误消息，使其更友好
    default_error_messages = {"no_active_account": "账号或密码错误"}

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # 您可以在这里添加自定义声明到 token 中，如果需要的话
        # 示例：可在此向 token 写入用户名声明。
        return token

    def validate(self, attrs):
        # 先走父类认证校验，再附加用户信息以减少前端二次请求。
        data = super().validate(attrs)

        # 添加用户基础信息
        user_serializer = UserDetailSerializer(self.user)
        data["user"] = user_serializer.data

        return data
