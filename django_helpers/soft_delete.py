"""Opt-in soft deletion for Django models."""

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        count = self.active().update(deleted_at=timezone.now())
        return count, {self.model._meta.label: count}

    def restore(self):
        return self.deleted().update(deleted_at=None)

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().active()


class SoftDeleteModel(models.Model):
    """Hide deleted rows from the default manager while retaining recovery access."""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True
        base_manager_name = "all_objects"
        default_manager_name = "objects"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False):
        if self.is_deleted:
            return 0, {self._meta.label: 0}
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["deleted_at"])
        return 1, {self._meta.label: 1}

    def restore(self, *, using=None) -> None:
        if self.is_deleted:
            self.deleted_at = None
            self.save(using=using, update_fields=["deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)
