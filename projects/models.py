from django.conf import settings
from django.db import models


class Project(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects'
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    # Custom names shown for the two default historical eras.
    era_bc_name = models.CharField(max_length=80, default='Antes de Cristo')
    era_bc_abbreviation = models.CharField(max_length=20, default='A.C.')
    era_ad_name = models.CharField(max_length=80, default='Después de Cristo')
    era_ad_abbreviation = models.CharField(max_length=20, default='D.C.')

    # Dashboard display preferences.
    dashboard_show_stats = models.BooleanField(default=True)
    dashboard_show_module_cards = models.BooleanField(default=True)
    dashboard_show_recent_events = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Place(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='places'
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    image = models.ImageField(
        upload_to='places/',
        blank=True,
        null=True
    )

    type = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name