import uuid
from typing import Any

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Abstract model with a UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class UuidModel(UUIDModel):
    """Backward-compatible spelling of `UUIDModel`."""

    str = None

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.str.format(self=self) if self.str else super().__str__()


class OwnerMixin(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_owned",
    )

    class Meta:
        abstract = True


class OwnerChildMixin(models.Model):
    """Expose an owner reached through a configured relationship path."""

    owner_path = "parent.owner"

    class Meta:
        abstract = True

    @property
    def owner(self) -> Any:
        value: Any = self
        for part in self.owner_path.split("."):
            value = getattr(value, part)
        return value


class TitleMixin(models.Model):
    title = models.CharField(max_length=255)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.title
