import re
import unicodedata

from django.db import transaction

from .models import Event, EventCharacter


def guess_date_type(value):
    value = (value or '').strip()
    if re.fullmatch(r'\d{1,2}/\d{1,2}/\d{2,4}', value) or re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return Event.DATE_TYPE_EXACT
    if re.fullmatch(r'\d{1,4}(?:\s*(?:D\.?C\.?|A\.?C\.?|d\.e\.?|a\.e\.?))?', value, re.IGNORECASE):
        return Event.DATE_TYPE_YEAR
    return Event.DATE_TYPE_TEXT


def guess_date_era(value):
    """Infer the era from explicit Spanish/English suffixes; default to D.C."""
    normalized = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').lower()
    if re.search(r'(?<![a-z])a\s*\.?\s*c\.?(?![a-z])|\bbce\b|antes de cristo', normalized):
        return Event.ERA_BC
    return Event.ERA_AD


@transaction.atomic
def sync_birth_event(character):
    """Keep one automatic birth event synchronized with a character's birth date."""
    linked = EventCharacter.objects.filter(
        character=character,
        role='Nacido/a',
        event__automatic=True,
        event__event_type='Nacimiento',
        event__project=character.project,
    ).select_related('event').first()

    birth_date = (character.birth_date or '').strip()
    if not birth_date:
        if linked:
            event = linked.event
            linked.delete()
            if not event.character_links.exists():
                from django.contrib.contenttypes.models import ContentType
                from concept_map.models import ConceptNode
                content_type = ContentType.objects.get_for_model(event, for_concrete_model=False)
                ConceptNode.objects.filter(
                    project=event.project,
                    content_type=content_type,
                    object_id=event.pk,
                ).delete()
                event.delete()
        return None

    if linked:
        event = linked.event
        event.title = f'Nacimiento de {character.full_name}'
        event.date_value = birth_date
        event.date_type = guess_date_type(birth_date)
        event.date_era = guess_date_era(birth_date)
        event.description = f'Fecha de nacimiento de {character.full_name}.'
        event.save()
    else:
        event = Event.objects.create(
            project=character.project,
            title=f'Nacimiento de {character.full_name}',
            description=f'Fecha de nacimiento de {character.full_name}.',
            date_value=birth_date,
            date_type=guess_date_type(birth_date),
            date_era=guess_date_era(birth_date),
            event_type='Nacimiento',
            automatic=True,
        )
        EventCharacter.objects.create(
            event=event,
            character=character,
            role='Nacido/a',
        )

    # Ensure an automatic event always has a corresponding graph node.
    from projects.utils import ensure_concept_node
    ensure_concept_node(character.project, event, 'EVENT')
    return event
