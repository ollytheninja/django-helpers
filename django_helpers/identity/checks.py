from importlib.util import find_spec

from django.conf import settings
from django.core.checks import Error, register


@register()
def passkey_configuration_check(app_configs=None, **_kwargs):
    if not getattr(settings, "DJANGO_HELPERS_AUTHN_PASSKEYS", False):
        return []
    errors = []
    if find_spec("webauthn") is None:
        errors.append(
            Error(
                "Passkeys need the webauthn package. Install django-helpers[passkeys].",
                id="django_helpers_identity.E001",
            )
        )
    if not settings.DEBUG and (
        not getattr(settings, "DJANGO_HELPERS_PASSKEY_RP_ID", "")
        or not getattr(settings, "DJANGO_HELPERS_PASSKEY_ORIGIN", "")
    ):
        errors.append(
            Error(
                "Production passkeys need an explicit RP ID and origin.",
                id="django_helpers_identity.E002",
            )
        )
    return errors
