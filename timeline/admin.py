from django.contrib import admin
from .models import Event, EventCharacter, EventPlace, EventRelationship, TimelineSpan

admin.site.register(Event)
admin.site.register(EventCharacter)
admin.site.register(EventPlace)
admin.site.register(EventRelationship)
admin.site.register(TimelineSpan)
