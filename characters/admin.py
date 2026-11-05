from django.contrib import admin
from .models import Character, CharacterRelationship


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'project', 'species', 'current_status')
    list_filter = ('species', 'current_status')
    search_fields = ('full_name', 'project__name')


@admin.register(CharacterRelationship)
class CharacterRelationshipAdmin(admin.ModelAdmin):
    list_display = ('character_1', 'relationship_type', 'character_2', 'project')
    search_fields = ('character_1__full_name', 'character_2__full_name', 'relationship_type')
