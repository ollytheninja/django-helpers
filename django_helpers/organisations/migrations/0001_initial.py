import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Organisation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=150)),
                ("slug", models.SlugField(max_length=150, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "personal_owner",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="personal_organisation",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="organisations.organisation",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="OrganisationMembership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("role", models.CharField(default="member", max_length=50)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "organisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="organisations.organisation",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="organisation_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["organisation__name", "user_id", "role"]},
        ),
        migrations.AddConstraint(
            model_name="organisation",
            constraint=models.UniqueConstraint(
                fields=("parent", "name"), name="unique_org_name_per_parent"
            ),
        ),
        migrations.AddConstraint(
            model_name="organisationmembership",
            constraint=models.UniqueConstraint(
                fields=("organisation", "user", "role"),
                name="unique_organisation_user_role",
            ),
        ),
        migrations.AddIndex(
            model_name="organisationmembership",
            index=models.Index(
                fields=["organisation", "role", "is_active"], name="organisatio_organis_056e64_idx"
            ),
        ),
    ]
