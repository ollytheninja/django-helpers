from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class EmailUserManager(BaseUserManager):
    """Create users whose unique identifier is a normalised email address."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields: Any):
        email = email.strip()
        if not email:
            raise ValueError("An email address is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True")
        return self._create_user(email, password, **extra_fields)


class AbstractEmailUser(AbstractUser):
    """Abstract Django user identified by email, with no username field."""

    username = None
    email = models.EmailField("email address", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = EmailUserManager()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = type(self).objects.normalize_email(self.email.strip()).lower()
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return self.get_full_name().strip() or self.email

    def __str__(self) -> str:
        return self.display_name
