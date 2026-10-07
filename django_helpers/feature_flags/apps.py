from django.apps import AppConfig


class FeatureFlagsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_helpers.feature_flags"
    verbose_name = "Feature flags"
