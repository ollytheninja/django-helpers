import re

import pytest
from django.core import mail
from django.test import override_settings

from django_helpers.identity.models import EmailOTPChallenge, IdentityProfile
from django_helpers.identity.otp import CHALLENGE_SESSION_KEY
from django_helpers.organisations.models import Organisation, OrganisationMembership
from tests.testapp.models import CustomUser


def _code() -> str:
    return re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()


@pytest.mark.django_db
@override_settings(DJANGO_HELPERS_AUTHN_ALLOW_SIGNUP=True)
def test_email_code_creates_verified_user_and_personal_organisation(client):
    response = client.post("/auth/login/", {"email": " Person@EXAMPLE.COM ", "next": "/next/"})
    assert response.status_code == 302
    assert response.url == "/auth/code/verify/"
    session_key_before_login = client.session.session_key
    challenge = EmailOTPChallenge.objects.get(pk=client.session[CHALLENGE_SESSION_KEY])
    assert challenge.email == "person@example.com"
    assert challenge.code_hash != _code()

    response = client.post("/auth/code/verify/", {"code": _code()})
    assert response.status_code == 302
    assert response.url == "/next/"
    user = CustomUser.objects.get(email="person@example.com")
    assert IdentityProfile.objects.get(user=user).email_verified_at is not None
    assert OrganisationMembership.objects.filter(user=user, role="owner").exists()
    assert (
        Organisation.objects.get(personal_owner=user)
        .memberships.filter(user=user, role="owner")
        .exists()
    )
    assert client.session.get("_auth_user_id") == str(user.pk)
    assert client.session.session_key != session_key_before_login
    assert CHALLENGE_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_unknown_email_stays_unclaimed_when_signup_closed(client):
    client.post("/auth/login/", {"email": "unknown@example.com"})
    response = client.post("/auth/code/verify/", {"code": _code()})

    assert response.status_code == 200
    assert b"Contact support" in response.content
    assert not CustomUser.objects.filter(email="unknown@example.com").exists()


@pytest.mark.django_db
@override_settings(DJANGO_HELPERS_AUTHN_ALLOW_SIGNUP=True)
def test_signup_does_not_claim_an_existing_organisation(client):
    existing = Organisation.objects.create(name="Existing", slug="personal-1")
    client.post("/auth/login/", {"email": "person@example.com"})
    client.post("/auth/code/verify/", {"code": _code()})

    user = CustomUser.objects.get(email="person@example.com")
    assert not OrganisationMembership.objects.filter(organisation=existing, user=user).exists()
    assert Organisation.objects.get(personal_owner=user).pk != existing.pk


@pytest.mark.django_db
def test_email_code_is_session_bound_and_single_use(client, django_user_model):
    user = django_user_model.objects.create_user("user@example.com")
    client.post("/auth/login/", {"email": user.email})
    code = _code()
    other = type(client)()
    assert other.post("/auth/code/verify/", {"code": code}).status_code == 302
    assert "_auth_user_id" not in other.session

    assert client.post("/auth/code/verify/", {"code": code}).status_code == 302
    assert CHALLENGE_SESSION_KEY not in client.session
    assert client.post("/auth/code/verify/", {"code": code}).url == "/auth/login/"


@pytest.mark.django_db
@override_settings(EMAIL_OTP_MAX_ATTEMPTS=2)
def test_email_code_locks_after_failed_attempts(client, django_user_model):
    django_user_model.objects.create_user("user@example.com")
    client.post("/auth/login/", {"email": "user@example.com"})
    challenge_id = client.session[CHALLENGE_SESSION_KEY]

    assert b"incorrect" in client.post("/auth/code/verify/", {"code": "000000"}).content
    assert b"incorrect" in client.post("/auth/code/verify/", {"code": "000000"}).content
    assert EmailOTPChallenge.objects.get(pk=challenge_id).used_at is not None
    assert b"incorrect" in client.post("/auth/code/verify/", {"code": _code()}).content


@pytest.mark.django_db
@override_settings(LOGIN_REDIRECT_URL="/")
def test_login_rejects_external_next_path(client, django_user_model):
    django_user_model.objects.create_user("user@example.com")
    client.post("/auth/login/", {"email": "user@example.com", "next": "https://evil.example/"})

    assert EmailOTPChallenge.objects.latest("pk").next_path == "/"


@pytest.mark.django_db
@override_settings(EMAIL_OTP_MAX_REQUESTS_PER_HOUR=1)
def test_email_requests_are_rate_limited(client):
    assert client.post("/auth/login/", {"email": "person@example.com"}).status_code == 302
    response = client.post("/auth/login/", {"email": "person@example.com"})

    assert response.status_code == 200
    assert b"Too many codes" in response.content
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_email_change_requires_new_address_verification(client, django_user_model):
    user = django_user_model.objects.create_user("old@example.com")
    client.force_login(user)

    response = client.post("/auth/email/change/", {"email": "new@example.com"})
    assert response.url == "/auth/code/verify/"
    user.refresh_from_db()
    assert user.email == "old@example.com"

    response = client.post("/auth/code/verify/", {"code": _code()})
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.email == "new@example.com"


@pytest.mark.django_db
@override_settings(
    DJANGO_HELPERS_AUTHN_PASSKEYS=True,
    DJANGO_HELPERS_PASSKEY_RP_ID="example.com",
    DJANGO_HELPERS_PASSKEY_ORIGIN="https://example.com",
)
def test_login_and_passkey_pages_render(client, django_user_model):
    response = client.get("/auth/login/")
    assert response.status_code == 200
    assert b"passkey-login-btn" in response.content
    assert b"/auth/passkeys/auth/options/" in response.content

    user = django_user_model.objects.create_user("person@example.com")
    client.force_login(user)
    response = client.get("/auth/passkeys/")
    assert response.status_code == 200
    assert b"passkey-register-btn" in response.content
    assert b"/auth/passkeys/register/options/" in response.content


@pytest.mark.django_db
@override_settings(
    DJANGO_HELPERS_AUTHN_PASSKEYS=True,
    DJANGO_HELPERS_PASSKEY_RP_ID="example.com",
    DJANGO_HELPERS_PASSKEY_ORIGIN="https://example.com",
)
def test_passkey_option_endpoints_use_real_webauthn_library(client, django_user_model):
    response = client.get("/auth/passkeys/auth/options/")
    assert response.status_code == 200
    assert response.json()["challenge"]

    user = django_user_model.objects.create_user("person@example.com")
    client.force_login(user)
    response = client.post("/auth/passkeys/register/options/")
    assert response.status_code == 200
    assert response.json()["user"]["id"]
