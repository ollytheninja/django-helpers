"""WebAuthn passkey ceremony helpers for reusable passwordless authentication."""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import IdentityProfile, PasskeyCredential

REGISTRATION_CHALLENGE_KEY = "django_helpers_passkey_registration_challenge"
AUTHENTICATION_CHALLENGE_KEY = "django_helpers_passkey_authentication_challenge"


def _get_rp_config(request):
    """Resolve the stable relying party identity for this deployment."""
    rp_name = getattr(settings, "DJANGO_HELPERS_PASSKEY_RP_NAME", "Django Helpers")
    rp_id = getattr(settings, "DJANGO_HELPERS_PASSKEY_RP_ID", "")
    origin = getattr(settings, "DJANGO_HELPERS_PASSKEY_ORIGIN", "").rstrip("/")

    if (not rp_id or not origin) and not settings.DEBUG:
        raise ImproperlyConfigured(
            "Set DJANGO_HELPERS_PASSKEY_RP_ID and DJANGO_HELPERS_PASSKEY_ORIGIN"
        )
    if not rp_id or not origin:
        if not origin:
            origin = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}"
        if not rp_id:
            rp_id = urlsplit(origin).hostname
        if not rp_id:
            raise ImproperlyConfigured(
                "DJANGO_HELPERS_PASSKEY_RP_ID must be set or derivable from request host"
            )

    return rp_id, origin, rp_name


def _get_or_create_profile(user):
    """Fetch or create the IdentityProfile for a user."""
    profile, _ = IdentityProfile.objects.get_or_create(user=user)
    return profile


def registration_options(request, user):
    """Generate WebAuthn registration options for a user.

    Stores the challenge in the session for later verification.
    Returns JSON-serializable options dict.
    """
    profile = _get_or_create_profile(user)
    rp_id, origin, rp_name = _get_rp_config(request)

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=bytes(profile.webauthn_user_handle),
        user_name=user.email or user.get_username(),
        user_display_name=user.get_full_name() or user.email or user.get_username(),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=bytes(pc.credential_id)) for pc in user.passkeys.all()
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )

    request.session[REGISTRATION_CHALLENGE_KEY] = bytes_to_base64url(options.challenge)
    return options_to_json(options)


def verify_registration(request, user, credential):
    """Verify a WebAuthn registration response and store the credential.

    Returns the created PasskeyCredential instance.
    Raises ValueError on missing/expired challenge or verification failure.
    """
    challenge_b64 = request.session.pop(REGISTRATION_CHALLENGE_KEY, None)
    if not challenge_b64:
        raise ValueError("Registration challenge is missing or expired.")

    rp_id, origin, _ = _get_rp_config(request)
    challenge = base64url_to_bytes(challenge_b64)

    verification = verify_registration_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=rp_id,
        expected_origin=origin,
        require_user_verification=True,
    )

    response = credential.get("response", {})
    passkey = PasskeyCredential.objects.create(
        user=user,
        name=(credential.get("name") or "Passkey")[:100],
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=response.get("transports", []),
        device_type=getattr(
            verification.credential_device_type,
            "value",
            str(verification.credential_device_type),
        ),
        backed_up=verification.credential_backed_up,
    )
    return passkey


def authentication_options(request):
    """Generate WebAuthn authentication options (no user binding yet).

    Stores the challenge in the session for later verification.
    Returns JSON-serializable options dict.
    """
    rp_id, _, _ = _get_rp_config(request)

    options = generate_authentication_options(
        rp_id=rp_id,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    request.session[AUTHENTICATION_CHALLENGE_KEY] = bytes_to_base64url(options.challenge)
    return options_to_json(options)


@transaction.atomic
def verify_authentication(request, credential):
    """Verify a WebAuthn authentication response.

    Looks up the credential by rawId/id, verifies the signature and
    user verification, and increments the sign counter atomically.

    Returns (stored_credential, verification) tuple.
    Raises ValueError on missing/expired challenge.
    Raises PasskeyCredential.DoesNotExist if credential not found.
    Raises webauthn.exceptions.InvalidAuthenticationResponse on verification failure.
    """
    challenge_b64 = request.session.pop(AUTHENTICATION_CHALLENGE_KEY, None)
    if not challenge_b64:
        raise ValueError("Authentication challenge is missing or expired.")

    raw_id = credential.get("rawId") or credential.get("id")
    if not raw_id:
        raise ValueError("Credential missing 'id' or 'rawId' field.")

    credential_id = base64url_to_bytes(raw_id)

    stored = (
        PasskeyCredential.objects.select_for_update()
        .select_related("user")
        .get(credential_id=credential_id)
    )
    if not stored.user.is_active:
        raise ValueError("Inactive user")
    user_handle = credential.get("response", {}).get("userHandle")
    if user_handle and base64url_to_bytes(user_handle) != bytes(
        stored.user.identity_profile.webauthn_user_handle
    ):
        raise ValueError("Passkey user handle does not match")

    rp_id, origin, _ = _get_rp_config(request)
    challenge = base64url_to_bytes(challenge_b64)

    verification = verify_authentication_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=rp_id,
        expected_origin=origin,
        credential_public_key=bytes(stored.public_key),
        credential_current_sign_count=stored.sign_count,
        require_user_verification=True,
    )

    stored.sign_count = verification.new_sign_count
    stored.last_used_at = timezone.now()
    stored.save(update_fields=["sign_count", "last_used_at"])

    return stored, verification
