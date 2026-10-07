import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

from django_helpers.feature_flags import feature_required
from django_helpers.feature_flags.models import FeatureFlag
from django_helpers.feature_flags.service import get_value, is_active


@pytest.mark.django_db
def test_unknown_flag_fails_closed():
    assert is_active("missing") is False
    assert get_value("missing") == ""


@pytest.mark.django_db
def test_flag_updates_invalidate_cache():
    flag = FeatureFlag.objects.create(name="NEW_UI", is_active=True, value="beta")

    assert is_active("NEW_UI") is True
    assert get_value("NEW_UI") == "beta"

    flag.is_active = False
    flag.value = ""
    flag.save()

    assert is_active("NEW_UI") is False
    assert get_value("NEW_UI") == ""


@pytest.mark.django_db
def test_bulk_flag_changes_invalidate_cache():
    flag = FeatureFlag.objects.create(name="BULK", is_active=True)
    assert is_active("BULK") is True

    FeatureFlag.objects.filter(pk=flag.pk).update(is_active=False)
    assert is_active("BULK") is False

    FeatureFlag.objects.filter(pk=flag.pk).delete()
    assert is_active("BULK") is False

    FeatureFlag.objects.bulk_create([FeatureFlag(name="BULK", is_active=True)])
    assert is_active("BULK") is True


@pytest.mark.django_db
def test_feature_required_gates_function_view(rf):
    @feature_required("REPORTS")
    def reports(_request):
        return HttpResponse("ok")

    with pytest.raises(PermissionDenied):
        reports(rf.get("/reports/"))

    FeatureFlag.objects.create(name="REPORTS", is_active=True)
    assert reports(rf.get("/reports/")).content == b"ok"
