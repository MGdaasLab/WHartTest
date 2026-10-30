# 导入 DRF 视图集与权限基类。
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as drf_status

# 导入 SimpleJWT，用于签发短时效 WS 连接令牌。
from rest_framework_simplejwt.tokens import RefreshToken

# 导入 API Key 模型。
from .models import APIKey

# 导入 API Key 认证类（兑换端点仅接受 API Key 凭据）。
from .authentication import APIKeyAuthentication

# 导入 API Key 序列化器。
from .serializers import APIKeySerializer

# 导入对象级权限（所有者或管理员）。
from .permissions import IsOwnerOrAdmin

# 导入项目统一模型权限控制。
from wharttest_django.permissions import HasModelPermission


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    API Key 管理接口，支持查看与编辑。
    普通用户仅可管理自己的 API Key。
    管理员可管理所有 API Key。
    访问受 api_keys 模型权限控制。
    """

    serializer_class = APIKeySerializer
    permission_classes = [
        permissions.IsAuthenticated,
        HasModelPermission,
        IsOwnerOrAdmin,
    ]

    def get_queryset(self):
        """
        返回当前认证用户可见的 API Key 列表。
        """
        user = self.request.user


        # 条件：任意登录用户（含 staff）；动作：仅返回本人 Key；结果：列表接口不暴露他人密钥元数据。
        return APIKey.objects.filter(user=user).order_by("-created_at")

    def perform_create(self, serializer):
        """
        创建时自动绑定当前用户。
        """
        # 创建时强制绑定当前用户，避免通过伪造请求体写入他人账号名下。
        serializer.save(user=self.request.user)


class ExchangeTokenView(APIView):
    """
    API Key 兑换短时效 JWT access token。

    供持有 API Key 的非浏览器客户端（ui-automation skill 工具等）换取
    WebSocket 连接凭据：/ws/ui/web/ 认证中间件只认 SimpleJWT access token，
    不接受 X-API-Key，skill 需先经本端点兑换再携带 ?token=<jwt> 连接。

    认证只允许 APIKeyAuthentication：防止用 JWT 反复换 JWT 绕过
    Key 的启用/过期校验。签发的是 access token（不返回 refresh token，
    过期后重新兑换即可），生命周期跟随 SIMPLE_JWT 配置。
    """

    authentication_classes = [APIKeyAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # authenticate() 返回的 auth 值即 APIKey 实例；无 Key 的 JWT 直连会被拒
        api_key_obj = getattr(request, "auth", None)
        if not isinstance(api_key_obj, APIKey):
            return Response(
                {"error": "仅支持 API Key 兑换，不接受其他凭据"},
                status=drf_status.HTTP_403_FORBIDDEN,
            )

        # 请求头方式与 authentication.py 保持一致：Bearer 优先，回退 X-API-Key。
        # 返回裸结构，由 UnifiedResponseRenderer 统一包装为 {status, code, data} 信封
        # （手写信封会被再包一层变成 data.data 双重嵌套，客户端取不到 token）。
        access = RefreshToken.for_user(request.user).access_token
        from django.conf import settings

        lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
        return Response(
            {
                "access": str(access),
                "token_type": "Bearer",
                "expires_in": int(lifetime.total_seconds()),
            }
        )
