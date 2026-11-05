from django.contrib import admin
from .models import Project, Place


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at', 'updated_at')
    search_fields = ('name', 'user__email')
    list_filter = ('created_at',)


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'project', 'created_at')
    list_filter = ('type',)
    search_fields = ('name', 'project__name')
