from django.urls import path

from .views import (
    WeixinBotAccountListAPIView,
    WeixinBotAccountToggleAPIView,
    WeixinLoginStartAPIView,
    WeixinLoginStatusAPIView,
    WeixinPluginInboundAPIView,
)


urlpatterns = [
    path("login/start/", WeixinLoginStartAPIView.as_view(), name="weixin-login-start"),
    path("login/<str:session_key>/status/", WeixinLoginStatusAPIView.as_view(), name="weixin-login-status"),
    path("accounts/", WeixinBotAccountListAPIView.as_view(), name="weixin-account-list"),
    path("accounts/<int:account_id>/toggle/", WeixinBotAccountToggleAPIView.as_view(), name="weixin-account-toggle"),
    path("plugin/inbound/", WeixinPluginInboundAPIView.as_view(), name="weixin-plugin-inbound"),
]
