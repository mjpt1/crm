"""
Signal handlers for the users app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.users.models import AuditLog, CustomUser


@receiver(post_save, sender=CustomUser)
def user_post_save(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            user=None,
            action=AuditLog.ACTION_CREATE,
            model_name='CustomUser',
            object_id=str(instance.id),
            data={'email': instance.email, 'role': instance.role},
        )
