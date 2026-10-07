"""Session-bound email codes and account verification."""

import secrets
import uuid
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from django_helpers.http import safe_next_path

from .models import EmailOTPChallenge, EmailOTPRateLimitBucket, IdentityProfile

CHALLENGE_SESSION_KEY = "django_helpers.identity.otp_challenge_id"
RATE_LIMIT_SESSION_KEY = "django_helpers.identity.otp_rate_limit_id"


class EmailOTPRateLimitError(RuntimeError):
    pass


class AmbiguousEmailError(RuntimeError):
    pass


class SignupClosedError(RuntimeError):
    pass


def normalize_email(email: str) -> str:
    return get_user_model().objects.normalize_email(email.strip()).lower()


def _setting(name: str, default: int) -> int:
    value = int(getattr(settings, name, default))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _rate_limit(scope: str, value: str, limit: int, now) -> None:
    key = salted_hmac("django_helpers.identity.otp-rate-limit.v1", f"{scope}:{value}").hexdigest()
    window_start = now.replace(minute=0, second=0, microsecond=0)
    bucket, _ = EmailOTPRateLimitBucket.objects.select_for_update().get_or_create(
        key=key,
        defaults={"window_start": window_start},
    )
    if bucket.window_start != window_start:
        bucket.window_start = window_start
        bucket.request_count = 0
    if bucket.request_count >= limit:
        raise EmailOTPRateLimitError(scope)
    bucket.request_count += 1
    bucket.save(update_fields=["window_start", "request_count", "updated_at"])


@transaction.atomic
def issue_email_otp(
    request,
    email: str,
    *,
    next_path: str = "",
    purpose: str = EmailOTPChallenge.Purpose.SIGN_IN,
    user=None,
) -> EmailOTPChallenge:
    """Rate-limit, persist, and email a six-digit code for this browser session."""

    email = normalize_email(email)
    validate_email(email)
    if purpose == EmailOTPChallenge.Purpose.EMAIL_CHANGE:
        if user is None or not request.user.is_authenticated or request.user.pk != user.pk:
            raise ValueError("Email change requires the signed-in user")
    elif purpose != EmailOTPChallenge.Purpose.SIGN_IN:
        raise ValueError("Unknown email code purpose")

    now = timezone.now()
    session_id = request.session.get(RATE_LIMIT_SESSION_KEY)
    if session_id is None:
        session_id = secrets.token_hex(16)
        request.session[RATE_LIMIT_SESSION_KEY] = session_id
    _rate_limit("email", email, _setting("EMAIL_OTP_MAX_REQUESTS_PER_HOUR", 5), now)
    _rate_limit(
        "session", session_id, _setting("EMAIL_OTP_MAX_REQUESTS_PER_SESSION_PER_HOUR", 10), now
    )
    _rate_limit(
        "ip",
        request.META.get("REMOTE_ADDR") or "unknown",
        _setting("EMAIL_OTP_MAX_REQUESTS_PER_IP_PER_HOUR", 50),
        now,
    )

    lifetime = _setting("EMAIL_OTP_TTL_SECONDS", 900)
    code = f"{secrets.randbelow(1_000_000):06d}"
    previous_id = request.session.get(CHALLENGE_SESSION_KEY)
    if previous_id:
        EmailOTPChallenge.objects.filter(pk=previous_id, used_at__isnull=True).update(used_at=now)
    challenge = EmailOTPChallenge.objects.create(
        email=email,
        code_hash=make_password(code),
        user=user,
        purpose=purpose,
        next_path=safe_next_path(request, next_path),
        expires_at=now + timedelta(seconds=lifetime),
    )
    request.session[CHALLENGE_SESSION_KEY] = challenge.pk
    subject = getattr(settings, "DJANGO_HELPERS_OTP_SUBJECT", "Your sign-in code")
    send_mail(
        subject,
        f"Your code is {code}. It expires in {lifetime // 60} minutes and can be used once.",
        getattr(settings, "OTP_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL),
        [email],
        fail_silently=False,
    )
    return challenge


@transaction.atomic
def consume_email_otp(request, code: str) -> EmailOTPChallenge | None:
    """Consume the current session's code once, counting failed attempts."""

    challenge_id = request.session.get(CHALLENGE_SESSION_KEY)
    if not challenge_id:
        return None
    try:
        challenge = EmailOTPChallenge.objects.select_for_update().get(pk=challenge_id)
    except (EmailOTPChallenge.DoesNotExist, TypeError, ValueError):
        return None
    now = timezone.now()
    max_attempts = _setting("EMAIL_OTP_MAX_ATTEMPTS", 5)
    if (
        challenge.used_at is not None
        or challenge.expires_at <= now
        or challenge.failed_attempts >= max_attempts
    ):
        return None
    if not check_password(code, challenge.code_hash):
        challenge.failed_attempts += 1
        fields = ["failed_attempts"]
        if challenge.failed_attempts >= max_attempts:
            challenge.used_at = now
            fields.append("used_at")
        challenge.save(update_fields=fields)
        return None
    challenge.used_at = now
    challenge.save(update_fields=["used_at"])
    request.session.pop(CHALLENGE_SESSION_KEY, None)
    return challenge


@transaction.atomic
def verified_user_for_challenge(challenge: EmailOTPChallenge):
    """Resolve or create an account only after the email code was consumed."""

    if challenge.used_at is None or challenge.purpose != EmailOTPChallenge.Purpose.SIGN_IN:
        raise ValueError("A consumed sign-in challenge is required")
    User = get_user_model()
    matches = list(
        User._default_manager.select_for_update().filter(email__iexact=challenge.email)[:2]
    )
    if len(matches) > 1:
        raise AmbiguousEmailError(challenge.email)
    if matches:
        user = matches[0]
        if not user.is_active:
            raise SignupClosedError
    else:
        if not getattr(settings, "DJANGO_HELPERS_AUTHN_ALLOW_SIGNUP", False):
            raise SignupClosedError
        user = User._default_manager.create_user(email=challenge.email)
    profile, _ = IdentityProfile.objects.get_or_create(user=user)
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=["email_verified_at"])
    if apps.is_installed("django_helpers.organisations") and getattr(
        settings, "DJANGO_HELPERS_AUTHN_PERSONAL_ORGANISATIONS", True
    ):
        from django_helpers.organisations.models import Organisation, OrganisationMembership

        organisation, _ = Organisation.objects.get_or_create(
            personal_owner=user,
            defaults={
                "slug": f"personal-{uuid.uuid4().hex}",
                "name": user.get_full_name().strip() or user.email,
            },
        )
        OrganisationMembership.objects.get_or_create(
            organisation=organisation, user=user, role="owner"
        )
    return user


@transaction.atomic
def apply_verified_email_change(request, challenge: EmailOTPChallenge):
    """Change the signed-in user's address after proving control of the new one."""

    if (
        challenge.used_at is None
        or challenge.purpose != EmailOTPChallenge.Purpose.EMAIL_CHANGE
        or challenge.user_id != request.user.pk
        or not request.user.is_authenticated
    ):
        raise ValueError("A signed-in email change challenge is required")
    User = get_user_model()
    if (
        User._default_manager.filter(email__iexact=challenge.email)
        .exclude(pk=request.user.pk)
        .exists()
    ):
        raise AmbiguousEmailError(challenge.email)
    user = request.user
    user.email = normalize_email(challenge.email)
    user.save(update_fields=["email"])
    profile, _ = IdentityProfile.objects.get_or_create(user=user)
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=["email_verified_at"])
    return user
