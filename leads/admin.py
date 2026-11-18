from django.contrib import admin

from .models import Building, Note, Run


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("address", "class_a_units", "class_b_units", "on_class_b_list", "tax_owed", "lien_stage", "score", "status")
    list_filter = ("on_class_b_list", "status", "zip_code")
    search_fields = ("street_name", "bin", "bbl", "owner_name")


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("started", "finished", "ok")


admin.site.register(Note)
