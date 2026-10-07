from .settings import *  # noqa: F403

AUTH_USER_MODEL = "django_helpers_identity.User"
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "tests.testapp"]  # noqa: F405
