# Django Helpers

Small, reusable Django building blocks extracted from production projects. The package favours
Django primitives and explicit project-owned policy over a large framework.

## Install

```shell
uv add django-helpers
```

For passkeys, install the optional WebAuthn dependency with `uv add 'django-helpers[passkeys]'`.

The base package has no dependencies beyond Django. Add only the optional Django apps that a
project uses:

```python
INSTALLED_APPS = [
    # Django apps...
    "django_helpers",
    "django_helpers.organisations",
    "django_helpers.feature_flags",
]
```

Run migrations after enabling any model-bearing app.

## Passwordless login

`django_helpers.identity` provides the complete email-code and passkey login flow: models,
views, URLs, templates, browser JavaScript, rate limits, and WebAuthn verification. The app works
with a project-owned email user model whose manager supports `create_user(email=...)` and whose
email addresses are unique without regard to case. New projects
can use its concrete user model instead:

```python
INSTALLED_APPS += ["django.contrib.sessions", "django_helpers.identity"]
AUTH_USER_MODEL = "django_helpers_identity.User"  # Set before the first migration.
MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
TEMPLATES[0]["APP_DIRS"] = True
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
DEFAULT_FROM_EMAIL = "login@example.com"
DJANGO_HELPERS_AUTHN_ALLOW_SIGNUP = True
LOGIN_REDIRECT_URL = "/"
```

Mount the supplied URLs with `path("auth/", include("django_helpers.identity.urls"))`. Run
`migrate` and configure an email provider before offering login. The packaged templates work
without a project base template and can be overridden under
`django_helpers/identity/login.html`, `otp_verify.html`, and `passkeys.html`.

Signup is closed by default. With `DJANGO_HELPERS_AUTHN_ALLOW_SIGNUP = True`, a verified code
creates an account. If `django_helpers.organisations` is installed, the account also receives a
personal organisation with a `personal_owner` link and an `owner` membership. Set
`DJANGO_HELPERS_AUTHN_PERSONAL_ORGANISATIONS = False` to skip that step. Existing accounts can
sign in regardless of the signup setting. Email changes use a fresh code sent to the new address.

Enable passkeys after installing the extra:

```python
DJANGO_HELPERS_AUTHN_PASSKEYS = True
DJANGO_HELPERS_PASSKEY_RP_NAME = "Example"
DJANGO_HELPERS_PASSKEY_RP_ID = "example.com"
DJANGO_HELPERS_PASSKEY_ORIGIN = "https://example.com"
```

Keep the RP ID stable after enrolment. Production requires explicit RP ID and origin settings;
development can derive them from the request. Django owns the login session. The passkey library
verifies challenges, origin, RP ID, signatures, and user verification; the package stores public
credentials and sign counters. For an existing project, keep its current `AUTH_USER_MODEL` and
install the identity app against that user. Switching Django's user model after migrations needs
a project-specific data migration.

## Email-only users

Subclass `AbstractEmailUser` at the very start of a project. It removes `username`, normalises
email addresses, uses email as `USERNAME_FIELD`, and supplies a compatible manager.

```python
from django_helpers.auth import AbstractEmailUser


class CustomUser(AbstractEmailUser):
    pass
```

Then set `AUTH_USER_MODEL = "accounts.CustomUser"` before the first migration. The model provides
`display_name`, falling back to the email address when a person has no name.

## Authorization policy

Keep domain policy in small functions that receive a user (and optionally an object). Registering
a check makes the same rule available to Python, view decorators, mixins, and templates.

```python
from django_helpers.authz import authenticated, register_check


@register_check
@authenticated
def can_edit_invoice(user, invoice):
    return invoice.organisation.memberships.filter(user=user, role="admin").exists()
```

```python
from django_helpers.authz import check_passes


@check_passes(
    can_edit_invoice,
    object_getter=lambda request, invoice_id: get_object_or_404(Invoice, pk=invoice_id),
)
def edit_invoice(request, invoice_id): ...
```

Templates can load `django_helpers_authz` and use `{% if request.user|can:"can_list_invoices" %}`
for user-only checks. For an object check, assign the tag result first:

```django
{% can_object request.user "can_edit_invoice" invoice as may_edit %}
{% if may_edit %}...{% endif %}
```

Python remains the enforcement point; template checks only control presentation.

For a class-based detail or update view, put `AuthorizationRequiredMixin` before the Django view
class and set `authorization_uses_object = True`. The mixin calls `get_object()` before evaluating
the check. User-only checks leave that setting at its default, `False`.

```python
class InvoiceDetail(AuthorizationRequiredMixin, DetailView):
    model = Invoice
    authorization_check = can_edit_invoice
    authorization_uses_object = True
```

## Organisations

`Organisation` supports an optional parent, so the same model represents a company, school,
event, unit, team, or nested subdivision. `OrganisationMembership` joins any configured user to
an organisation with an application-defined string role. Helpers cover active membership and role
checks without dictating a project-specific role hierarchy.

## Feature flags

`FeatureFlag` stores a name, active state, description, and optional string value. `is_active()`
and `get_value()` use Django's cache and fail closed for unknown flags. Model saves and deletes
invalidate the cache, as do queryset updates, deletes, and bulk writes. Call `clear_cache()` after
raw SQL changes. `@feature_required("FLAG_NAME")` gates a function view on a global flag and
raises HTTP 403 when it is inactive.

## Soft deletion

Subclass `django_helpers.soft_delete.SoftDeleteModel` to keep deleted rows recoverable. The
default `objects` manager returns active rows. `all_objects` includes deleted rows and supports
`.deleted()`, `.restore()`, and `.hard_delete()`. Instance `delete()` and queryset `delete()` both
soft-delete rows. Use `hard_delete()` when permanent removal is intended.

## Other helpers

- `django_helpers.db.sqlite_database()` produces a Fly/Litestream-friendly SQLite configuration.
- `django_helpers.http.htmx_redirect()` produces an `HX-Redirect` response.
- `django_helpers.http.safe_next_path()` validates a user-supplied return URL against the request
  host and scheme.
- `django_helpers.views.healthz()` reports liveness without a database query; `readyz()` checks
  the default database. Mount them at public probe routes in the project's URL configuration.
- `django_helpers.models` contains timestamp, title, UUID, and ownership abstract models.

See each public function's docstring and the test suite for executable examples.

## Development

```shell
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
