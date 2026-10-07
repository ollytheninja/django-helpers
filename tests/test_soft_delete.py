import pytest

from tests.testapp.models import RecoverableThing


@pytest.mark.django_db
def test_soft_delete_hides_and_restores_instance():
    thing = RecoverableThing.objects.create(name="recoverable")

    assert thing.delete()[0] == 1
    assert not RecoverableThing.objects.filter(pk=thing.pk).exists()
    assert RecoverableThing.all_objects.get(pk=thing.pk).is_deleted

    thing.restore()
    assert RecoverableThing.objects.filter(pk=thing.pk).exists()


@pytest.mark.django_db
def test_queryset_soft_delete_and_explicit_hard_delete():
    first = RecoverableThing.objects.create(name="first")
    second = RecoverableThing.objects.create(name="second")

    assert RecoverableThing.objects.filter(pk__in=[first.pk, second.pk]).delete()[0] == 2
    assert RecoverableThing.objects.count() == 0
    assert RecoverableThing.all_objects.deleted().count() == 2

    assert RecoverableThing.all_objects.deleted().restore() == 2
    assert RecoverableThing.objects.count() == 2

    first.hard_delete()
    assert not RecoverableThing.all_objects.filter(pk=first.pk).exists()
