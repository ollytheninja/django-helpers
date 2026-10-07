from django.db import models

from django_helpers.auth import AbstractEmailUser
from django_helpers.models import OwnerChildMixin, OwnerMixin
from django_helpers.soft_delete import SoftDeleteModel


class CustomUser(AbstractEmailUser):
    pass


class OwnedThing(OwnerMixin):
    name = models.CharField(max_length=50)


class ChildThing(OwnerChildMixin):
    parent = models.ForeignKey(OwnedThing, on_delete=models.CASCADE)


class RecoverableThing(SoftDeleteModel):
    name = models.CharField(max_length=50)
