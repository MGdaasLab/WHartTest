from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer as BaseTokenObtainPairSerializer

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
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'is_staff', 'is_active') # 添加管理员相关字段

    def create(self, validated_data):
        # 信号处理器会自动处理管理员权限分配，这里只需要正常创建用户
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_staff=validated_data.get('is_staff', False),
            is_active=validated_data.get('is_active', True)
        )
        
        return user

class UserDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying user details (read-only, no password).
    """
    groups = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'groups') # 根据需要添加更多字段
        read_only_fields = fields

class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user details by an admin.
    Password is not required and handled separately if provided.
    """
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    groups = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), many=True, required=False)
    # Add other fields that can be updated by an admin
    # For example: first_name, last_name, is_staff, is_active

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'password', 'groups')
        extra_kwargs = {
            'password': {'write_only': True, 'required': False, 'style': {'input_type': 'password'}},
            'username': {'required': False},
            'email': {'required': False},
            # 'groups' will use default PrimaryKeyRelatedField behavior
        }

    def update(self, instance, validated_data):
        # 信号处理器会自动处理管理员权限分配，这里只需要正常更新用户
        
        # Handle password update separately
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)

        # Handle groups update separately
        if 'groups' in validated_data:
            instance.groups.set(validated_data.pop('groups'))

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()  # 保存时会触发信号处理器
        
        return instance


class GroupSerializer(serializers.ModelSerializer):
    users = serializers.StringRelatedField(many=True, read_only=True, source='user_set')

    class Meta:
        model = Group
        fields = ('id', 'name', 'users')


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
        fields = ('id', 'app_label', 'app_label_cn', 'app_label_subcategory', 'app_label_subcategory_sort', 'app_label_sort', 'model', 'model_cn', 'model_verbose')

    def get_app_label_cn(self, obj):
        """
        返回应用标签的中文名称
        第一层：项目管理、需求管理、用例管理、LLM对话、知识库管理、系统管理
        第二层：系统管理下有子分类：用户管理、组织管理、权限管理、LLM配置、KEY管理、MCP配置
        """
        # langgraph_integration应用特殊处理：根据模型区分分类
        if obj.app_label == 'langgraph_integration':
            model_name = obj.model.lower()
            if model_name == 'llmconfig':
                return '系统管理'  # LLM配置归到系统管理下的LLM配置
            else:  # chatsession, chatmessage
                return 'LLM对话'  # 对话相关归到LLM对话
        
        # prompts应用归类到LLM对话（用户提示词与对话功能相关）
        if obj.app_label == 'prompts':
            return 'LLM对话'
        
        app_labels = {
            # 核心业务模块 (第一层)
            'projects': '项目管理',
            'testcases': '用例管理', 
            'requirements': '需求管理',
            'knowledge': '知识库管理',

            # 系统管理模块 (第一层，下面会有第二层细分)
            'auth': '系统管理',  # 用户、组、权限管理
            'accounts': '系统管理',  # 账户相关功能
            'api_keys': '系统管理',
            'apikey': '系统管理',  # API密钥管理
            'mcp_tools': '系统管理', 
            'llms': '系统管理',  # LLM服务相关
            'llm_config': '系统管理',  # LLM配置相关
            'message': '系统管理',  # 消息系统
            'mcpserverconfig': '系统管理',  # MCP服务器配置
            
            # 这些系统核心应用明确归类，但不给第二层分类
            'admin': '系统管理',
            'contenttypes': '系统管理', 
            'sessions': '系统管理',
            'authtoken': '系统管理',  # 如果存在
        }
        # 对于明确映射中没有的应用，检查后再决定是否归类到系统管理
        return app_labels.get(obj.app_label, '系统管理')  # 保持默认归类到系统管理

    def get_app_label_subcategory(self, obj):
        """
        返回第二层分类（仅系统管理模块有第二层分类）
        系统管理下的子分类：用户管理、组织管理、权限管理、LLM配置、KEY管理、MCP配置
        """
        # 只有系统管理模块才有第二层分类
        if self.get_app_label_cn(obj) != '系统管理':
            return None
            
        # 严格控制：只有明确定义的应用才给第二层分类
        # 排除所有系统核心应用，即使它们被归类到"系统管理"也不给第二层分类
        if obj.app_label in ['admin', 'contenttypes', 'sessions', 'authtoken']:
            return None
        
        # langgraph_integration应用特殊处理：只有llmconfig模型才归到LLM配置
        if obj.app_label == 'langgraph_integration' and obj.model.lower() == 'llmconfig':
            return 'LLM配置'
            
        # 其他所有应用（包括任何未知应用）都不设第二层分类
        subcategories = {
            # auth应用：用户、组、权限管理
            'auth': self._get_auth_subcategory(obj),
            # accounts应用：权限管理相关
            'accounts': '权限管理',
            # API密钥管理
            'api_keys': 'KEY管理',
            'apikey': 'KEY管理',  # API密钥也归到KEY管理
            # MCP工具配置
            'mcp_tools': 'MCP配置',
            'mcpserverconfig': 'MCP配置',  # MCP服务器配置也归到MCP配置
            # LLM相关应用都归到LLM配置（注意：prompts现在归到LLM对话了）
            'llms': 'LLM配置',
            'llm_config': 'LLM配置',
            # 消息系统
            'message': '消息管理',
        }
        # 严格控制：只返回明确定义的分类，其他一律返回None
        return subcategories.get(obj.app_label, None)
    
    def _get_auth_subcategory(self, obj):
        """
        auth应用下的具体分类 - 只对特定模型进行分类
        """
        model_name = obj.model.lower()
        if model_name == 'user':
            return '用户管理'
        elif model_name == 'group':
            return '组织管理'  
        elif model_name == 'permission':
            return '权限管理'
        else:
            # 对于auth应用下的其他模型，不分配第二层分类
            return None
    
    def get_app_label_subcategory_sort(self, obj):
        """
        返回第二层分类的排序权重
        """
        subcategory = self.get_app_label_subcategory(obj)
        if not subcategory:
            return 99  # 没有第二层分类的排在最后
            
        subcategory_sort = {
            '用户管理': 1,
            '组织管理': 2,
            '权限管理': 3,
            'LLM配置': 4,
            'KEY管理': 5,
            'MCP配置': 6,
            '消息管理': 7,
        }
        return subcategory_sort.get(subcategory, 99)

    def get_app_label_sort(self, obj):
        """
        返回应用标签的排序权重
        数字越小排序越靠前
        """
        app_label_cn = self.get_app_label_cn(obj)
        sort_order = {
            '项目管理': 1,
            '需求管理': 2,
            '用例管理': 3,
            'LLM对话': 4,
            '知识库管理': 5,
            '系统管理': 6,  # 系统管理排在最后
        }
        return sort_order.get(app_label_cn, 6)  # 默认排在最后

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
                'llm_config.llmprovider': 'LLM提供商配置',
                'llm_config.llmmodel': 'LLM模型配置', 
                'llm_config.llmconfiguration': 'LLM配置',
                
                # llms 应用下的模型
                'llms.llmprovider': 'LLM提供商',
                'llms.llmmodel': 'LLM模型',
                'llms.llmservice': 'LLM服务',
                
                # 其他应用模型
                'message.message': '消息',
                'conversation.conversation': '对话',
                'api_keys.apikey': 'API密钥',
                'mcp_tools.mcpserverconfig': 'MCP服务器配置',
                'knowledge.document': '文档',
                'knowledge.knowledgebase': '知识库',
                'knowledge.knowledgedocument': '知识库文档',
                'knowledge.documentchunk': '文档分块',
                'knowledge.vectordatabaseindex': '向量数据库索引',
                'knowledge.vectorstoreindex': '向量存储索引',
            }
            
            # 先尝试应用+模型的精确匹配
            app_model_key = f"{app_label}.{model_name}"
            if app_model_key in app_model_translations:
                return app_model_translations[app_model_key]
            
            # 通用模型名称翻译映射（作为备选）
            model_name_translations = {
                'chatsession': '对话会话',
                'chat session': '对话会话',
                'chatmessage': '对话消息',
                'chat message': '对话消息',
                'message': '消息',
                'conversation': '对话',
                'apikey': 'API密钥',
                'api key': 'API密钥',
                'mcpserverconfig': 'MCP服务器配置',
                'mcp server config': 'MCP服务器配置',
                'llmprovider': 'LLM提供商',
                'llm provider': 'LLM提供商',
                'llmmodel': 'LLM模型',
                'llm model': 'LLM模型',
                'llmconfiguration': 'LLM配置',
                'llm configuration': 'LLM配置',
                'vectordatabaseindex': '向量数据库索引',
                'vector database index': '向量数据库索引',
                'vectorstoreindex': '向量存储索引',
                'vector store index': '向量存储索引',
                'document': '文档',
                'knowledgebase': '知识库',
                'knowledge base': '知识库',
                'knowledgedocument': '知识库文档',
                'knowledge document': '知识库文档',
                'documentchunk': '文档分块',
                'document chunk': '文档分块',
                'user': '用户',
                'group': '用户组',
                'permission': '权限',
                'content type': '内容类型',
                'session': '会话',
                'log entry': '日志条目',
            }
            return model_name_translations.get(verbose_name.lower(), verbose_name)
        except:
            # 如果获取verbose_name失败，也尝试翻译model字段
            app_label = obj.app_label
            model_name = obj.model
            
            # 按应用+模型组合进行精确翻译  
            app_model_translations = {
                'llm_config.llmprovider': 'LLM提供商配置',
                'llm_config.llmmodel': 'LLM模型配置',
                'llm_config.llmconfiguration': 'LLM配置',
                'llms.llmprovider': 'LLM提供商', 
                'llms.llmmodel': 'LLM模型',
                'llms.llmservice': 'LLM服务',
            }
            
            app_model_key = f"{app_label}.{model_name}"
            if app_model_key in app_model_translations:
                return app_model_translations[app_model_key]
                
            model_name_translations = {
                'chatsession': '对话会话',
                'chatmessage': '对话消息',
                'message': '消息',
                'conversation': '对话',
                'apikey': 'API密钥',
                'mcpserverconfig': 'MCP服务器配置',
                'llmprovider': 'LLM提供商',
                'llmmodel': 'LLM模型',
                'llmconfiguration': 'LLM配置',
                'llmconfig': 'LLM配置',
                'vectordatabaseindex': '向量数据库索引',
                'vectorstoreindex': '向量存储索引',
                'document': '文档',
                'knowledgebase': '知识库',
                'knowledgedocument': '知识库文档',
                'documentchunk': '文档分块',
                'user': '用户',
                'group': '用户组',
                'permission': '权限',
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
    content_type = ContentTypeSerializer(read_only=True)  # 使用嵌套的ContentTypeSerializer
    name_cn = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ('id', 'name', 'name_cn', 'codename', 'content_type')

    def get_name_cn(self, obj):
        """
        返回权限名称的中文翻译。
        """
        # 优先从 PERMISSION_NAME_TRANSLATIONS 映射中获取
        # 如果Django的i18n配置好了，也可以直接翻译obj.name
        # 例如: return _(obj.name)
        # 这里我们使用预定义的映射，如果找不到，则返回原始名称
        return PERMISSION_NAME_TRANSLATIONS.get(obj.name, obj.name)

# New Serializers for specific operations

class UserGroupOperationSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        help_text="要操作的用户ID列表"
    )
    # Ensure users exist, or handle DoesNotExist in the view
    def validate_user_ids(self, value):
        if not User.objects.filter(id__in=value).count() == len(set(value)):
            raise serializers.ValidationError("一个或多个用户ID无效。")
        return value

class PermissionAssignToUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(help_text="目标用户ID")
    # permission_ids could be part of the request body if assigning multiple permissions
    # For assigning a single permission (identified by URL pk) to a user (identified by user_id in body)

    def validate_user_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("指定的用户ID无效。")
        return value

class PermissionAssignToGroupSerializer(serializers.Serializer):
    group_id = serializers.IntegerField(help_text="目标用户组ID")

    def validate_group_id(self, value):
        if not Group.objects.filter(id=value).exists():
            raise serializers.ValidationError("指定的用户组ID无效。")
        return value


# 批量权限操作序列化器
class BatchPermissionOperationSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        help_text="要操作的权限ID列表"
    )

    def validate_permission_ids(self, value):
        from django.contrib.auth.models import Permission
        # 检查所有权限ID是否有效
        existing_count = Permission.objects.filter(id__in=value).count()
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
        help_text="要设置的权限ID列表，将完全替换用户当前的直接权限"
    )

    def validate_permission_ids(self, value):
        from django.contrib.auth.models import Permission
        if not value:  # 如果是空列表，直接返回
            return value

        # 检查所有权限ID是否有效
        existing_count = Permission.objects.filter(id__in=value).count()
        if existing_count != len(set(value)):
            raise serializers.ValidationError("一个或多个权限ID无效。")
        return value


class UpdateGroupPermissionsSerializer(serializers.Serializer):
    """更新用户组权限序列化器 - 用于完全替换用户组的权限列表"""
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,  # 允许空列表，表示清空所有权限
        help_text="要设置的权限ID列表，将完全替换用户组当前的权限"
    )

    def validate_permission_ids(self, value):
        from django.contrib.auth.models import Permission
        if not value:  # 如果是空列表，直接返回
            return value

        # 检查所有权限ID是否有效
        existing_count = Permission.objects.filter(id__in=value).count()
        if existing_count != len(set(value)):
            raise serializers.ValidationError("一个或多个权限ID无效。")
        return value


class MyTokenObtainPairSerializer(BaseTokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # 您可以在这里添加自定义声明到 token 中，如果需要的话
        # token['username'] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # 添加用户基础信息
        user_serializer = UserDetailSerializer(self.user)
        data['user'] = user_serializer.data

        return data