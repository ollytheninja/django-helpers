import secrets

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from django_helpers.auth import AbstractEmailUser


def generate_webauthn_user_handle() -> bytes:
    """Return a stable opaque handle that does not reveal the user's primary key."""

    return secrets.token_bytes(32)


class User(AbstractEmailUser):
    """Ready-to-use email user for new projects."""

    class Meta(AbstractEmailUser.Meta):
        swappable = "AUTH_USER_MODEL"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="identity_unique_email_casefold")
        ]


class IdentityProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="identity_profile",
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    webauthn_user_handle = models.BinaryField(
        max_length=64,
        unique=True,
        default=generate_webauthn_user_handle,
        editable=False,
    )

    def __str__(self) -> str:
        return str(self.user)


class EmailOTPChallenge(models.Model):
    class Purpose(models.TextChoices):
        SIGN_IN = "sign_in", "Sign in"
        EMAIL_CHANGE = "email_change", "Email change"

    email = models.EmailField()
    code_hash = models.CharField(max_length=128, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="email_otp_challenges",
    )
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.SIGN_IN)
    next_path = models.CharField(max_length=500, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["email", "purpose", "created_at"])]

    def __str__(self) -> str:
        return f"{self.get_purpose_display()} for {self.email}"


class EmailOTPRateLimitBucket(models.Model):
    key = models.CharField(max_length=64, unique=True, editable=False)
    window_start = models.DateTimeField()
    request_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["window_start"])]

    def __str__(self) -> str:
        return self.key


class PasskeyCredential(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="passkeys",
    )
    name = models.CharField(max_length=100, default="Passkey")
    credential_id = models.BinaryField(unique=True, editable=False)
    public_key = models.BinaryField(editable=False)
    sign_count = models.PositiveBigIntegerField(default=0)
    transports = models.JSONField(default=list, blank=True)
    device_type = models.CharField(max_length=32, blank=True)
    backed_up = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.user})"
