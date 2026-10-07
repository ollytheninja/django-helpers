from django.contrib import admin

from .models import Organisation, OrganisationMembership


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "personal_owner", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "personal_owner__email")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(OrganisationMembership)
class OrganisationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organisation", "role", "is_active")
    list_filter = ("role", "is_active", "organisation")
    search_fields = ("user__email", "organisation__name")
    list_select_related = ("user", "organisation")
