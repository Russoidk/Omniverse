from django.db import models
import re

from projects.models import Project, Place


class Event(models.Model):
    ERA_BC = 'BC'
    ERA_AD = 'AD'
    ERA_CHOICES = [(ERA_BC, 'Antes de Cristo (A.C.)'), (ERA_AD, 'Después de Cristo (D.C.)')]

    DATE_TYPE_EXACT = 'EXACT'
    DATE_TYPE_YEAR = 'YEAR'
    DATE_TYPE_TEXT = 'TEXT'
    DATE_TYPE_CHOICES = [
        (DATE_TYPE_EXACT, 'Fecha concreta'),
        (DATE_TYPE_YEAR, 'Solo año'),
        (DATE_TYPE_TEXT, 'Texto libre'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='events'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date_value = models.CharField(max_length=200, blank=True)
    date_era = models.CharField(
        max_length=2, choices=ERA_CHOICES, default=ERA_AD, verbose_name='Era histórica'
    )
    date_type = models.CharField(
        max_length=10, choices=DATE_TYPE_CHOICES, default=DATE_TYPE_TEXT
    )
    event_type = models.CharField(max_length=200, blank=True)
    timeline_span = models.ForeignKey(
        'TimelineSpan', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='events', verbose_name='Lapso de tiempo'
    )
    span_marker = models.CharField(
        max_length=5, blank=True, default='',
        choices=[('START', 'Inicio de lapso'), ('END', 'Final de lapso')],
        verbose_name='Marca del lapso'
    )
    sort_order = models.IntegerField(default=0)
    automatic = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date_value', 'sort_order', 'created_at', 'title']

    @property
    def display_date(self):
        return format_era_date(self.date_value, self.date_era, self.date_type, project=self.project)

    def __str__(self):
        return self.title


class EventCharacter(models.Model):
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='character_links'
    )
    character = models.ForeignKey(
        'characters.Character', on_delete=models.CASCADE, related_name='event_links'
    )
    role = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'character'], name='unique_event_character'
            )
        ]

    def __str__(self):
        return f'{self.character} — {self.event}'


class EventPlace(models.Model):
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='place_links'
    )
    place = models.ForeignKey(
        Place, on_delete=models.CASCADE, related_name='event_links'
    )
    role = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['event', 'place'], name='unique_event_place')
        ]

    def __str__(self):
        return f'{self.place} — {self.event}'


class EventRelationship(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='event_relationships'
    )
    event_1 = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='relationships_from'
    )
    event_2 = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='relationships_to'
    )
    relationship_type = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['event_1', 'event_2', 'relationship_type'],
                name='unique_event_relationship_type',
            )
        ]

    def __str__(self):
        return f'{self.event_1} — {self.relationship_type} — {self.event_2}'


class TimelineSpan(models.Model):
    """A named period that spans a beginning and an end on the timeline."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='timeline_spans')
    title = models.CharField(max_length=200)
    start_value = models.CharField(max_length=200)
    start_era = models.CharField(max_length=2, choices=Event.ERA_CHOICES, default=Event.ERA_AD, verbose_name='Era de comienzo')
    end_value = models.CharField(max_length=200)
    end_era = models.CharField(max_length=2, choices=Event.ERA_CHOICES, default=Event.ERA_AD, verbose_name='Era de finalización')
    span_type = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_value', 'created_at', 'title']

    @property
    def start_display(self):
        return format_era_date(self.start_value, self.start_era, project=self.project)

    @property
    def end_display(self):
        return format_era_date(self.end_value, self.end_era, project=self.project)

    def __str__(self):
        return f'{self.title} ({self.start_display} – {self.end_display})'


def format_era_date(value, era=Event.ERA_AD, date_type=None, project=None):
    """Format year-like values with their era without duplicating explicit suffixes."""
    value = str(value or '').strip()
    if not value:
        return 'Sin fecha'
    lowered = value.casefold()
    # Replace the old default abbreviations at the end of a date with the project's
    # configured abbreviation, while leaving arbitrary free-form prose untouched.
    if project is not None:
        match = re.search(r'\s*(a\s*\.?\s*c\.?)$', value, flags=re.IGNORECASE)
        if match:
            return value[:match.start()].rstrip() + ' ' + project.era_bc_abbreviation
        match = re.search(r'\s*(d\s*\.?\s*c\.?)$', value, flags=re.IGNORECASE)
        if match:
            return value[:match.start()].rstrip() + ' ' + project.era_ad_abbreviation
    if re.search(r'(?<![a-z])a\s*\.?\s*c\.?(?![a-z])|(?<![a-z])d\s*\.?\s*c\.?(?![a-z])|\bbce\b|\bce\b|antes de cristo|después de cristo|despues de cristo', lowered):
        return value
    # Free-form narrative dates without a year should remain natural prose.
    if date_type == Event.DATE_TYPE_TEXT and not re.search(r'\d', value):
        return value
    if not re.search(r'\d', value):
        return value
    if project is not None:
        suffix = project.era_bc_abbreviation if era == Event.ERA_BC else project.era_ad_abbreviation
    else:
        suffix = 'A.C.' if era == Event.ERA_BC else 'D.C.'
    return f'{value} {suffix}'
