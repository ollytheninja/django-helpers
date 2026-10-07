from django.core.cache import cache
from django.db import models

from django_helpers.models import TimeStampedModel

from .service import CACHE_KEY


class FeatureFlagQuerySet(models.QuerySet):
    """Keep the cached flag set current after bulk writes."""

    def update(self, **kwargs):
        count = super().update(**kwargs)
        if count:
            cache.delete(CACHE_KEY)
        return count

    def delete(self):
        result = super().delete()
        if result[0]:
            cache.delete(CACHE_KEY)
        return result

    def bulk_create(self, objs, **kwargs):
        result = super().bulk_create(objs, **kwargs)
        if result:
            cache.delete(CACHE_KEY)
        return result

    def bulk_update(self, objs, fields, **kwargs):
        count = super().bulk_update(objs, fields, **kwargs)
        if count:
            cache.delete(CACHE_KEY)
        return count


class FeatureFlag(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    value = models.TextField(blank=True)

    objects = FeatureFlagQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        state = "active" if self.is_active else "inactive"
        return f"{self.name} ({state})"

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)
        cache.delete(CACHE_KEY)

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        cache.delete(CACHE_KEY)
        return result
