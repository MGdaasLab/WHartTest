from django.contrib import admin

from .models import (
    WeixinBotAccount,
    WeixinConversation,
    WeixinConversationMessage,
    WeixinLoginSession,
)


@admin.register(WeixinLoginSession)
class WeixinLoginSessionAdmin(admin.ModelAdmin):
    list_display = ("session_key", "user", "project", "status", "raw_account_id", "created_at")
    search_fields = ("session_key", "raw_account_id", "scanned_user_id", "user__username")


@admin.register(WeixinBotAccount)
class WeixinBotAccountAdmin(admin.ModelAdmin):
    list_display = ("raw_account_id", "user", "project", "is_active", "worker_running", "status", "updated_at")
    search_fields = ("raw_account_id", "account_id", "scanned_user_id", "user__username")


@admin.register(WeixinConversation)
class WeixinConversationAdmin(admin.ModelAdmin):
    list_display = ("account", "peer_user_id", "updated_at")
    search_fields = ("peer_user_id", "account__raw_account_id")


@admin.register(WeixinConversationMessage)
class WeixinConversationMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "external_message_id", "created_at")
    search_fields = ("external_message_id", "conversation__peer_user_id")

