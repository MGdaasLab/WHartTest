from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Permission
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=User)
def track_staff_status_change(sender, instance, **kwargs):
    """
    在保存用户前，记录 is_staff 状态变化
    """
    if instance.pk:  # 只对已存在的用户记录状态变化
        try:
            old_instance = User.objects.get(pk=instance.pk)
            instance._old_is_staff = old_instance.is_staff
        except User.DoesNotExist:
            instance._old_is_staff = None
    else:
        instance._old_is_staff = None

@receiver(post_save, sender=User)
def auto_assign_admin_permissions(sender, instance, created, **kwargs):
    """
    用户保存后，根据 is_staff 状态自动分配或移除权限
    """
    old_is_staff = getattr(instance, '_old_is_staff', None)
    current_is_staff = instance.is_staff
    
    # 检查是否有状态变化
    staff_status_changed = old_is_staff is not None and old_is_staff != current_is_staff
    is_new_staff_user = created and current_is_staff
    
    if is_new_staff_user or staff_status_changed:
        if current_is_staff:
            # 设置为管理员或新建管理员：分配所有权限
            all_permissions = Permission.objects.all()
            instance.user_permissions.set(all_permissions)
            logger.info(f"用户 {instance.username} 设置为管理员，已自动分配 {all_permissions.count()} 个权限")
        elif staff_status_changed and not current_is_staff:
            # 从管理员降级：移除所有直接权限
            instance.user_permissions.clear()
            logger.info(f"用户 {instance.username} 取消管理员，已移除所有直接权限（用户组权限保留）")
    
    # 清理临时状态
    if hasattr(instance, '_old_is_staff'):
        delattr(instance, '_old_is_staff')
