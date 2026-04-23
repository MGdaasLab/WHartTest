from django.shortcuts import get_object_or_404
from api_keys.authentication import APIKeyAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from langgraph_integration.views import check_project_permission

from .models import WeixinBotAccount, WeixinLoginSession
from .serializers import (
    WeixinBotAccountSerializer,
    WeixinBotAccountToggleSerializer,
    WeixinPluginInboundSerializer,
    WeixinLoginSessionSerializer,
    WeixinLoginStartSerializer,
)
from .services import (
    WeixinServiceError,
    ensure_weixin_account_worker,
    handle_plugin_inbound_message,
    list_weixin_plugin_accounts_status,
    refresh_login_session,
    start_login_session,
    stop_weixin_plugin_account,
    sync_account_runtime_status,
)

class WeixinLoginStartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = WeixinLoginStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = check_project_permission(request.user, serializer.validated_data["project_id"])
        if not project:
            return Response(
                {
                    "status": "error",
                    "code": 403,
                    "message": "项目不存在或无访问权限",
                    "data": None,
                    "errors": {"project_id": ["Permission denied or project not found."]},
                },
                status=403,
            )

        prompt = None
        prompt_id = serializer.validated_data.get("prompt_id")
        if prompt_id:
            from prompts.models import UserPrompt

            prompt = get_object_or_404(UserPrompt, id=prompt_id, user=request.user, is_active=True)

        try:
            login_session = start_login_session(
                user=request.user,
                project=project,
                prompt=prompt,
            )
        except WeixinServiceError as exc:
            return Response(
                {
                    "status": "error",
                    "code": exc.status_code,
                    "message": exc.message,
                    "data": None,
                    "errors": {"detail": [exc.message]},
                },
                status=exc.status_code,
            )

        return Response(
            {
                "status": "success",
                "code": 200,
                "message": "微信二维码生成成功",
                "data": WeixinLoginSessionSerializer(login_session).data,
                "errors": None,
            }
        )


class WeixinLoginStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_key, *args, **kwargs):
        login_session = get_object_or_404(
            WeixinLoginSession,
            session_key=session_key,
            user=request.user,
        )
        login_session = refresh_login_session(login_session)

        if login_session.status == "confirmed" and login_session.raw_account_id:
            account = WeixinBotAccount.objects.filter(
                raw_account_id=login_session.raw_account_id,
                user=request.user,
            ).first()
            if account and account.is_active:
                try:
                    ensure_weixin_account_worker(account)
                except WeixinServiceError:
                    pass

        return Response(
            {
                "status": "success",
                "code": 200,
                "message": "获取微信登录状态成功",
                "data": WeixinLoginSessionSerializer(login_session).data,
                "errors": None,
            }
        )


class WeixinBotAccountListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        project_id = request.query_params.get("project_id")
        queryset = WeixinBotAccount.objects.select_related("project", "prompt").filter(
            user=request.user
        )
        if project_id:
            project = check_project_permission(request.user, project_id)
            if not project:
                return Response(
                    {
                        "status": "error",
                        "code": 403,
                        "message": "项目不存在或无访问权限",
                        "data": None,
                        "errors": {"project_id": ["Permission denied or project not found."]},
                    },
                    status=403,
                )
            queryset = queryset.filter(project_id=project_id)

        active_accounts = list(queryset.filter(is_active=True))
        for account in active_accounts:
            try:
                ensure_weixin_account_worker(account)
            except WeixinServiceError:
                continue

        try:
            runtime_status_mapping = list_weixin_plugin_accounts_status()
        except WeixinServiceError:
            runtime_status_mapping = {}
        for account in queryset:
            runtime_status = runtime_status_mapping.get(account.account_id)
            if runtime_status:
                sync_account_runtime_status(account, runtime_status)

        queryset = WeixinBotAccount.objects.select_related("project", "prompt").filter(
            user=request.user
        )
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        data = WeixinBotAccountSerializer(queryset, many=True).data
        return Response(
            {
                "status": "success",
                "code": 200,
                "message": "获取微信账号成功",
                "data": data,
                "errors": None,
            }
        )


class WeixinBotAccountToggleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, account_id, *args, **kwargs):
        account = get_object_or_404(WeixinBotAccount, id=account_id, user=request.user)
        serializer = WeixinBotAccountToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        account.is_active = serializer.validated_data["is_active"]
        if account.is_active:
            account.status = "connected"
        else:
            account.status = "stopped"
            account.worker_running = False
        account.save(update_fields=["is_active", "status", "worker_running", "updated_at"])

        if account.is_active:
            try:
                ensure_weixin_account_worker(account)
            except WeixinServiceError as exc:
                return Response(
                    {
                        "status": "error",
                        "code": exc.status_code,
                        "message": exc.message,
                        "data": None,
                        "errors": {"detail": [exc.message]},
                    },
                    status=exc.status_code,
                )
        else:
            try:
                stop_weixin_plugin_account(account)
            except WeixinServiceError:
                pass

        return Response(
            {
                "status": "success",
                "code": 200,
                "message": "更新微信账号状态成功",
                "data": WeixinBotAccountSerializer(account).data,
                "errors": None,
            }
        )


class WeixinPluginInboundAPIView(APIView):
    authentication_classes = [APIKeyAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = WeixinPluginInboundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            reply = handle_plugin_inbound_message(**serializer.validated_data)
        except WeixinServiceError as exc:
            return Response(
                {
                    "status": "error",
                    "code": exc.status_code,
                    "message": exc.message,
                    "data": None,
                    "errors": {"detail": [exc.message]},
                },
                status=exc.status_code,
            )

        return Response(
            {
                "status": "success",
                "code": 200,
                "message": "微信插件入站消息处理成功",
                "data": {"reply": reply},
                "errors": None,
            }
        )
