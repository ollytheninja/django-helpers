from django.apps import AppConfig


class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_helpers.identity"
    label = "django_helpers_identity"
    verbose_name = "Identity"

    def ready(self):
        from . import checks  # noqa: F401
