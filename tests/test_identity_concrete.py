import re

import pytest
from django.conf import settings
from django.core import mail

from django_helpers.identity.models import IdentityProfile


@pytest.mark.django_db
@pytest.mark.skipif(
    settings.AUTH_USER_MODEL != "django_helpers_identity.User",
    reason="Runs with tests.settings_identity",
)
def test_package_user_completes_email_login(client, django_user_model, settings):
    settings.DJANGO_HELPERS_AUTHN_ALLOW_SIGNUP = True
    client.post("/auth/login/", {"email": "person@example.com"})
    code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()

    response = client.post("/auth/code/verify/", {"code": code})

    assert response.status_code == 302
    user = django_user_model.objects.get(email="person@example.com")
    assert user.username is None
    assert IdentityProfile.objects.get(user=user).email_verified_at is not None
