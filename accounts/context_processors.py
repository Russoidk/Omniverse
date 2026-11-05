from django.conf import settings


def external_links(request):
    # Estas rutas apuntan al sitio web servido por la misma instancia local de Django.
    return {
        "registration_url": getattr(settings, "OMNIVERSE_REGISTRATION_URL", "/crear-cuenta/"),
        "subscription_url": getattr(settings, "OMNIVERSE_SUBSCRIPTION_URL", "/suscripcion/"),
    }
