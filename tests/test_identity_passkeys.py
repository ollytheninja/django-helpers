from types import SimpleNamespace

import pytest
from django.test import override_settings
from webauthn.helpers import bytes_to_base64url

from django_helpers.identity import passkeys
from django_helpers.identity.checks import passkey_configuration_check
from django_helpers.identity.models import IdentityProfile, PasskeyCredential
from tests.testapp.models import CustomUser


@pytest.mark.django_db
@override_settings(
    DJANGO_HELPERS_PASSKEY_RP_ID="example.com",
    DJANGO_HELPERS_PASSKEY_ORIGIN="https://example.com",
)
def test_registration_verifies_challenge_and_stores_public_credential(rf, monkeypatch):
    user = CustomUser.objects.create_user("person@example.com")
    request = rf.post("/", secure=True, HTTP_HOST="example.com")
    request.session = {}
    monkeypatch.setattr(
        passkeys,
        "generate_registration_options",
        lambda **kwargs: SimpleNamespace(challenge=b"challenge"),
    )
    monkeypatch.setattr(passkeys, "options_to_json", lambda _options: "{}")
    captured = {}

    def verify(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            credential_id=b"id",
            credential_public_key=b"public-key",
            sign_count=0,
            credential_device_type=SimpleNamespace(value="multi_device"),
            credential_backed_up=True,
        )

    monkeypatch.setattr(passkeys, "verify_registration_response", verify)
    assert passkeys.registration_options(request, user) == "{}"
    assert IdentityProfile.objects.filter(user=user).exists()
    credential = passkeys.verify_registration(
        request, user, {"name": "Laptop", "response": {"transports": ["internal"]}}
    )

    assert captured["expected_challenge"] == b"challenge"
    assert captured["expected_rp_id"] == "example.com"
    assert captured["expected_origin"] == "https://example.com"
    assert captured["require_user_verification"] is True
    assert credential.name == "Laptop"
    assert credential.transports == ["internal"]
    assert bytes(credential.public_key) == b"public-key"
    with pytest.raises(ValueError, match="missing"):
        passkeys.verify_registration(request, user, {})


@pytest.mark.django_db
@override_settings(
    DJANGO_HELPERS_PASSKEY_RP_ID="example.com",
    DJANGO_HELPERS_PASSKEY_ORIGIN="https://example.com",
)
def test_authentication_verifies_and_advances_counter(rf, monkeypatch):
    user = CustomUser.objects.create_user("person@example.com")
    profile = IdentityProfile.objects.create(user=user)
    stored = PasskeyCredential.objects.create(
        user=user, credential_id=b"id", public_key=b"public-key", sign_count=1
    )
    request = rf.post("/", secure=True, HTTP_HOST="example.com")
    request.session = {passkeys.AUTHENTICATION_CHALLENGE_KEY: bytes_to_base64url(b"challenge")}
    captured = {}

    def verify(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(new_sign_count=2)

    monkeypatch.setattr(passkeys, "verify_authentication_response", verify)
    credential = {
        "rawId": bytes_to_base64url(b"id"),
        "response": {"userHandle": bytes_to_base64url(bytes(profile.webauthn_user_handle))},
    }
    result, _verification = passkeys.verify_authentication(request, credential)

    assert result.pk == stored.pk
    assert captured["credential_current_sign_count"] == 1
    assert captured["expected_challenge"] == b"challenge"
    assert captured["require_user_verification"] is True
    stored.refresh_from_db()
    assert stored.sign_count == 2
    assert stored.last_used_at is not None
    with pytest.raises(ValueError, match="missing"):
        passkeys.verify_authentication(request, credential)


@pytest.mark.django_db
@override_settings(
    DJANGO_HELPERS_PASSKEY_RP_ID="example.com",
    DJANGO_HELPERS_PASSKEY_ORIGIN="https://example.com",
)
def test_authentication_rejects_other_user_handle(rf):
    user = CustomUser.objects.create_user("person@example.com")
    IdentityProfile.objects.create(user=user)
    PasskeyCredential.objects.create(user=user, credential_id=b"id", public_key=b"public-key")
    request = rf.post("/", secure=True, HTTP_HOST="example.com")
    request.session = {passkeys.AUTHENTICATION_CHALLENGE_KEY: bytes_to_base64url(b"challenge")}

    with pytest.raises(ValueError, match="handle"):
        passkeys.verify_authentication(
            request,
            {
                "rawId": bytes_to_base64url(b"id"),
                "response": {"userHandle": bytes_to_base64url(b"other")},
            },
        )


@override_settings(DJANGO_HELPERS_AUTHN_PASSKEYS=True, DEBUG=False)
def test_production_passkeys_require_stable_relying_party_settings():
    errors = passkey_configuration_check(None)

    assert any(error.id == "django_helpers_identity.E002" for error in errors)
