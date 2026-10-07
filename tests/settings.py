SECRET_KEY = "test-only"
DEBUG = True
USE_TZ = True
ROOT_URLCONF = "tests.urls"
AUTH_USER_MODEL = "testapp.CustomUser"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django_helpers",
    "django_helpers.organisations",
    "django_helpers.feature_flags",
    "django_helpers.identity",
    "tests.testapp",
]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
VERSION = "test-version"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
