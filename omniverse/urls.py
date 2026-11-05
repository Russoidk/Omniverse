from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('website.urls')),
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('proyectos/', include('projects.urls')),
    path('personajes/', include('characters.urls')),
    path('cronologia/', include('timeline.urls')),
    path('red-conceptual/', include('concept_map.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
