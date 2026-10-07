import pytest
from django.db import DatabaseError

from django_helpers.db import SQLITE_INIT_COMMAND, sqlite_database
from django_helpers.http import htmx_redirect, safe_next_path


def test_sqlite_database_has_deployment_defaults(tmp_path):
    config = sqlite_database(tmp_path / "database.sqlite3")

    assert config["OPTIONS"]["transaction_mode"] == "IMMEDIATE"
    assert "journal_mode=WAL" in SQLITE_INIT_COMMAND
    assert config["TEST"]["NAME"] == ":memory:"


def test_htmx_redirect_uses_response_header():
    response = htmx_redirect("/next/")

    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == "/next/"


def test_safe_next_path_rejects_external_urls(rf, settings):
    settings.ALLOWED_HOSTS = ["example.com"]
    request = rf.get("/login/", secure=True, HTTP_HOST="example.com")

    assert safe_next_path(request, "/dashboard/") == "/dashboard/"
    assert safe_next_path(request, "https://example.com/dashboard/") == (
        "https://example.com/dashboard/"
    )
    assert safe_next_path(request, "https://evil.example/dashboard/", default="/home/") == (
        "/home/"
    )
    assert safe_next_path(request, "http://example.com/") == "/"


@pytest.mark.django_db
def test_healthz_reports_version(client):
    response = client.get("/healthz/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "test-version"}


@pytest.mark.django_db
def test_readyz_checks_database(client):
    response = client.get("/readyz/")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_hides_database_errors(client, monkeypatch):
    from django_helpers import views

    def unavailable():
        raise DatabaseError("private database detail")

    monkeypatch.setattr(views.connection, "cursor", unavailable)
    response = client.get("/readyz/")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
