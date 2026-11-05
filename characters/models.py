from django.db import models

from projects.models import Project, Place


class Character(models.Model):

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='characters'
    )

    image = models.ImageField(
        upload_to='characters/',
        blank=True,
        null=True
    )

    # Identificación
    full_name = models.CharField(max_length=200)

    role = models.CharField(
        max_length=200,
        blank=True
    )

    # Citas
    quote_1 = models.TextField(blank=True)

    quote_1_author = models.CharField(
        max_length=200,
        blank=True
    )

    quote_1_context = models.CharField(
        max_length=200,
        blank=True
    )

    quote_2 = models.TextField(blank=True)

    quote_2_author = models.CharField(
        max_length=200,
        blank=True
    )

    quote_2_context = models.CharField(
        max_length=200,
        blank=True
    )

    # Datos esenciales
    birth_date = models.CharField(
        max_length=200,
        blank=True
    )

    age_at_story_start = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    species = models.CharField(
        max_length=200,
        blank=True
    )

    current_status = models.CharField(
        max_length=200,
        blank=True
    )

    faction = models.CharField(
        max_length=200,
        blank=True
    )

    main_residence = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        related_name='residents',
        null=True,
        blank=True
    )

    # Rasgos y preferencias
    dominant_traits = models.TextField(blank=True)

    destructive_traits = models.TextField(blank=True)

    secret_dream = models.TextField(blank=True)

    likes = models.TextField(blank=True)

    dislikes = models.TextField(blank=True)

    happier_if = models.TextField(blank=True)

    # Historia
    childhood = models.TextField(blank=True)

    adolescence = models.TextField(blank=True)

    adulthood = models.TextField(blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.full_name


class CharacterRelationship(models.Model):

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='character_relationships'
    )

    character_1 = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name='relationships_from'
    )

    character_2 = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name='relationships_to',
        null=True, blank=True,
    )

    # Free-text references allow relationships to people without a character sheet.
    character_2_name = models.CharField(max_length=200, blank=True, default='')

    relationship_type = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f'{self.character_1} → '
            f'{self.relationship_type} → '
            f'{self.character_2.full_name if self.character_2_id else self.character_2_name}'
        )