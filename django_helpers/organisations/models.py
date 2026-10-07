from django.conf import settings
from django.db import models

from django_helpers.models import TimeStampedModel


class Organisation(TimeStampedModel):
    """A named organisation or nested organisational unit."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    personal_owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="personal_organisation",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="unique_org_name_per_parent")
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        ancestor = self.parent
        while ancestor is not None:
            if ancestor.pk == self.pk:
                from django.core.exceptions import ValidationError

                raise ValidationError({"parent": "An organisation cannot contain itself."})
            ancestor = ancestor.parent


class OrganisationMembership(TimeStampedModel):
    """An active user role within an organisation."""

    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organisation_memberships",
    )
    role = models.CharField(max_length=50, default="member")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["organisation__name", "user_id", "role"]
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "user", "role"],
                name="unique_organisation_user_role",
            )
        ]
        indexes = [models.Index(fields=["organisation", "role", "is_active"])]

    def __str__(self) -> str:
        return f"{self.user} — {self.organisation} ({self.role})"
