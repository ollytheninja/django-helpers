import uuid

from django.conf import settings
from django.db import models


class UuidModel(models.Model):
    str = None
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True

    def __str__(self):
        if self.str:
            return self.str.format(self=self)
        else:
            return super(UuidModel, self).__str__()


class OwnerMixin(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        abstract = True


class OwnerChildMixin(models.Model):
    parent = ''

    @property
    def owner(self):
        return self._meta.get_field(self.parent)

    class Meta:
        abstract = True


class TitleMixin(models.Model):
    title = models.CharField(max_length=255)

    class Meta:
        abstract = True
