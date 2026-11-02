from django.conf import settings
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .services import anonymize_application


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def anonymize_on_account_deletion(sender, instance, **kwargs):
    """Remove a deleted user's hiring data.

    Accounts are deleted only in Django admin, so a signal is what covers
    both its single delete and its bulk action.
    """
    for application in instance.applications.all():
        anonymize_application(application)
